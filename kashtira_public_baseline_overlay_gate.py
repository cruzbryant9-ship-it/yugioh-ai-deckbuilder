from __future__ import annotations

import argparse
import copy
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations
from deck.executed_dependency_telemetry import build_dependency_telemetry, compare_dependency_summaries, promotion_safety_gates, summarize_dependency_telemetry
from kashtira_experimental_regression_gate import quota_balance
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_public_baseline_overlay_gate.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_public_baseline_overlay_gate.md"


def run_public_baseline_gate(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    rows = []
    run_count = max(1, int(runs or 1))
    for index in range(run_count):
        run_seed = int(seed) + index
        rows.append(
            {
                "run": index + 1,
                "seed": run_seed,
                "generic": run_builder(cards, mode, run_seed, "generic"),
                "current_experimental": run_builder(cards, mode, run_seed, "current_experimental"),
                "hybrid_overlay": run_builder(cards, mode, run_seed, "hybrid_overlay"),
                "public_baseline_overlay": run_builder(cards, mode, run_seed, "public_baseline_overlay"),
            }
        )
    generic = summarize(rows, "generic")
    current = summarize(rows, "current_experimental")
    hybrid = summarize(rows, "hybrid_overlay")
    public = summarize(rows, "public_baseline_overlay")
    current_safety = promotion_safety_gates(generic["dependency_telemetry"], current["dependency_telemetry"])
    hybrid_safety = promotion_safety_gates(generic["dependency_telemetry"], hybrid["dependency_telemetry"])
    public_safety = promotion_safety_gates(generic["dependency_telemetry"], public["dependency_telemetry"])
    recommendation = choose_recommendation(generic, public, public_safety)
    return {
        "report_type": "kashtira_public_baseline_overlay_gate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "generic": generic,
        "current_experimental": current,
        "hybrid_overlay": hybrid,
        "public_baseline_overlay": public,
        "score_delta_vs_generic": {
            "current_experimental": round(current["average_score"] - generic["average_score"], 4),
            "hybrid_overlay": round(hybrid["average_score"] - generic["average_score"], 4),
            "public_baseline_overlay": round(public["average_score"] - generic["average_score"], 4),
        },
        "dependency_delta": {
            "current_experimental_vs_generic": compare_dependency_summaries(generic["dependency_telemetry"], current["dependency_telemetry"]),
            "hybrid_overlay_vs_generic": compare_dependency_summaries(generic["dependency_telemetry"], hybrid["dependency_telemetry"]),
            "public_baseline_overlay_vs_generic": compare_dependency_summaries(generic["dependency_telemetry"], public["dependency_telemetry"]),
        },
        "generic_fill_gate": {
            "current_experimental_vs_generic": current_safety["generic_fill_gate"],
            "hybrid_overlay_vs_generic": hybrid_safety["generic_fill_gate"],
            "public_baseline_overlay_vs_generic": public_safety["generic_fill_gate"],
        },
        "interaction_loss_gate": {
            "current_experimental_vs_generic": current_safety["interaction_loss_gate"],
            "hybrid_overlay_vs_generic": hybrid_safety["interaction_loss_gate"],
            "public_baseline_overlay_vs_generic": public_safety["interaction_loss_gate"],
        },
        "promotion_blocking_reasons": {
            "current_experimental_vs_generic": current_safety["promotion_blocking_reasons"],
            "hybrid_overlay_vs_generic": hybrid_safety["promotion_blocking_reasons"],
            "public_baseline_overlay_vs_generic": public_safety["promotion_blocking_reasons"],
        },
        "lost_interaction_cards": {
            "current_experimental_vs_generic": current_safety["lost_interaction_cards"],
            "hybrid_overlay_vs_generic": hybrid_safety["lost_interaction_cards"],
            "public_baseline_overlay_vs_generic": public_safety["lost_interaction_cards"],
        },
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
    elif kind == "public_baseline_overlay":
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira", "experimental_variant": "public_baseline_interaction_overlay"}
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    score = score_deck_breakdown(deck, "Kashtira", mode)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    telemetry = build_dependency_telemetry(deck, report, "Kashtira")
    return {
        "builder_used": report.get("builder_used"),
        "experimental": bool(report.get("experimental", False)),
        "variant": report.get("variant"),
        "dry_run_variant": bool(report.get("dry_run_variant", False)),
        "not_default": bool(report.get("not_default", False)),
        "fallback_used": bool(report.get("fallback_used", False)),
        "score": float(score.get("final_score", 0) or 0),
        "package_quality": float(score.get("package_quality_score", 0) or 0),
        "package_counts": package_counts,
        "quota_balance": quota_balance(package_counts),
        "generic_fill_count": telemetry["generic_fill_count"],
        "interaction_selected_count": telemetry["interaction_candidates_selected"],
        "dependency_telemetry": telemetry,
        "legality_ok": int(report.get("main_deck_count", 0) or 0) >= 40 and not blocked,
        "blocked_card_violations": blocked,
    }


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    dependency = summarize_dependency_telemetry(selected)
    scores = [float(row["score"]) for row in selected]
    generic_fill_average = dependency["generic_fill_count"].get("average")
    interaction_selected_average = dependency["interaction_candidates_selected"].get("average")
    return {
        "average_score": round(mean(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "quota_balance": round(mean(float(row["quota_balance"]) for row in selected), 4),
        "generic_fill_count": dependency["generic_fill_count"],
        "generic_fill_average": generic_fill_average,
        "interaction_selected_count": dependency["interaction_candidates_selected"],
        "interaction_selected_average": interaction_selected_average,
        "dependency_telemetry": dependency,
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in selected), 4),
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in selected), 4),
        "blocked_card_violations": sorted(set(name for row in selected for name in row["blocked_card_violations"])),
        "builders_used": sorted(set(str(row["builder_used"]) for row in selected)),
        "variants": sorted(set(str(row["variant"]) for row in selected if row.get("variant"))),
        "dry_run_variant_rate": round(mean(1.0 if row["dry_run_variant"] else 0.0 for row in selected), 4),
    }


