from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from kashtira_h_variant_dry_run_gate import H_DRY_RUN_VARIANT, run_builder, safety_metrics, summarize
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_h_variant_broader_validation.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_h_variant_broader_validation.md"


def run_broader_validation(
    mode: str = "meta",
    runs: int = 50,
    seeds: list[int] | None = None,
    frozen_cards: bool = False,
) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    seed_values = [int(seed) for seed in (seeds or [12345, 23456, 34567])]
    per_seed = []
    total_positive = 0
    total_negative = 0
    total_neutral = 0

    for seed in seed_values:
        rows = []
        for index in range(run_count):
            run_seed = seed + index
            generic = run_builder(cards, mode, run_seed, None)
            h_variant = run_builder(cards, mode, run_seed, H_DRY_RUN_VARIANT)
            delta = round(h_variant["score"] - generic["score"], 4)
            rows.append(
                {
                    "run": index + 1,
                    "seed_used": run_seed,
                    "generic": generic,
                    "h_variant": h_variant,
                    "delta": delta,
                    "outcome": classify_delta(delta),
                }
            )

        generic_summary = summarize([row["generic"] for row in rows])
        h_summary = summarize([row["h_variant"] for row in rows])
        delta = round(h_summary["average_score"] - generic_summary["average_score"], 4)
        positives = sum(1 for row in rows if row["delta"] > 0)
        negatives = sum(1 for row in rows if row["delta"] < 0)
        neutrals = sum(1 for row in rows if row["delta"] == 0)
        total_positive += positives
        total_negative += negatives
        total_neutral += neutrals
        safety = safety_metrics(generic_summary, h_summary)
        blockers = seed_blockers(delta, safety)
        per_seed.append(
            {
                "seed": seed,
                "runs": run_count,
                "generic": generic_summary,
                "h_variant": h_summary,
                "delta": delta,
                "positive_run_count": positives,
                "negative_run_count": negatives,
                "neutral_run_count": neutrals,
                "positive_rate": round(positives / run_count, 4),
                "legality_rate": h_summary["legality_rate"],
                "fallback_rate": h_summary["fallback_rate"],
                "interaction_count": h_summary["interaction_count"],
                "generic_fill_count": h_summary["generic_fill_count"],
                "blocked_card_violations": h_summary["blocked_card_violations"],
                "safety_metrics": safety,
                "promotion_blockers": blockers,
                "run_results": rows,
            }
        )

    deltas = [float(seed_report["delta"]) for seed_report in per_seed]
    total_runs = run_count * max(1, len(seed_values))
    aggregate = {
        "average_delta_across_seeds": round(mean(deltas), 4),
        "worst_seed_delta": round(min(deltas), 4),
        "best_seed_delta": round(max(deltas), 4),
        "total_positive_run_count": total_positive,
        "total_negative_run_count": total_negative,
        "total_neutral_run_count": total_neutral,
        "total_positive_rate": round(total_positive / total_runs, 4),
        "safety_status": aggregate_safety(per_seed),
    }
    recommendation = choose_recommendation(per_seed, aggregate)
    return {
        "report_type": "kashtira_h_variant_broader_validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs_per_seed": run_count,
        "seeds": seed_values,
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "h_dry_run_variant": H_DRY_RUN_VARIANT,
        "per_seed_results": per_seed,
        "aggregate": aggregate,
        "recommendation": recommendation,
        "promotion_applied": False,
        "default_behavior_changed": False,
    }


def classify_delta(delta: float) -> str:
    if delta > 0:
        return "positive"
    if delta < 0:
        return "negative"
    return "neutral"


def seed_blockers(delta: float, safety: dict[str, Any]) -> list[str]:
    blockers = list(safety.get("promotion_blocking_reasons", []) or [])
    if delta <= 0:
        blockers.append("seed_average_delta_not_positive")
    return sorted(set(blockers))


