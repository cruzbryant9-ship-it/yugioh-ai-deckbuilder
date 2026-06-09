from __future__ import annotations

import argparse
import copy
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import quota_balance
from kashtira_public_overlay_large_sample import VARIANT as PUBLIC_OVERLAY_VARIANT
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_targeted_swap_sensitivity.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_targeted_swap_sensitivity.md"
COMPONENTS = ("package_quality_score", "endboard_score", "brick_penalty", "final_score")
SWAP_VARIANTS: dict[str, dict[str, str]] = {
    "A_book_over_akstra": {"add": "Book of Eclipse", "remove": "Kashtira Akstra", "label": "Add Book of Eclipse / remove Kashtira Akstra"},
    "B_book_over_overlap": {"add": "Book of Eclipse", "remove": "Kashtira Overlap", "label": "Add Book of Eclipse / remove Kashtira Overlap"},
    "C_book_over_tearlaments": {"add": "Book of Eclipse", "remove": "Tearlaments Kashtira", "label": "Add Book of Eclipse / remove Tearlaments Kashtira"},
    "D_preparations_over_akstra": {"add": "Kashtira Preparations", "remove": "Kashtira Akstra", "label": "Add Kashtira Preparations / remove Kashtira Akstra"},
    "E_preparations_over_overlap": {"add": "Kashtira Preparations", "remove": "Kashtira Overlap", "label": "Add Kashtira Preparations / remove Kashtira Overlap"},
    "F_preparations_over_tearlaments": {"add": "Kashtira Preparations", "remove": "Tearlaments Kashtira", "label": "Add Kashtira Preparations / remove Tearlaments Kashtira"},
    "G_restore_akstra_reduce_book": {"add": "Kashtira Akstra", "remove": "Book of Eclipse", "label": "Keep Book package but restore one Kashtira Akstra"},
    "H_restore_overlap_reduce_preparations": {"add": "Kashtira Overlap", "remove": "Kashtira Preparations", "label": "Keep Preparations package but restore one Kashtira Overlap"},
    "I_reduce_book_restore_tearlaments": {"add": "Tearlaments Kashtira", "remove": "Book of Eclipse", "label": "Reduce Book of Eclipse count"},
    "J_reduce_preparations_restore_tearlaments": {"add": "Tearlaments Kashtira", "remove": "Kashtira Preparations", "label": "Reduce Kashtira Preparations count"},
}


