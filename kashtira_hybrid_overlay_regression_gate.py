from __future__ import annotations

import argparse
import copy
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
INTERACTION_CORE = {"Ash Blossom & Joyous Spring", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being"}
QUOTA_TARGETS = {"starters": 12, "starters_searchers": 12, "extenders": 7, "payoffs": 3, "interruptions": 9, "board_breakers": 3, "generic_fill": 0}


def run_hybrid_gate(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    rows = []
    for index in range(max(1, int(runs or 1))):
        run_seed = int(seed) + index
        rows.append(
            {
                "run": index + 1,
                "seed": run_seed,
                "generic": run_builder(cards, mode, run_seed, "generic"),
                "current_experimental": run_builder(cards, mode, run_seed, "current_experimental"),
                "hybrid_overlay": run_builder(cards, mode, run_seed, "hybrid_overlay"),
            }
        )
    generic = summarize(rows, "generic")
    current = summarize(rows, "current_experimental")
    hybrid = summarize(rows, "hybrid_overlay")
    recommendation = choose_recommendation(generic, hybrid)
    return {
        "report_type": "kashtira_hybrid_overlay_regression_gate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": max(1, int(runs or 1)),
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "generic": generic,
        "current_experimental": current,
        "hybrid_overlay": hybrid,
        "hybrid_score_delta_vs_generic": round(hybrid["average_score"] - generic["average_score"], 4),
        "hybrid_score_delta_vs_current_experimental": round(hybrid["average_score"] - current["average_score"], 4),
        "recommendation": recommendation,
        "promotion_applied": False,
        "run_results": rows,
    }


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, kind: str) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if kind == "current_experimental":
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira"}
    elif kind == "hybrid_overlay":
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira", "experimental_variant": "hybrid_generic_interaction_overlay"}
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    score = score_deck_breakdown(deck, "Kashtira", mode)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    return {
        "builder_used": report.get("builder_used"),
        "experimental": bool(report.get("experimental", False)),
        "variant": report.get("variant"),
        "dry_run_variant": bool(report.get("dry_run_variant", False)),
        "fallback_used": bool(report.get("fallback_used", False)),
        "score": float(score.get("final_score", 0) or 0),
        "package_quality": float(score.get("package_quality_score", 0) or 0),
        "brick_penalty": float(score.get("brick_penalty", 0) or 0),
        "consistency": float(score.get("consistency_score", 0) or 0),
        "endboard": float(score.get("endboard_score", 0) or 0),
        "interruption_score": float(score.get("interruption_score", 0) or 0),
        "package_counts": package_counts,
        "quota_balance": quota_balance(package_counts),
        "preserved_interaction_count": interaction_count(deck),
        "generic_fill_count": float(package_counts.get("generic_fill", 0) or 0),
        "legality_ok": int(report.get("main_deck_count", 0) or 0) >= 40 and not blocked,
        "blocked_card_violations": blocked,
    }


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    scores = [row["score"] for row in selected]
    return {
        "average_score": round(mean(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "package_quality": round(mean(row["package_quality"] for row in selected), 4),
        "brick_penalty": round(mean(row["brick_penalty"] for row in selected), 4),
        "consistency": round(mean(row["consistency"] for row in selected), 4),
        "endboard": round(mean(row["endboard"] for row in selected), 4),
        "interruption_score": round(mean(row["interruption_score"] for row in selected), 4),
        "quota_balance": round(mean(row["quota_balance"] for row in selected), 4),
        "preserved_interaction_count": round(mean(row["preserved_interaction_count"] for row in selected), 4),
        "generic_fill_count": round(mean(row["generic_fill_count"] for row in selected), 4),
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in selected), 4),
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in selected), 4),
        "blocked_card_violations": sorted(set(name for row in selected for name in row["blocked_card_violations"])),
        "builders_used": sorted(set(str(row["builder_used"]) for row in selected)),
        "variants": sorted(set(str(row["variant"]) for row in selected if row.get("variant"))),
        "dry_run_variant_rate": round(mean(1.0 if row["dry_run_variant"] else 0.0 for row in selected), 4),
    }


def choose_recommendation(generic: dict[str, Any], hybrid: dict[str, Any]) -> str:
    if hybrid["legality_rate"] < 1.0 or hybrid["fallback_rate"] > 0.0 or hybrid["blocked_card_violations"]:
        return "promote_blocked"
    delta = hybrid["average_score"] - generic["average_score"]
    if delta <= 0:
        return "keep_dry_run_only"
    if delta < 0.5:
        return "needs_retest"
    return "eligible_for_larger_sample"


def quota_balance(package_counts: dict[str, Any]) -> float:
    return round(sum(abs(float(package_counts.get(key, 0) or 0) - target) for key, target in QUOTA_TARGETS.items() if key in package_counts), 4)


def interaction_count(deck: list[dict[str, Any]]) -> int:
    return sum(1 for card in deck if str(card.get("name", "")) in INTERACTION_CORE)


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_kashtira_hybrid_overlay_regression_gate.json"
    md_path = REPORT_DIR / "latest_kashtira_hybrid_overlay_regression_gate.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Hybrid Overlay Regression Gate",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: {report['promotion_applied']}",
        "",
    ]
    for key, title in (("generic", "Generic"), ("current_experimental", "Current Experimental"), ("hybrid_overlay", "Hybrid Overlay")):
        row = report[key]
        lines.extend([
            f"## {title}",
            "",
            f"- Average score: {row['average_score']}",
            f"- Best score: {row['best_score']}",
            f"- Worst score: {row['worst_score']}",
            f"- Package quality: {row['package_quality']}",
            f"- Brick penalty: {row['brick_penalty']}",
            f"- Consistency: {row['consistency']}",
            f"- Endboard: {row['endboard']}",
            f"- Interruption score: {row['interruption_score']}",
            f"- Quota balance: {row['quota_balance']}",
            f"- Preserved interaction count: {row['preserved_interaction_count']}",
            f"- Generic fill count: {row['generic_fill_count']}",
            f"- Legality rate: {row['legality_rate']}",
            f"- Fallback rate: {row['fallback_rate']}",
            "",
        ])
    lines.extend([
        "## Deltas",
        "",
        f"- Hybrid score delta vs generic: {report['hybrid_score_delta_vs_generic']}",
        f"- Hybrid score delta vs current experimental: {report['hybrid_score_delta_vs_current_experimental']}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed-seed dry-run gate for the Kashtira hybrid interaction overlay.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_hybrid_gate(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Hybrid Overlay Regression Gate Complete")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Current experimental average score: {report['current_experimental']['average_score']}")
    print(f"Hybrid average score: {report['hybrid_overlay']['average_score']}")
    print(f"Hybrid delta vs generic: {report['hybrid_score_delta_vs_generic']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
