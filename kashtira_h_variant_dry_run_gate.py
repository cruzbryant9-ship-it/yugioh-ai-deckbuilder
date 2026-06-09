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
from deck.deck_utils import blocked_card_violations, split_deck
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import quota_balance
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_h_variant_dry_run_gate.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_h_variant_dry_run_gate.md"
PUBLIC_OVERLAY_VARIANT = "public_overlay_reduce_generic_fill"
H_DRY_RUN_VARIANT = "public_overlay_restore_overlap_reduce_preparations"


def run_h_dry_run_gate(mode: str = "meta", runs: int = 50, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        generic = run_builder(cards, mode, run_seed, None)
        public_overlay = run_builder(cards, mode, run_seed, PUBLIC_OVERLAY_VARIANT)
        h_variant = run_builder(cards, mode, run_seed, H_DRY_RUN_VARIANT)
        rows.append(
            {
                "run": index + 1,
                "seed": run_seed,
                "generic": generic,
                "public_overlay": public_overlay,
                "h_variant": h_variant,
                "h_delta_vs_generic": round(h_variant["score"] - generic["score"], 4),
                "h_delta_vs_public_overlay": round(h_variant["score"] - public_overlay["score"], 4),
            }
        )

    generic_summary = summarize([row["generic"] for row in rows])
    overlay_summary = summarize([row["public_overlay"] for row in rows])
    h_summary = summarize([row["h_variant"] for row in rows])
    h_summary.update(
        {
            "delta_vs_generic": round(h_summary["average_score"] - generic_summary["average_score"], 4),
            "delta_vs_public_overlay": round(h_summary["average_score"] - overlay_summary["average_score"], 4),
            "package_quality_delta_vs_public_overlay": round(h_summary["average_package_quality"] - overlay_summary["average_package_quality"], 4),
            "endboard_delta_vs_public_overlay": round(h_summary["average_endboard_score"] - overlay_summary["average_endboard_score"], 4),
            "brick_penalty_delta_vs_public_overlay": round(h_summary["average_brick_penalty"] - overlay_summary["average_brick_penalty"], 4),
        }
    )
    deltas = [float(row["h_delta_vs_generic"]) for row in rows]
    overlay_deltas = [float(row["h_delta_vs_public_overlay"]) for row in rows]
    safety = safety_metrics(generic_summary, h_summary)
    recommendation = choose_recommendation(h_summary, safety, deltas)
    return {
        "report_type": "kashtira_h_variant_dry_run_gate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "public_overlay_variant": PUBLIC_OVERLAY_VARIANT,
        "h_dry_run_variant": H_DRY_RUN_VARIANT,
        "generic": generic_summary,
        "public_overlay": overlay_summary,
        "h_variant": h_summary,
        "delta_vs_generic_standard_deviation": round(pstdev(deltas), 6) if len(deltas) > 1 else 0.0,
        "delta_vs_public_overlay_standard_deviation": round(pstdev(overlay_deltas), 6) if len(overlay_deltas) > 1 else 0.0,
        "positive_run_count": sum(1 for value in deltas if value > 0),
        "negative_run_count": sum(1 for value in deltas if value < 0),
        "neutral_run_count": sum(1 for value in deltas if value == 0),
        "positive_vs_public_overlay_run_count": sum(1 for value in overlay_deltas if value > 0),
        "negative_vs_public_overlay_run_count": sum(1 for value in overlay_deltas if value < 0),
        "neutral_vs_public_overlay_run_count": sum(1 for value in overlay_deltas if value == 0),
        "safety_metrics": safety,
        "promotion_blocking_reasons": safety["promotion_blocking_reasons"],
        "recommendation": recommendation,
        "promotion_applied": False,
        "run_results": rows,
    }


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, variant: str | None) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if variant:
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": "Kashtira", "experimental_variant": variant}
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    return deck_metrics(deck, report, mode)


def deck_metrics(deck: list[dict[str, Any]], report: dict[str, Any], mode: str) -> dict[str, Any]:
    score = score_deck_breakdown(deck, "Kashtira", mode)
    main, extra = split_deck(deck)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    interaction_count = sum(1 for card in main if str(card.get("name", "")) in interaction_core_for("Kashtira"))
    return {
        "score": float(score.get("final_score", 0) or 0),
        "package_quality": float(score.get("package_quality_score", 0) or 0),
        "endboard_score": float(score.get("endboard_score", 0) or 0),
        "brick_penalty": float(score.get("brick_penalty", 0) or 0),
        "package_counts": package_counts,
        "quota_balance": quota_balance(package_counts),
        "interaction_count": float(interaction_count),
        "generic_fill_count": float(package_counts.get("generic_fill", 0) or 0),
        "legality_ok": len(main) >= 40 and len(extra) <= 15 and not blocked,
        "fallback_used": bool(report.get("fallback_used", False)),
        "blocked_card_violations": blocked,
        "builder_used": report.get("builder_used"),
        "experimental": bool(report.get("experimental", False)),
        "variant": report.get("variant"),
        "dry_run_variant": bool(report.get("dry_run_variant", False)),
        "not_default": bool(report.get("not_default", False)),
        "h_variant_status": report.get("h_variant_status"),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row["score"]) for row in rows]
    package_totals: Counter[str] = Counter()
    for row in rows:
        package_totals.update({name: float(value or 0) for name, value in (row.get("package_counts", {}) or {}).items()})
    return {
        "average_score": round(mean(scores), 4),
        "median_score": round(median(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "score_standard_deviation": round(pstdev(scores), 6) if len(scores) > 1 else 0.0,
        "average_package_quality": round(mean(float(row["package_quality"]) for row in rows), 4),
        "average_endboard_score": round(mean(float(row["endboard_score"]) for row in rows), 4),
        "average_brick_penalty": round(mean(float(row["brick_penalty"]) for row in rows), 4),
        "quota_balance": round(mean(float(row["quota_balance"]) for row in rows), 4),
        "average_package_counts": {name: round(total / max(1, len(rows)), 4) for name, total in sorted(package_totals.items())},
        "interaction_count": round(mean(float(row["interaction_count"]) for row in rows), 4),
        "generic_fill_count": round(mean(float(row["generic_fill_count"]) for row in rows), 4),
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in rows), 4),
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in rows), 4),
        "blocked_card_violations": sorted(set(name for row in rows for name in row["blocked_card_violations"])),
        "builders_used": sorted(set(str(row.get("builder_used")) for row in rows)),
        "variants": sorted(set(str(row.get("variant")) for row in rows if row.get("variant"))),
        "dry_run_variant_rate": round(mean(1.0 if row["dry_run_variant"] else 0.0 for row in rows), 4),
        "h_variant_applied_rate": round(mean(1.0 if (row.get("h_variant_status") or {}).get("applied") else 0.0 for row in rows), 4),
        "h_variant_failures": sorted(set((row.get("h_variant_status") or {}).get("reason") for row in rows if (row.get("h_variant_status") or {}).get("applied") is False)),
    }