def run_swap_sensitivity(mode: str = "meta", runs: int = 30, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    run_count = max(1, int(runs or 1))
    rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        generic = build_path(cards, mode, run_seed, experimental=False)
        public_overlay = build_path(cards, mode, run_seed, experimental=True)
        adjustments = {
            name: evaluate_adjustment(public_overlay, lookup, mode, name, spec)
            for name, spec in SWAP_VARIANTS.items()
        }
        rows.append({"run": index + 1, "seed": run_seed, "generic": generic, "public_overlay": public_overlay, "adjustments": adjustments})

    attach_comparisons(rows)
    generic_summary = summarize_path([row["generic"] for row in rows])
    overlay_summary = summarize_path([row["public_overlay"] for row in rows])
    adjustment_summaries = {name: summarize_path([row["adjustments"][name] for row in rows]) for name in SWAP_VARIANTS}
    for name, summary in adjustment_summaries.items():
        summary["score_delta_vs_generic"] = round(summary["average_score"] - generic_summary["average_score"], 4)
        summary["score_delta_vs_public_overlay"] = round(summary["average_score"] - overlay_summary["average_score"], 4)
        summary["package_quality_delta_vs_public_overlay"] = round(summary["average_package_quality"] - overlay_summary["average_package_quality"], 4)
        summary["endboard_delta_vs_public_overlay"] = round(summary["average_endboard_score"] - overlay_summary["average_endboard_score"], 4)
        summary["brick_penalty_delta_vs_public_overlay"] = round(summary["average_brick_penalty"] - overlay_summary["average_brick_penalty"], 4)
        summary["classification"] = classify_adjustment(summary)

    best_adjustment = choose_best_adjustment(adjustment_summaries)
    recommendation = choose_recommendation(adjustment_summaries, best_adjustment)
    return {
        "report_type": "kashtira_targeted_swap_sensitivity",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "public_overlay_variant": PUBLIC_OVERLAY_VARIANT,
        "swap_variants": {name: dict(spec) for name, spec in SWAP_VARIANTS.items()},
        "generic_baseline": generic_summary,
        "public_overlay_baseline": overlay_summary,
        "adjustment_summaries": adjustment_summaries,
        "best_adjustment": best_adjustment,
        "harmful_adjustments": [name for name, summary in adjustment_summaries.items() if summary["classification"] == "harmful"],
        "recommendation": recommendation,
        "promotion_applied": False,
        "run_results": rows,
    }


def build_path(cards: list[dict[str, Any]], mode: str, seed: int, experimental: bool) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if experimental:
        kwargs = {
            "experimental_semi_specialized": True,
            "specialization_profile": "Kashtira",
            "experimental_variant": PUBLIC_OVERLAY_VARIANT,
        }
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    return deck_metrics(deck, report, mode, proposed_only=False)


def evaluate_adjustment(base: dict[str, Any], lookup: dict[str, dict[str, Any]], mode: str, name: str, spec: dict[str, str]) -> dict[str, Any]:
    deck = copy.deepcopy(base["deck"])
    adjusted, status = apply_swap(deck, lookup, spec["add"], spec["remove"])
    metrics = deck_metrics(adjusted, base.get("report", {}), mode, proposed_only=True)
    metrics.update(
        {
            "adjustment": name,
            "adjustment_label": spec["label"],
            "add_card": spec["add"],
            "remove_card": spec["remove"],
            "adjustment_status": status,
        }
    )
    return metrics


def apply_swap(deck: list[dict[str, Any]], lookup: dict[str, dict[str, Any]], add_name: str, remove_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    main, extra = split_deck(deck)
    status = {"applied": False, "add_card": add_name, "remove_card": remove_name, "reason": None}
    remove_index = next((index for index, card in enumerate(main) if str(card.get("name", "")) == remove_name), None)
    add_card = lookup.get(add_name)
    if remove_index is None:
        status["reason"] = f"remove card absent: {remove_name}"
        return deck, status
    if not add_card:
        status["reason"] = f"add card unavailable: {add_name}"
        return deck, status
    counts = Counter(str(card.get("name", "")) for card in main)
    counts[remove_name] -= 1
    if counts[add_name] >= get_card_limit(add_card):
        status["reason"] = f"copy limit prevents adding: {add_name}"
        return deck, status
    main[remove_index] = add_card
    status["applied"] = True
    status["reason"] = "applied"
    return main + extra, status


def deck_metrics(deck: list[dict[str, Any]], report: dict[str, Any], mode: str, proposed_only: bool) -> dict[str, Any]:
    score = score_deck_breakdown(deck, "Kashtira", mode)
    main, extra = split_deck(deck)
    package_counts = dict(report.get("package_counts", {}) or {})
    blocked = blocked_card_violations(deck)
    interaction_count = sum(1 for card in main if str(card.get("name", "")) in interaction_core_for("Kashtira"))
    generic_fill_count = float(package_counts.get("generic_fill", 0) or 0)
    return {
        "deck": deck,
        "report": copy.deepcopy(report),
        "main_names": [str(card.get("name", "")) for card in main],
        "extra_names": [str(card.get("name", "")) for card in extra],
        "score": float(score.get("final_score", 0) or 0),
        "package_quality": float(score.get("package_quality_score", 0) or 0),
        "endboard_score": float(score.get("endboard_score", 0) or 0),
        "brick_penalty": float(score.get("brick_penalty", 0) or 0),
        "quota_balance": quota_balance(package_counts),
        "interaction_count": float(interaction_count),
        "generic_fill_count": generic_fill_count,
        "legality_ok": len(main) >= 40 and len(extra) <= 15 and not blocked,
        "fallback_used": bool(report.get("fallback_used", False)) if not proposed_only else False,
        "blocked_card_violations": blocked,
        "proposed_only": proposed_only,
    }


def summarize_path(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row["score"]) for row in rows]
    overlay_scores = [float(row.get("public_overlay_score", row["score"])) for row in rows]
    return {
        "average_score": round(mean(scores), 4),
        "median_score": round(median(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "positive_run_count": sum(1 for row in rows if row["score"] > row.get("comparison_score", row["score"])),
        "negative_run_count": sum(1 for row in rows if row["score"] < row.get("comparison_score", row["score"])),
        "neutral_run_count": sum(1 for row in rows if row["score"] == row.get("comparison_score", row["score"])),
        "average_package_quality": round(mean(float(row["package_quality"]) for row in rows), 4),
        "average_endboard_score": round(mean(float(row["endboard_score"]) for row in rows), 4),
        "average_brick_penalty": round(mean(float(row["brick_penalty"]) for row in rows), 4),
        "quota_balance": round(mean(float(row["quota_balance"]) for row in rows), 4),
        "interaction_count": round(mean(float(row["interaction_count"]) for row in rows), 4),
        "generic_fill_count": round(mean(float(row["generic_fill_count"]) for row in rows), 4),
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in rows), 4),
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in rows), 4),
        "blocked_card_violations": sorted(set(name for row in rows for name in row["blocked_card_violations"])),
        "applied_rate": round(mean(1.0 if row.get("adjustment_status", {}).get("applied", True) else 0.0 for row in rows), 4),
        "adjustment_failures": sorted(set(row.get("adjustment_status", {}).get("reason") for row in rows if row.get("adjustment_status", {}).get("applied") is False)),
    }


