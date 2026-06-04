from __future__ import annotations

import argparse
import copy
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import split_deck
from deck.semi_specialized_quota_replay import count_extra_deck_payoffs
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
COMPONENTS = (
    "final_score",
    "consistency_score",
    "starter_score",
    "extender_score",
    "interruption_score",
    "brick_penalty",
    "endboard_score",
    "package_quality_score",
)
PACKAGE_KEYS = (
    "starters_searchers",
    "starters",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "bricks_garnets",
    "garnet_brick",
    "generic_fill",
    "extra_deck_payoffs",
)


def run_regression_analysis(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    rows = []
    for index in range(max(1, int(runs or 1))):
        run_seed = int(seed) + index
        generic = run_one(cards, mode, run_seed, experimental=False)
        experimental = run_one(cards, mode, run_seed, experimental=True)
        rows.append({"run": index + 1, "seed": run_seed, "generic": generic, "experimental": experimental})
    component_deltas = average_component_deltas(rows)
    card_diff = card_level_diff(rows)
    package_diff = package_level_diff(rows)
    root_causes = likely_root_causes(component_deltas, card_diff, package_diff)
    recommendation = choose_recommendation(component_deltas, root_causes)
    return {
        "report_type": "kashtira_experimental_regression_analysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": max(1, int(runs or 1)),
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "generic_average_score": round(mean(row["generic"]["scores"]["final_score"] for row in rows), 4),
        "experimental_average_score": round(mean(row["experimental"]["scores"]["final_score"] for row in rows), 4),
        "score_delta": round(mean(row["experimental"]["scores"]["final_score"] - row["generic"]["scores"]["final_score"] for row in rows), 4),
        "component_deltas": component_deltas,
        "largest_negative_components": largest_components(component_deltas, negative=True),
        "largest_positive_components": largest_components(component_deltas, negative=False),
        "card_level_differences": card_diff,
        "package_level_differences": package_diff,
        "likely_root_causes": root_causes,
        "safe_adjustment_candidates": safe_adjustments(root_causes, card_diff, package_diff),
        "unsafe_adjustment_candidates": unsafe_adjustments(root_causes),
        "recommendation": recommendation,
        "report_only": True,
        "run_results": rows,
    }


def run_one(cards: list[dict[str, Any]], mode: str, seed: int, experimental: bool) -> dict[str, Any]:
    random.seed(seed)
    deck, _pool = build_deck(
        copy.deepcopy(cards),
        "Kashtira",
        mode=mode,
        experimental_semi_specialized=experimental,
        specialization_profile="Kashtira" if experimental else None,
    )
    report = get_last_build_report()
    scores = score_deck_breakdown(deck, "Kashtira", mode)
    main, extra = split_deck(deck)
    package_counts = dict(report.get("package_counts", {}) or {})
    package_counts["extra_deck_payoffs"] = count_extra_deck_payoffs(deck, "Kashtira")
    return {
        "builder_used": report.get("builder_used"),
        "generic_confidence_score": report.get("generic_confidence_score"),
        "repair_actions": report.get("repair_action_count", 0) or 0,
        "filler_dependency": report.get("safe_filler_used_count", 0) or 0,
        "side_candidates": report.get("side_candidates", []) or [],
        "scores": {key: float(scores.get(key, 0) or 0) for key in COMPONENTS},
        "package_counts": package_counts,
        "main_card_names": [str(card.get("name", "")) for card in main],
        "extra_card_names": [str(card.get("name", "")) for card in extra],
        "extra_deck_payoffs": package_counts["extra_deck_payoffs"],
    }


def average_component_deltas(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        key: round(mean(row["experimental"]["scores"].get(key, 0) - row["generic"]["scores"].get(key, 0) for row in rows), 4)
        for key in COMPONENTS
    }


def card_level_diff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    added = Counter()
    removed = Counter()
    score_loss = defaultdict(list)
    score_gain = defaultdict(list)
    for row in rows:
        generic = Counter(row["generic"]["main_card_names"] + row["generic"]["extra_card_names"])
        experimental = Counter(row["experimental"]["main_card_names"] + row["experimental"]["extra_card_names"])
        delta_score = row["experimental"]["scores"]["final_score"] - row["generic"]["scores"]["final_score"]
        for name in sorted(set(generic) | set(experimental)):
            delta = experimental[name] - generic[name]
            if delta > 0:
                added[name] += delta
                (score_loss if delta_score < 0 else score_gain)[name].append(delta_score)
            elif delta < 0:
                removed[name] += abs(delta)
    return {
        "cards_added_more_often_by_experimental": top_counter(added),
        "cards_removed_more_often_by_experimental": top_counter(removed),
        "cards_associated_with_score_loss": score_assoc(score_loss),
        "cards_associated_with_score_gain": score_assoc(score_gain),
        "role_category_affected": infer_affected_roles(added, removed),
    }


def package_level_diff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    generic_avg = average_packages(row["generic"]["package_counts"] for row in rows)
    experimental_avg = average_packages(row["experimental"]["package_counts"] for row in rows)
    deltas = {
        key: round(experimental_avg.get(key, 0) - generic_avg.get(key, 0), 4)
        for key in sorted(set(PACKAGE_KEYS) | set(generic_avg) | set(experimental_avg))
    }
    return {
        "generic_average_package_counts": generic_avg,
        "experimental_average_package_counts": experimental_avg,
        "package_count_deltas": deltas,
        "over_correcting_from_starters_extenders": deltas.get("starters_searchers", 0) < -2 or deltas.get("extenders", 0) < -2,
        "underselecting_score_positive_cards": True if deltas.get("generic_fill", 0) > 5 else False,
    }


def average_packages(values: Any) -> dict[str, float]:
    rows = list(values)
    totals = Counter()
    for row in rows:
        for key, value in (row or {}).items():
            totals[str(key)] += float(value or 0)
    return {key: round(total / max(1, len(rows)), 4) for key, total in sorted(totals.items())}


def largest_components(deltas: dict[str, float], negative: bool) -> list[dict[str, Any]]:
    rows = [
        {"component": key, "delta": value}
        for key, value in deltas.items()
        if (value < 0 if negative else value > 0)
    ]
    return sorted(rows, key=lambda row: abs(float(row["delta"])), reverse=True)[:5]


def likely_root_causes(component_deltas: dict[str, float], card_diff: dict[str, Any], package_diff: dict[str, Any]) -> list[str]:
    causes = []
    if component_deltas.get("final_score", 0) < 0 and component_deltas.get("package_quality_score", 0) > 0:
        causes.append("quota/package quality improves, but scoring components regress")
    if component_deltas.get("brick_penalty", 0) > 0:
        causes.append("experimental path increases brick penalty")
    if component_deltas.get("endboard_score", 0) < 0:
        causes.append("experimental path lowers endboard score")
    if component_deltas.get("consistency_score", 0) < 0:
        causes.append("experimental path lowers consistency")
    if package_diff.get("underselecting_score_positive_cards"):
        causes.append("experimental path relies on generic fill after quota picks, suggesting adapter selection needs tuning")
    if card_diff.get("cards_removed_more_often_by_experimental"):
        causes.append("experimental path repeatedly removes generic-selected cards associated with higher score")
    return causes or ["regression is present but not isolated by current component signals"]


def safe_adjustments(causes: list[str], card_diff: dict[str, Any], package_diff: dict[str, Any]) -> list[str]:
    candidates = []
    if package_diff.get("underselecting_score_positive_cards"):
        candidates.append("adjust_adapter_selection")
    if any("brick penalty" in cause for cause in causes):
        candidates.append("adjust_profile_targets")
    if any("endboard" in cause for cause in causes):
        candidates.append("adjust_adapter_selection")
    if not candidates:
        candidates.append("retest_needed")
    return sorted(set(candidates))


def unsafe_adjustments(causes: list[str]) -> list[str]:
    return ["change_scoring_weights", "promote_experimental_default", "change_generic_builder_behavior"]


def choose_recommendation(component_deltas: dict[str, float], causes: list[str]) -> str:
    if component_deltas.get("final_score", 0) < 0:
        if any("adapter" in cause for cause in causes):
            return "adjust_adapter_selection"
        if any("brick" in cause for cause in causes):
            return "adjust_profile_targets"
        return "keep_blocked"
    return "retest_needed"


def top_counter(counter: Counter[str], limit: int = 12) -> list[dict[str, Any]]:
    return [{"card": name, "count_delta": count, "role_category": role_category(name)} for name, count in counter.most_common(limit)]


def score_assoc(values: dict[str, list[float]], limit: int = 12) -> list[dict[str, Any]]:
    rows = [
        {"card": name, "average_score_delta_when_changed": round(mean(deltas), 4), "observations": len(deltas), "role_category": role_category(name)}
        for name, deltas in values.items()
    ]
    return sorted(rows, key=lambda row: abs(float(row["average_score_delta_when_changed"])), reverse=True)[:limit]


def infer_affected_roles(added: Counter[str], removed: Counter[str]) -> list[str]:
    roles = Counter()
    for name, count in added.items():
        roles[role_category(name)] += count
    for name, count in removed.items():
        roles[role_category(name)] += count
    return [role for role, _count in roles.most_common()]


def role_category(name: str) -> str:
    lowered = name.casefold()
    if any(term in lowered for term in ("fenrir", "unicorn", "planet", "theosis")):
        return "starters_searchers"
    if any(term in lowered for term in ("birth", "riseheart", "scareclaw", "tearlaments")):
        return "extenders"
    if any(term in lowered for term in ("arise-heart", "shangri-ira", "zeus", "big eye")):
        return "extra_deck_payoffs"
    if any(term in lowered for term in ("book of eclipse", "evenly", "dark ruler", "lightning storm")):
        return "board_breakers"
    if any(term in lowered for term in ("preparations", "big bang")):
        return "interruptions"
    if any(term in lowered for term in ("ogre", "overlap", "akstra")):
        return "bricks_garnets"
    return "other"


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_kashtira_regression_analysis.json"
    md_path = REPORT_DIR / "latest_kashtira_regression_analysis.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Experimental Regression Analysis",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Score delta: {report['score_delta']}",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Largest Negative Components",
        "",
    ]
    lines.extend(f"- `{row['component']}`: {row['delta']}" for row in report["largest_negative_components"]) or lines.append("- None")
    lines.extend(["", "## Largest Positive Components", ""])
    lines.extend(f"- `{row['component']}`: {row['delta']}" for row in report["largest_positive_components"]) or lines.append("- None")
    lines.extend(["", "## Card-Level Differences", ""])
    for row in report["card_level_differences"]["cards_added_more_often_by_experimental"][:8]:
        lines.append(f"- Added `{row['card']}`: +{row['count_delta']} ({row['role_category']})")
    for row in report["card_level_differences"]["cards_removed_more_often_by_experimental"][:8]:
        lines.append(f"- Removed `{row['card']}`: -{row['count_delta']} ({row['role_category']})")
    lines.extend(["", "## Package-Level Differences", ""])
    for key, value in report["package_level_differences"]["package_count_deltas"].items():
        if value:
            lines.append(f"- `{key}`: {value:+}")
    lines.extend(["", "## Likely Root Causes", ""])
    lines.extend(f"- {cause}" for cause in report["likely_root_causes"])
    lines.extend(["", "## Safe Adjustment Candidates", ""])
    lines.extend(f"- `{candidate}`" for candidate in report["safe_adjustment_candidates"])
    lines.extend(["", "## Unsafe Adjustment Candidates", ""])
    lines.extend(f"- `{candidate}`" for candidate in report["unsafe_adjustment_candidates"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze fixed-seed Kashtira experimental regression root causes.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_regression_analysis(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Experimental Regression Analysis Complete")
    print(f"Generic average score: {report['generic_average_score']}")
    print(f"Experimental average score: {report['experimental_average_score']}")
    print(f"Score delta: {report['score_delta']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