def choose_recommendation(generic: dict[str, Any], public: dict[str, Any], safety: dict[str, Any]) -> str:
    score_delta = float(public.get("average_score", 0) or 0) - float(generic.get("average_score", 0) or 0)
    if score_delta < 0:
        return "keep_dry_run_only"
    if safety.get("interaction_loss_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if safety.get("generic_fill_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if public.get("blocked_card_violations") or float(public.get("legality_rate", 0) or 0) < 1.0:
        return "keep_dry_run_only"
    if score_delta < 0.5:
        return "needs_retest"
    return "eligible_for_larger_sample"


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Public Baseline Interaction Overlay Gate",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: {report['promotion_applied']}",
        "",
        "## Summary",
        "",
        "| Path | Average Score | Delta vs Generic | Quota Balance | Generic Fill | Interaction Selected | Legality | Fallback |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for key, title in (
        ("generic", "Generic"),
        ("current_experimental", "Current Experimental"),
        ("hybrid_overlay", "Hybrid Overlay"),
        ("public_baseline_overlay", "Public Baseline Overlay"),
    ):
        row = report[key]
        delta = 0.0 if key == "generic" else report["score_delta_vs_generic"][key]
        lines.append(
            f"| {title} | {row['average_score']} | {delta} | {row['quota_balance']} | "
            f"{row['generic_fill_average']} | {row['interaction_selected_average']} | {row['legality_rate']} | {row['fallback_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Public Baseline Safety Gates",
            "",
            f"- Generic-fill gate: `{report['generic_fill_gate']['public_baseline_overlay_vs_generic']}`",
            f"- Interaction-loss gate: `{report['interaction_loss_gate']['public_baseline_overlay_vs_generic']}`",
            f"- Promotion-blocking reasons: `{report['promotion_blocking_reasons']['public_baseline_overlay_vs_generic']}`",
            f"- Lost interaction cards: `{report['lost_interaction_cards']['public_baseline_overlay_vs_generic']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed-seed dry-run gate for public-baseline Kashtira interaction overlay.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_public_baseline_gate(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Public Baseline Overlay Gate Complete")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Public overlay average score: {report['public_baseline_overlay']['average_score']}")
    print(f"Public overlay delta vs generic: {report['score_delta_vs_generic']['public_baseline_overlay']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
