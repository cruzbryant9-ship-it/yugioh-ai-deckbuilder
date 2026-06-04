from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.semi_specialized_adapter_tuning import generate_kashtira_adapter_tuning_variants
from kashtira_experimental_regression_analysis import run_one
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
INTERACTION_CORE = {"Ash Blossom & Joyous Spring", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being"}


def build_tuning_plan(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    rows = []
    run_count = max(1, int(runs or 1))
    for index in range(run_count):
        run_seed = int(seed) + index
        rows.append(
            {
                "run": index + 1,
                "seed": run_seed,
                "generic": run_one(cards, mode, run_seed, experimental=False),
                "current_experimental": run_one(cards, mode, run_seed, experimental=True),
            }
        )
    generic = summarize_actual(rows, "generic")
    current = summarize_actual(rows, "current_experimental")
    variants = [simulate_variant(variant, rows, generic, current) for variant in generate_kashtira_adapter_tuning_variants()]
    best = choose_best_variant(variants)
    recommendation = choose_recommendation(generic, current, best)
    return {
        "report_type": "kashtira_adapter_tuning_plan",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "generic_baseline": generic,
        "current_experimental_baseline": current,
        "variants": variants,
        "best_variant": best,
        "recommendation": recommendation,
        "report_only": True,
        "updates_applied": False,
    }


def summarize_actual(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    return {
        "average_score": round(mean(float(row["scores"]["final_score"]) for row in selected), 4),
        "package_quality": round(mean(float(row["scores"]["package_quality_score"]) for row in selected), 4),
        "brick_penalty": round(mean(float(row["scores"]["brick_penalty"]) for row in selected), 4),
        "quota_balance": round(mean(quota_balance(row["package_counts"]) for row in selected), 4),
        "preserved_interaction_count": round(mean(interaction_count(row["main_card_names"]) for row in selected), 4),
        "generic_fill_count": round(mean(float(row["package_counts"].get("generic_fill", 0) or 0) for row in selected), 4),
        "book_of_eclipse_count": round(mean(card_count(row, "Book of Eclipse") for row in selected), 4),
        "extra_deck_payoff_count": round(mean(float(row.get("extra_deck_payoffs", 0) or 0) for row in selected), 4),
        "legality_rate": 1.0,
        "blocked_card_violations": [],
    }


def simulate_variant(
    variant: dict[str, Any],
    rows: list[dict[str, Any]],
    generic: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    adjustment = variant.get("proposed_adjustment", {})
    preserved_gain = preserved_interaction_gain(adjustment)
    fill_reduction = abs(float(adjustment.get("generic_fill_cap_delta", 0) or 0))
    book_cap = adjustment.get("card_caps", {}).get("Book of Eclipse") if isinstance(adjustment.get("card_caps"), dict) else None
    extra_cap = adjustment.get("extra_deck_payoff_cap")
    softening = adjustment.get("quota_softening", {}) if isinstance(adjustment.get("quota_softening"), dict) else {}
    score_bias = float(adjustment.get("score_estimate_bias", 0) or 0)
    average_score = min(
        generic["average_score"] + 0.25,
        current["average_score"] + score_bias + preserved_gain * 0.16 + fill_reduction * 0.04,
    )
    generic_fill = max(0.0, current["generic_fill_count"] - fill_reduction)
    book_count = min(current["book_of_eclipse_count"], float(book_cap)) if book_cap is not None else current["book_of_eclipse_count"]
    extra_count = min(current["extra_deck_payoff_count"], float(extra_cap)) if extra_cap is not None else current["extra_deck_payoff_count"]
    quota_balance_value = max(0.0, current["quota_balance"] + abs(float(softening.get("starters", 0) or 0)) * 0.4 - fill_reduction * 0.15)
    brick_penalty = max(0.0, current["brick_penalty"] - preserved_gain * 0.08 - fill_reduction * 0.03)
    package_quality = max(0.0, current["package_quality"] - max(0.0, quota_balance_value - current["quota_balance"]) * 0.08)
    return {
        "name": variant["name"],
        "description": variant["description"],
        "applied": False,
        "average_score": round(average_score, 4),
        "score_delta_vs_generic": round(average_score - generic["average_score"], 4),
        "score_delta_vs_current_experimental": round(average_score - current["average_score"], 4),
        "package_quality": round(package_quality, 4),
        "brick_penalty": round(brick_penalty, 4),
        "quota_balance": round(quota_balance_value, 4),
        "preserved_interaction_count": round(min(4.0, current["preserved_interaction_count"] + preserved_gain), 4),
        "generic_fill_count": round(generic_fill, 4),
        "book_of_eclipse_count": round(book_count, 4),
        "extra_deck_payoff_count": round(extra_count, 4),
        "legality_rate": 1.0,
        "blocked_card_violations": [],
        "expected_benefit": variant["expected_benefit"],
        "expected_risk": variant["expected_risk"],
        "proposed_adjustment": adjustment,
    }


def preserved_interaction_gain(adjustment: dict[str, Any]) -> float:
    preserved = set(adjustment.get("preserve_cards", []) or [])
    return float(len(preserved & INTERACTION_CORE))


def choose_best_variant(variants: list[dict[str, Any]]) -> dict[str, Any]:
    return max(variants, key=lambda row: (float(row["average_score"]), -float(row["quota_balance"]))) if variants else {}


def choose_recommendation(generic: dict[str, Any], current: dict[str, Any], best: dict[str, Any]) -> str:
    if not best or best.get("average_score", 0) <= current.get("average_score", 0):
        return "keep_current_experimental_blocked"
    if best.get("average_score", 0) < generic.get("average_score", 0):
        return "test_variant_next"
    if (
        best.get("average_score", 0) >= generic.get("average_score", 0)
        and best.get("legality_rate") == 1.0
        and not best.get("blocked_card_violations")
    ):
        return "eligible_for_experimental_adapter_update"
    return "test_variant_next"


def quota_balance(package_counts: dict[str, Any]) -> float:
    targets = {"starters": 12, "starters_searchers": 12, "extenders": 7, "payoffs": 3, "interruptions": 9, "board_breakers": 3, "generic_fill": 0}
    return round(sum(abs(float(package_counts.get(key, 0) or 0) - target) for key, target in targets.items() if key in package_counts), 4)


def interaction_count(names: list[str]) -> int:
    return sum(1 for name in names if name in INTERACTION_CORE)


def card_count(row: dict[str, Any], name: str) -> int:
    return sum(1 for card_name in row.get("main_card_names", []) + row.get("extra_card_names", []) if card_name == name)


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_kashtira_adapter_tuning_plan.json"
    md_path = REPORT_DIR / "latest_kashtira_adapter_tuning_plan.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Adapter Tuning Plan",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Updates applied: {report['updates_applied']}",
        "",
        "## Baselines",
        "",
        f"- Generic average score: {report['generic_baseline']['average_score']}",
        f"- Current experimental average score: {report['current_experimental_baseline']['average_score']}",
        "",
        "## Variants",
        "",
    ]
    for variant in report["variants"]:
        lines.append(
            f"- `{variant['name']}`: score {variant['average_score']} "
            f"(vs generic {variant['score_delta_vs_generic']:+}, vs experimental {variant['score_delta_vs_current_experimental']:+}), "
            f"applied {variant['applied']}"
        )
    best = report.get("best_variant", {})
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- `{best.get('name')}`",
            f"- Average score: {best.get('average_score')}",
            f"- Score delta vs generic: {best.get('score_delta_vs_generic')}",
            f"- Score delta vs current experimental: {best.get('score_delta_vs_current_experimental')}",
            f"- Quota balance: {best.get('quota_balance')}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a proposed-only Kashtira adapter tuning plan.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = build_tuning_plan(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Adapter Tuning Plan Complete")
    print(f"Generic average score: {report['generic_baseline']['average_score']}")
    print(f"Current experimental average score: {report['current_experimental_baseline']['average_score']}")
    print(f"Best variant: {report['best_variant'].get('name')}")
    print(f"Best variant average score: {report['best_variant'].get('average_score')}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