def safety_metrics(generic: dict[str, Any], h_variant: dict[str, Any]) -> dict[str, Any]:
    generic_fill_delta = round(float(h_variant.get("generic_fill_count", 0) or 0) - float(generic.get("generic_fill_count", 0) or 0), 4)
    interaction_delta = round(float(h_variant.get("interaction_count", 0) or 0) - float(generic.get("interaction_count", 0) or 0), 4)
    reasons = []
    if float(h_variant.get("legality_rate", 0) or 0) < 1.0:
        reasons.append("legality_issue")
    if float(h_variant.get("fallback_rate", 0) or 0) > 0:
        reasons.append("fallback_used")
    if h_variant.get("blocked_card_violations"):
        reasons.append("blocked_card_violation")
    if interaction_delta < 0:
        reasons.append("interaction_loss")
    if generic_fill_delta > 0:
        reasons.append("generic_fill_increase")
    if float(h_variant.get("h_variant_applied_rate", 0) or 0) < 1.0:
        reasons.append("h_variant_not_always_applied")
    return {
        "generic_fill_delta_vs_generic": generic_fill_delta,
        "interaction_delta_vs_generic": interaction_delta,
        "interaction_loss_count": abs(interaction_delta) if interaction_delta < 0 else 0.0,
        "legality_rate": h_variant.get("legality_rate"),
        "fallback_rate": h_variant.get("fallback_rate"),
        "blocked_card_violations": h_variant.get("blocked_card_violations", []),
        "h_variant_applied_rate": h_variant.get("h_variant_applied_rate"),
        "promotion_blocking_reasons": reasons,
    }


def choose_recommendation(h_variant: dict[str, Any], safety: dict[str, Any], deltas: list[float]) -> str:
    delta = round(float(h_variant.get("delta_vs_generic", 0) or 0), 4)
    positive_rate = sum(1 for value in deltas if value > 0) / max(1, len(deltas))
    if delta <= 0 or safety.get("promotion_blocking_reasons"):
        return "keep_dry_run_only"
    if delta < 0.5:
        return "needs_retest"
    if delta >= 2.0 and positive_rate >= 0.9:
        return "eligible_for_experimental_candidate"
    return "eligible_for_larger_sample"


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira H Variant Dry-Run Gate",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: `{report['runs']}`",
        f"- Seed: `{report['seed']}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- H dry-run variant: `{report['h_dry_run_variant']}`",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion applied: `{report['promotion_applied']}`",
        "",
        "## Summary",
        "",
        "| Path | Average | Median | Best | Worst | Package Quality | Endboard | Brick Penalty | Interaction | Generic Fill | Legality | Fallback |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in (("generic", "Generic"), ("public_overlay", "Public Overlay"), ("h_variant", "H Variant")):
        row = report[key]
        lines.append(
            f"| {label} | {row['average_score']} | {row['median_score']} | {row['best_score']} | {row['worst_score']} | "
            f"{row['average_package_quality']} | {row['average_endboard_score']} | {row['average_brick_penalty']} | "
            f"{row['interaction_count']} | {row['generic_fill_count']} | {row['legality_rate']} | {row['fallback_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Deltas",
            "",
            f"- Delta vs generic: `{report['h_variant']['delta_vs_generic']}`",
            f"- Delta vs public overlay: `{report['h_variant']['delta_vs_public_overlay']}`",
            f"- Positive / negative / neutral vs generic: `{report['positive_run_count']}` / `{report['negative_run_count']}` / `{report['neutral_run_count']}`",
            f"- Safety metrics: `{report['safety_metrics']}`",
            f"- Promotion-blocking reasons: `{report['promotion_blocking_reasons']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run explicit dry-run gate for Kashtira H adapter variant.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_h_dry_run_gate(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira H Variant Dry-Run Gate Complete")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Public overlay average score: {report['public_overlay']['average_score']}")
    print(f"H variant average score: {report['h_variant']['average_score']}")
    print(f"Delta vs generic: {report['h_variant']['delta_vs_generic']}")
    print(f"Delta vs public overlay: {report['h_variant']['delta_vs_public_overlay']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