def aggregate_safety(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = sorted(set(reason for seed in per_seed for reason in seed.get("promotion_blockers", [])))
    return {
        "clean": not blockers,
        "promotion_blockers": blockers,
        "any_legality_issue": any(float(seed.get("legality_rate", 0) or 0) < 1.0 for seed in per_seed),
        "any_fallback": any(float(seed.get("fallback_rate", 0) or 0) > 0 for seed in per_seed),
        "any_blocked_card_violation": any(seed.get("blocked_card_violations") for seed in per_seed),
        "any_interaction_drop": any(float((seed.get("safety_metrics") or {}).get("interaction_delta_vs_generic", 0) or 0) < 0 for seed in per_seed),
        "any_generic_fill_increase": any(float((seed.get("safety_metrics") or {}).get("generic_fill_delta_vs_generic", 0) or 0) > 0 for seed in per_seed),
    }


def choose_recommendation(per_seed: list[dict[str, Any]], aggregate: dict[str, Any]) -> str:
    safety = aggregate.get("safety_status", {})
    if any(float(seed.get("delta", 0) or 0) <= 0 for seed in per_seed):
        return "keep_dry_run_only"
    if float(aggregate.get("total_positive_rate", 0) or 0) < 0.75:
        return "keep_dry_run_only"
    if not safety.get("clean", False):
        return "keep_dry_run_only"
    if float(aggregate.get("worst_seed_delta", 0) or 0) < 0.5:
        return "needs_more_data"
    return "eligible_for_candidate_review"


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# Kashtira H Variant Broader Validation",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs per seed: `{report['runs_per_seed']}`",
        f"- Seeds: `{', '.join(str(seed) for seed in report['seeds'])}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- H dry-run variant: `{report['h_dry_run_variant']}`",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: `{report['promotion_applied']}`",
        "",
        "## Per-Seed Results",
        "",
        "| Seed | Generic Avg | H Avg | Delta | Positive | Negative | Neutral | Legality | Fallback | Interaction | Generic Fill | Blockers |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for seed_report in report["per_seed_results"]:
        blockers = ", ".join(seed_report.get("promotion_blockers", [])) or "none"
        lines.append(
            f"| {seed_report['seed']} | {seed_report['generic']['average_score']} | {seed_report['h_variant']['average_score']} | "
            f"{seed_report['delta']} | {seed_report['positive_run_count']} | {seed_report['negative_run_count']} | "
            f"{seed_report['neutral_run_count']} | {seed_report['legality_rate']} | {seed_report['fallback_rate']} | "
            f"{seed_report['interaction_count']} | {seed_report['generic_fill_count']} | {blockers} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Average delta across seeds: `{aggregate['average_delta_across_seeds']}`",
            f"- Worst seed delta: `{aggregate['worst_seed_delta']}`",
            f"- Best seed delta: `{aggregate['best_seed_delta']}`",
            f"- Total positive / negative / neutral: `{aggregate['total_positive_run_count']}` / `{aggregate['total_negative_run_count']}` / `{aggregate['total_neutral_run_count']}`",
            f"- Total positive rate: `{aggregate['total_positive_rate']}`",
            f"- Safety status: `{aggregate['safety_status']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run broader fixed-seed validation for the explicit Kashtira H dry-run variant.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--seeds", type=int, nargs="+", default=[12345, 23456, 34567])
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_broader_validation(args.mode, args.runs, args.seeds, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    aggregate = report["aggregate"]
    print("Kashtira H Variant Broader Validation Complete")
    print(f"Seeds: {', '.join(str(seed) for seed in report['seeds'])}")
    print(f"Runs per seed: {report['runs_per_seed']}")
    print(f"Average delta across seeds: {aggregate['average_delta_across_seeds']}")
    print(f"Worst seed delta: {aggregate['worst_seed_delta']}")
    print(f"Best seed delta: {aggregate['best_seed_delta']}")
    print(f"Total positive / negative / neutral: {aggregate['total_positive_run_count']} / {aggregate['total_negative_run_count']} / {aggregate['total_neutral_run_count']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