def attach_comparisons(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        generic_score = row["generic"]["score"]
        overlay_score = row["public_overlay"]["score"]
        row["generic"]["comparison_score"] = generic_score
        row["public_overlay"]["comparison_score"] = generic_score
        for adjustment in row["adjustments"].values():
            adjustment["comparison_score"] = generic_score
            adjustment["public_overlay_score"] = overlay_score


def classify_adjustment(summary: dict[str, Any]) -> str:
    if summary.get("applied_rate", 1.0) < 1.0:
        return "inconclusive"
    if summary["legality_rate"] < 1.0 or summary["fallback_rate"] > 0.0 or summary["blocked_card_violations"]:
        return "harmful"
    delta = float(summary.get("score_delta_vs_public_overlay", 0) or 0)
    if delta >= 0.25:
        return "helpful"
    if delta <= -0.25:
        return "harmful"
    if abs(delta) <= 0.05:
        return "neutral"
    return "inconclusive"


def choose_best_adjustment(summaries: dict[str, dict[str, Any]]) -> str:
    return max(
        summaries,
        key=lambda name: (
            summaries[name]["classification"] == "helpful",
            summaries[name]["score_delta_vs_public_overlay"],
            summaries[name]["average_score"],
        ),
    )


def choose_recommendation(summaries: dict[str, dict[str, Any]], best: str) -> str:
    if all(summary["classification"] == "harmful" for summary in summaries.values()):
        return "abandon_public_overlay"
    best_summary = summaries[best]
    if best_summary["classification"] == "helpful" and best_summary["score_delta_vs_public_overlay"] >= 0.25:
        return "test_adjusted_variant_next"
    if not any(summary["score_delta_vs_public_overlay"] > 0 for summary in summaries.values()):
        return "keep_current_public_overlay"
    return "needs_more_data"


def finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    attach_comparisons(report["run_results"])
    return report


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, scrub_decks(report))
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def scrub_decks(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: scrub_decks(item) for key, item in value.items() if key not in {"deck", "report"}}
    if isinstance(value, list):
        return [scrub_decks(item) for item in value]
    return value


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Targeted Swap Sensitivity",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: `{report['runs']}`",
        f"- Seed: `{report['seed']}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- Best adjustment: `{report['best_adjustment']}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Adjustment Summary",
        "",
        "| Adjustment | Classification | Avg Score | vs Generic | vs Public Overlay | Interaction | Generic Fill | Legality |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in report["adjustment_summaries"].items():
        lines.append(
            f"| {name} | {summary['classification']} | {summary['average_score']} | "
            f"{summary['score_delta_vs_generic']} | {summary['score_delta_vs_public_overlay']} | "
            f"{summary['interaction_count']} | {summary['generic_fill_count']} | {summary['legality_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Harmful Adjustments",
            "",
            f"- `{report['harmful_adjustments']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run proposed-only Kashtira targeted swap sensitivity.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_swap_sensitivity(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Targeted Swap Sensitivity Complete")
    print(f"Best adjustment: {report['best_adjustment']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
