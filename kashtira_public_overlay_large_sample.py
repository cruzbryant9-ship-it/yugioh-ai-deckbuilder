from __future__ import annotations

import argparse
import copy
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations
from deck.executed_dependency_telemetry import build_dependency_telemetry, compare_dependency_summaries, promotion_safety_gates, summarize_dependency_telemetry
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import quota_balance
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_public_overlay_large_sample.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_public_overlay_large_sample.md"
VARIANT = "public_overlay_reduce_generic_fill"


def run_large_sample(mode: str = "meta", runs: int = 30, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        generic = run_builder(cards, mode, run_seed, experimental=False)
        variant = run_builder(cards, mode, run_seed, experimental=True)
        delta = round(float(variant["score"]) - float(generic["score"]), 4)
        rows.append({"run": index + 1, "seed": run_seed, "generic": generic, "variant": variant, "score_delta": delta})

    generic_summary = summarize(rows, "generic")
    variant_summary = summarize(rows, "variant")
    deltas = [float(row["score_delta"]) for row in rows]
    safety = promotion_safety_gates(generic_summary["dependency_telemetry"], variant_summary["dependency_telemetry"])
    score_delta = round(float(variant_summary["average_score"]) - float(generic_summary["average_score"]), 4)
    recommendation = choose_recommendation(generic_summary, variant_summary, score_delta, safety)
    return {
        "report_type": "kashtira_public_overlay_large_sample",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "variant_name": VARIANT,
        "generic": generic_summary,
        "variant": variant_summary,
        "score_delta": score_delta,
        "delta_standard_deviation": round(pstdev(deltas), 6) if deltas else 0.0,
        "positive_run_count": sum(1 for value in deltas if value > 0),
        "negative_run_count": sum(1 for value in deltas if value < 0),
        "neutral_run_count": sum(1 for value in deltas if value == 0),
        "dependency_delta": compare_dependency_summaries(generic_summary["dependency_telemetry"], variant_summary["dependency_telemetry"]),
        "generic_fill_gate": safety["generic_fill_gate"],
        "interaction_loss_gate": safety["interaction_loss_gate"],
        "promotion_blocking_reasons": safety["promotion_blocking_reasons"],
        "lost_interaction_cards": safety["lost_interaction_cards"],
        "recommendation": recommendation,
        "promotion_applied": False,
        "run_results": rows,
    }


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, experimental: bool) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if experimental:
        kwargs = {
            "experimental_semi_specialized": True,
            "specialization_profile": "Kashtira",
            "experimental_variant": VARIANT,
        }
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    score = score_deck_breakdown(deck, "Kashtira", mode)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    main_count = int(report.get("main_deck_count", 0) or 0)
    extra_count = int(report.get("extra_deck_count", 0) or 0)
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
        "brick_penalty": float(score.get("brick_penalty", 0) or 0),
        "package_counts": package_counts,
        "quota_balance": quota_balance(package_counts),
        "generic_fill_count": telemetry["generic_fill_count"],
        "interaction_selected_count": telemetry["interaction_candidates_selected"],
        "dependency_telemetry": telemetry,
        "legality_ok": main_count >= 40 and extra_count <= 15 and not blocked,
        "blocked_card_violations": blocked,
    }


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    dependency = summarize_dependency_telemetry(selected)
    scores = [float(row["score"]) for row in selected]
    package_quality = [float(row["package_quality"]) for row in selected]
    brick_penalty = [float(row["brick_penalty"]) for row in selected]
    package_totals: Counter[str] = Counter()
    for row in selected:
        package_totals.update({name: float(value or 0) for name, value in (row.get("package_counts", {}) or {}).items()})
    return {
        "average_score": round(mean(scores), 4),
        "median_score": round(median(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "score_standard_deviation": round(pstdev(scores), 6) if len(scores) > 1 else 0.0,
        "average_package_quality": round(mean(package_quality), 4),
        "average_brick_penalty": round(mean(brick_penalty), 4),
        "quota_balance": round(mean(float(row["quota_balance"]) for row in selected), 4),
        "average_package_counts": {name: round(total / max(1, len(selected)), 4) for name, total in sorted(package_totals.items())},
        "generic_fill_count": dependency["generic_fill_count"],
        "generic_fill_average": dependency["generic_fill_count"].get("average"),
        "interaction_selected_count": dependency["interaction_candidates_selected"],
        "interaction_selected_average": dependency["interaction_candidates_selected"].get("average"),
        "dependency_telemetry": dependency,
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in selected), 4),
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in selected), 4),
        "blocked_card_violations": sorted(set(name for row in selected for name in row["blocked_card_violations"])),
        "builders_used": sorted(set(str(row["builder_used"]) for row in selected)),
        "variants": sorted(set(str(row["variant"]) for row in selected if row.get("variant"))),
        "dry_run_variant_rate": round(mean(1.0 if row["dry_run_variant"] else 0.0 for row in selected), 4),
    }


def choose_recommendation(generic: dict[str, Any], variant: dict[str, Any], score_delta: float, safety: dict[str, Any]) -> str:
    if score_delta <= 0:
        return "keep_dry_run_only"
    if float(variant.get("legality_rate", 0) or 0) < 1.0 or float(variant.get("fallback_rate", 0) or 0) > 0.0:
        return "keep_dry_run_only"
    if variant.get("blocked_card_violations"):
        return "keep_dry_run_only"
    if safety.get("interaction_loss_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if safety.get("generic_fill_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if score_delta < 0.5:
        return "needs_more_data"
    return "eligible_for_experimental_update"


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Public Overlay Large Sample",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: `{report['runs']}`",
        f"- Seed: `{report['seed']}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- Variant: `{report['variant_name']}`",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: `{report['promotion_applied']}`",
        "",
        "## Score Results",
        "",
        "| Path | Average | Median | Best | Worst | Std Dev | Package Quality | Brick Penalty | Quota Gap | Generic Fill | Interaction | Legality | Fallback |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, title in (("generic", "Generic"), ("variant", "Public Overlay Reduce Generic Fill")):
        row = report[key]
        lines.append(
            f"| {title} | {row['average_score']} | {row['median_score']} | {row['best_score']} | {row['worst_score']} | "
            f"{row['score_standard_deviation']} | {row['average_package_quality']} | {row['average_brick_penalty']} | "
            f"{row['quota_balance']} | {row['generic_fill_average']} | {row['interaction_selected_average']} | "
            f"{row['legality_rate']} | {row['fallback_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Delta Summary",
            "",
            f"- Average score delta: `{report['score_delta']}`",
            f"- Delta standard deviation: `{report['delta_standard_deviation']}`",
            f"- Positive / negative / neutral runs: `{report['positive_run_count']}` / `{report['negative_run_count']}` / `{report['neutral_run_count']}`",
            f"- Lost interaction cards: `{report['lost_interaction_cards']}`",
            f"- Promotion-blocking reasons: `{report['promotion_blocking_reasons']}`",
            "",
            "## Interaction Core",
            "",
            f"- Registry cards: `{list(interaction_core_for('Kashtira'))}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a larger fixed-seed public-overlay Kashtira validation sample.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_large_sample(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Public Overlay Large Sample Complete")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Variant average score: {report['variant']['average_score']}")
    print(f"Score delta: {report['score_delta']}")
    print(f"Positive/negative/neutral runs: {report['positive_run_count']}/{report['negative_run_count']}/{report['neutral_run_count']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
