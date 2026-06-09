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
from deck.executed_dependency_telemetry import build_dependency_telemetry, compare_dependency_summaries, promotion_safety_gates, summarize_dependency_telemetry
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import quota_balance
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_public_overlay_tuning_gate.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_public_overlay_tuning_gate.md"
PATHS = {
    "generic": None,
    "current_experimental": None,
    "hybrid_overlay": "hybrid_generic_interaction_overlay",
    "public_baseline_overlay": "public_baseline_interaction_overlay",
    "public_overlay_reduce_generic_fill": "public_overlay_reduce_generic_fill",
    "public_overlay_archetype_fill_priority": "public_overlay_archetype_fill_priority",
    "public_overlay_interaction_plus_archetype_core": "public_overlay_interaction_plus_archetype_core",
}
TUNING_VARIANTS = (
    "public_overlay_reduce_generic_fill",
    "public_overlay_archetype_fill_priority",
    "public_overlay_interaction_plus_archetype_core",
)


def run_tuning_gate(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        row = {"run": index + 1, "seed": run_seed}
        for key in PATHS:
            row[key] = run_builder(cards, mode, run_seed, key)
        rows.append(row)

    summaries = {key: summarize(rows, key) for key in PATHS}
    generic = summaries["generic"]
    score_delta = {key: round(summaries[key]["average_score"] - generic["average_score"], 4) for key in PATHS if key != "generic"}
    dependency_delta = {
        f"{key}_vs_generic": compare_dependency_summaries(generic["dependency_telemetry"], summaries[key]["dependency_telemetry"])
        for key in PATHS
        if key != "generic"
    }
    safety = {key: promotion_safety_gates(generic["dependency_telemetry"], summaries[key]["dependency_telemetry"]) for key in PATHS if key != "generic"}
    recommendations = {key: choose_recommendation(generic, summaries[key], safety[key]) for key in PATHS if key != "generic"}
    best_variant = choose_best_variant(summaries, recommendations)
    report: dict[str, Any] = {
        "report_type": "kashtira_public_overlay_tuning_gate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        **summaries,
        "score_delta_vs_generic": score_delta,
        "dependency_delta": dependency_delta,
        "generic_fill_gate": {f"{key}_vs_generic": safety[key]["generic_fill_gate"] for key in safety},
        "interaction_loss_gate": {f"{key}_vs_generic": safety[key]["interaction_loss_gate"] for key in safety},
        "promotion_blocking_reasons": {f"{key}_vs_generic": safety[key]["promotion_blocking_reasons"] for key in safety},
        "lost_interaction_cards": {f"{key}_vs_generic": safety[key]["lost_interaction_cards"] for key in safety},
        "recommendations": recommendations,
        "best_variant": best_variant,
        "recommendation": recommendations.get(best_variant, "keep_dry_run_only") if best_variant else "keep_dry_run_only",
        "promotion_applied": False,
        "run_results": rows,
    }
    return report


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, key: str) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    variant = PATHS[key]
    if key == "current_experimental":
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira"}
    elif variant:
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira", "experimental_variant": variant}
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    score = score_deck_breakdown(deck, "Kashtira", mode)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    telemetry = build_dependency_telemetry(deck, report, "Kashtira")
    main_count = int(report.get("main_deck_count", 0) or 0)
    extra_count = int(report.get("extra_deck_count", 0) or 0)
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
        "fallback_rate_value": 1.0 if report.get("fallback_used") else 0.0,
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
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
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


def choose_recommendation(generic: dict[str, Any], candidate: dict[str, Any], safety: dict[str, Any]) -> str:
    score_delta = float(candidate.get("average_score", 0) or 0) - float(generic.get("average_score", 0) or 0)
    if safety.get("interaction_loss_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if score_delta < 0:
        return "keep_dry_run_only"
    if safety.get("generic_fill_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if candidate.get("blocked_card_violations") or float(candidate.get("legality_rate", 0) or 0) < 1.0:
        return "keep_dry_run_only"
    if score_delta < 0.5:
        return "needs_retest"
    return "eligible_for_larger_sample"


def choose_best_variant(summaries: dict[str, dict[str, Any]], recommendations: dict[str, str]) -> str | None:
    ordered = sorted(
        TUNING_VARIANTS,
        key=lambda key: (
            recommendations.get(key) == "eligible_for_larger_sample",
            recommendations.get(key) == "needs_retest",
            -float(summaries[key].get("generic_fill_average") or 9999),
            float(summaries[key].get("average_score") or 0),
        ),
        reverse=True,
    )
    return ordered[0] if ordered else None


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Public Overlay Tuning Gate",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: `{report['runs']}`",
        f"- Seed: `{report['seed']}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- Best variant: `{report['best_variant']}`",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: `{report['promotion_applied']}`",
        "",
        "## Summary",
        "",
        "| Path | Avg Score | Delta | Generic Fill | Interaction | Lost Cards | Quota Gap | Package Quality | Brick Penalty | Legality | Fallback | Recommendation |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for key, title in (
        ("generic", "Generic"),
        ("current_experimental", "Current Experimental"),
        ("hybrid_overlay", "Hybrid Overlay"),
        ("public_baseline_overlay", "Public Baseline Overlay"),
        ("public_overlay_reduce_generic_fill", "Reduce Generic Fill"),
        ("public_overlay_archetype_fill_priority", "Archetype Fill Priority"),
        ("public_overlay_interaction_plus_archetype_core", "Interaction + Archetype Core"),
    ):
        row = report[key]
        delta = 0.0 if key == "generic" else report["score_delta_vs_generic"][key]
        lost = [] if key == "generic" else report["lost_interaction_cards"].get(f"{key}_vs_generic", [])
        rec = "baseline" if key == "generic" else report["recommendations"].get(key)
        lines.append(
            f"| {title} | {row['average_score']} | {delta} | {row['generic_fill_average']} | "
            f"{row['interaction_selected_average']} | {', '.join(lost) or 'none'} | {row['quota_balance']} | "
            f"{row['average_package_quality']} | {row['average_brick_penalty']} | {row['legality_rate']} | {row['fallback_rate']} | {rec} |"
        )
    lines.extend(
        [
            "",
            "## Interaction Core",
            "",
            f"- Registry cards: `{list(interaction_core_for('Kashtira'))}`",
            "",
            "## Safety Notes",
            "",
            "- All tuning variants are explicit dry-run paths.",
            "- Recommendation remains report-only.",
            "- Generic-fill and interaction-loss gates are evaluated from executed deck telemetry.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare public-overlay Kashtira dry-run tuning variants.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_tuning_gate(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    best = report["best_variant"]
    print("Kashtira Public Overlay Tuning Gate Complete")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Best variant: {best}")
    print(f"Best variant average score: {report[best]['average_score'] if best else 'none'}")
    print(f"Best variant generic fill: {report[best]['generic_fill_average'] if best else 'none'}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
