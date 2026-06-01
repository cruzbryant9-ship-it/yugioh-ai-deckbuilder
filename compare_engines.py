from __future__ import annotations

import argparse
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.builder import detect_card_engines, is_extra_deck_card, score_deck_breakdown
from deck.deck_analysis import critique_deck
from deck.deck_utils import split_deck
from deck.engine_variants import ENGINE_VARIANTS, VARIANT_ENGINE_MAP
from deck.hand_simulator import real_combo_report
from deck.package_builder import build_package_deck, summarize_package_metrics
from deck.package_quality import score_package_quality
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.side_deck_planner import build_side_deck
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.report_schema import normalize_report

ENGINE_COMPARISONS_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "engine_comparisons"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Directly compare engine variants for an archetype.")
    parser.add_argument("--archetype", required=True, help='Archetype to test, for example "Blue-Eyes".')
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--runs-per-engine", type=int, default=20)
    parser.add_argument("--matchup", choices=list_matchup_names(), default="unknown_meta")
    parser.add_argument("--going", choices=("first", "second", "both"), default="both")
    return parser.parse_args()


def archetype_cards(cards: list[dict[str, Any]], archetype: str) -> list[dict[str, Any]]:
    return [
        card
        for card in cards
        if card.get("archetype") and archetype.lower() in str(card.get("archetype", "")).lower()
    ]


def engine_cards(cards: list[dict[str, Any]], engine: str) -> list[dict[str, Any]]:
    return [card for card in cards if engine in detect_card_engines(card)]


def candidate_pool(cards: list[dict[str, Any]], archetype: str, variant: str) -> list[dict[str, Any]]:
    base = archetype_cards(cards, archetype)
    if variant == "pure":
        return [
            card
            for card in base
            if not (detect_card_engines(card) - {"Blue-Eyes core"})
        ]

    engine = VARIANT_ENGINE_MAP[variant]
    by_name = {card["name"]: card for card in base if card.get("name")}
    for card in engine_cards(cards, engine):
        if card.get("name"):
            by_name[card["name"]] = card
    return list(by_name.values())


def card_weight_for_variant(card: dict[str, Any], variant: str) -> float:
    engines = detect_card_engines(card)
    if variant == "pure":
        return 1.2 if engines == {"Blue-Eyes core"} else 0.75

    target_engine = VARIANT_ENGINE_MAP[variant]
    weight = 1.0
    if target_engine in engines:
        weight += 0.75
    if "Blue-Eyes core" in engines:
        weight += 0.15
    return weight


def build_variant_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    variant: str,
    size: int = 40,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pool = candidate_pool(cards, archetype, variant)
    legal_pool = [card for card in pool if get_card_limit(card) > 0]
    if not legal_pool:
        return [], pool

    weights = [card_weight_for_variant(card, variant) for card in legal_pool]
    deck: list[dict[str, Any]] = []
    card_counts: Counter[str] = Counter()
    attempts = 0
    max_attempts = size * 150

    while len(deck) < size and attempts < max_attempts:
        attempts += 1
        card = random.choices(legal_pool, weights=weights, k=1)[0]
        name = str(card.get("name", ""))
        if card_counts[name] < get_card_limit(card):
            deck.append(card)
            card_counts[name] += 1

    return deck, pool


def run_variant(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    variant: str,
    runs: int,
    matchup: str = "unknown_meta",
    going: str = "both",
) -> dict[str, Any]:
    run_results = []
    for run_number in range(1, runs + 1):
        try:
            deck, package_report = build_package_deck(
                cards,
                archetype,
                mode=mode,
                engine_variant=variant,
            )
            pool = candidate_pool(cards, archetype, variant)
            if len(deck) < 40:
                deck, pool = build_variant_deck(cards, archetype, variant)
                package_report = summarize_package_metrics(deck, variant)
            main_deck, extra_deck = split_deck(deck)
            breakdown = score_deck_breakdown(deck, archetype, mode)
            gameplay_report = real_combo_report(deck, archetype, samples=100)
            package_quality = score_package_quality(deck, package_report, breakdown)
            side_report = build_side_deck(deck, archetype, get_matchup_profile(matchup), cards, going=going)
            run_results.append(
                {
                    "run": run_number,
                    "ok": True,
                    "variant": variant,
                    "final_score": breakdown["final_score"],
                    "score_breakdown": breakdown,
                    "candidate_pool_size": len(pool),
                    "main_deck": [card["name"] for card in main_deck],
                    "extra_deck": [card["name"] for card in extra_deck],
                    "detected_engines": sorted({engine for card in deck for engine in detect_card_engines(card)}),
                    "critique_issues": critique_deck(deck, archetype),
                    "real_combo_report": gameplay_report,
                    "playable_hand_rate": gameplay_report["playable_hand_rate"],
                    "brick_rate": gameplay_report["brick_rate"],
                    "combo_line_score": gameplay_report["combo_line_score"],
                    "average_endboard_score": gameplay_report["average_endboard_score"],
                    "interruption_resilience_score": gameplay_report["interruption_resilience_score"],
                    "follow_up_score": gameplay_report["follow_up_score"],
                    "package_report": package_report,
                    "package_quality": package_quality,
                    "package_quality_score": package_quality["final_package_quality_score"],
                    "side_deck_score": side_report["side_deck_score"],
                    "matchup_coverage_score": side_report["matchup_coverage_score"],
                    "going_first_side_score": side_report["going_first_side_score"],
                    "going_second_side_score": side_report["going_second_side_score"],
                    "matchup": matchup,
                    "recommended_side_cards": [card["name"] for card in side_report["side_deck"]],
                    "quota_violation_penalty": package_quality["quota_violation_penalty"],
                    "package_counts": package_report["package_counts"],
                    "package_starter_count": package_report["starter_count"],
                    "package_brick_count": package_report["brick_count"],
                    "non_engine_count": package_report["non_engine_count"],
                    "package_quota_violations": package_report["package_quota_violations"],
                }
            )
        except Exception as exc:
            run_results.append({"run": run_number, "ok": False, "variant": variant, "error": str(exc)})

    return summarize_variant(variant, run_results)


def summarize_variant(variant: str, run_results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in run_results if result.get("ok")]
    failed = [result for result in run_results if not result.get("ok")]
    if not successful:
        return {
            "variant": variant,
            "successful_runs": 0,
            "failed_runs": len(failed),
            "average_score": 0,
            "best_score": 0,
            "average_brick_penalty": 0,
            "playable_hand_rate": 0,
            "brick_rate": 0,
            "combo_line_score": 0,
            "average_endboard_score": 0,
            "average_interruption_score": 0,
            "interruption_resilience_score": 0,
            "follow_up_score": 0,
            "best_deck_list": {"main_deck": [], "extra_deck": []},
            "most_common_critique_issues": [],
            "runs": run_results,
        }

    best = max(successful, key=lambda result: result["final_score"])
    critiques = Counter(issue for result in successful for issue in result["critique_issues"])
    package_totals = Counter()
    package_violations = Counter()
    package_quality_scores = []
    side_card_counter = Counter()
    for result in successful:
        package_report = result.get("package_report", {})
        if isinstance(package_report, dict):
            package_totals.update(package_report.get("package_counts", {}))
            package_violations.update(str(item) for item in package_report.get("package_quota_violations", []))
        package_quality_scores.append(float(result.get("package_quality_score", 0) or 0))
        side_card_counter.update(str(card) for card in result.get("recommended_side_cards", []))

    return {
        "variant": variant,
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "average_score": round(mean(result["final_score"] for result in successful), 2),
        "best_score": best["final_score"],
        "average_brick_penalty": round(mean(result["score_breakdown"]["brick_penalty"] for result in successful), 2),
        "playable_hand_rate": round(mean(result.get("playable_hand_rate", 0) for result in successful), 4),
        "brick_rate": round(mean(result.get("brick_rate", 0) for result in successful), 4),
        "combo_line_score": round(mean(result.get("combo_line_score", 0) for result in successful), 2),
        "average_endboard_score": round(mean(result["score_breakdown"]["endboard_score"] for result in successful), 2),
        "average_interruption_score": round(mean(result["score_breakdown"]["interruption_score"] for result in successful), 2),
        "real_average_endboard_score": round(mean(result.get("average_endboard_score", 0) for result in successful), 2),
        "interruption_resilience_score": round(mean(result.get("interruption_resilience_score", 0) for result in successful), 2),
        "follow_up_score": round(mean(result.get("follow_up_score", 0) for result in successful), 2),
        "graph_valid_line_rate": round(mean(result.get("real_combo_report", {}).get("graph_valid_line_rate", 0) for result in successful), 4),
        "resource_valid_line_rate": round(mean(result.get("real_combo_report", {}).get("resource_valid_line_rate", 0) for result in successful), 4),
        "graph_average_line_score": round(mean(result.get("real_combo_report", {}).get("graph_average_line_score", 0) for result in successful), 2),
        "graph_average_risk_score": round(mean(result.get("real_combo_report", {}).get("graph_average_risk_score", 0) for result in successful), 2),
        "material_failure_rate": round(mean(result.get("real_combo_report", {}).get("missing_material_rate", 0) for result in successful), 4),
        "optional_line_failure_rate": round(mean(result.get("real_combo_report", {}).get("optional_line_failure_rate", 0) for result in successful), 4),
        "best_line_failure_rate": round(mean(result.get("real_combo_report", {}).get("best_line_failure_rate", 0) for result in successful), 4),
        "no_valid_line_rate": round(mean(result.get("real_combo_report", {}).get("no_valid_line_rate", 0) for result in successful), 4),
        "branch_valid_rate": round(mean(result.get("real_combo_report", {}).get("branch_valid_rate", 0) for result in successful), 4),
        "no_valid_branch_rate": round(mean(result.get("real_combo_report", {}).get("no_valid_branch_rate", 0) for result in successful), 4),
        "average_branch_score": round(mean(result.get("real_combo_report", {}).get("average_branch_score", 0) for result in successful), 2),
        "average_interruption_risk": round(mean(result.get("real_combo_report", {}).get("average_interruption_risk", 0) for result in successful), 2),
        "interrupted_line_success_rate": round(mean(result.get("real_combo_report", {}).get("interrupted_line_success_rate", 0) for result in successful), 4),
        "resilience_score": round(mean(result.get("real_combo_report", {}).get("resilience_score", 0) for result in successful), 2),
        "recovery_route_rate": round(mean(result.get("real_combo_report", {}).get("recovery_route_rate", 0) for result in successful), 4),
        "ash_vulnerability_rate": round(mean(result.get("real_combo_report", {}).get("ash_vulnerability_rate", 0) for result in successful), 4),
        "imperm_vulnerability_rate": round(mean(result.get("real_combo_report", {}).get("imperm_vulnerability_rate", 0) for result in successful), 4),
        "droll_vulnerability_rate": round(mean(result.get("real_combo_report", {}).get("droll_vulnerability_rate", 0) for result in successful), 4),
        "normalized_material_failure_rate": round(mean(result.get("real_combo_report", {}).get("normalized_material_failure_rate", 0) for result in successful), 4),
        "normalized_search_failure_rate": round(mean(result.get("real_combo_report", {}).get("normalized_search_failure_rate", 0) for result in successful), 4),
        "normalized_cost_failure_rate": round(mean(result.get("real_combo_report", {}).get("normalized_cost_failure_rate", 0) for result in successful), 4),
        "cost_condition_valid_rate": round(mean(result.get("real_combo_report", {}).get("cost_condition_valid_rate", 0) for result in successful), 4),
        "condition_failure_rate_normalized": round(mean(result.get("real_combo_report", {}).get("condition_failure_rate_normalized", 0) for result in successful), 4),
        "reveal_cost_failure_rate": round(mean(result.get("real_combo_report", {}).get("reveal_cost_failure_rate", 0) for result in successful), 4),
        "discard_cost_failure_rate": round(mean(result.get("real_combo_report", {}).get("discard_cost_failure_rate", 0) for result in successful), 4),
        "history_condition_failure_rate": round(mean(result.get("real_combo_report", {}).get("history_condition_failure_rate", 0) for result in successful), 4),
        "synchro_exact_level_valid_rate": round(mean(result.get("real_combo_report", {}).get("synchro_exact_level_valid_rate", 0) for result in successful), 4),
        "ritual_level_valid_rate": round(mean(result.get("real_combo_report", {}).get("ritual_level_valid_rate", 0) for result in successful), 4),
        "typed_material_valid_rate": round(mean(result.get("real_combo_report", {}).get("typed_material_valid_rate", 0) for result in successful), 4),
        "package_quality_score": round(mean(package_quality_scores), 2) if package_quality_scores else 0,
        "side_deck_compatibility_score": round(mean(result.get("side_deck_score", 0) for result in successful), 2),
        "matchup_coverage_score": round(mean(result.get("matchup_coverage_score", 0) for result in successful), 2),
        "going_first_side_score": round(mean(result.get("going_first_side_score", 0) for result in successful), 2),
        "going_second_side_score": round(mean(result.get("going_second_side_score", 0) for result in successful), 2),
        "best_matchup_profile": str(successful[0].get("matchup", "unknown_meta")),
        "worst_matchup_profile": str(successful[0].get("matchup", "unknown_meta")),
        "recommended_side_cards": side_card_counter.most_common(15),
        "best_deck_list": {
            "main_deck": best["main_deck"],
            "extra_deck": best["extra_deck"],
        },
        "most_common_critique_issues": critiques.most_common(10),
        "package_counts": dict(sorted(package_totals.items())),
        "package_quota_violations": package_violations.most_common(10),
        "runs": run_results,
    }


def rank_variants(results: dict[str, dict[str, Any]]) -> dict[str, str]:
    successful = [summary for summary in results.values() if summary["successful_runs"]]
    if not successful:
        return {
            "best_overall_engine": "none",
            "most_consistent_engine": "none",
            "strongest_endboard_engine": "none",
            "lowest_brick_engine": "none",
            "best_recommended_engine": "none",
        }

    best_overall = max(successful, key=lambda item: item["average_score"])
    most_consistent = max(successful, key=lambda item: (item["playable_hand_rate"], -item["brick_rate"], -item["average_brick_penalty"]))
    strongest_endboard = max(successful, key=lambda item: (item["real_average_endboard_score"], item["average_endboard_score"]))
    lowest_brick = min(successful, key=lambda item: (item["brick_rate"], item["average_brick_penalty"]))
    going_first = max(successful, key=lambda item: (item["average_score"] + item["real_average_endboard_score"] * 1.2 + item["interruption_resilience_score"] * 0.8))
    going_second = max(successful, key=lambda item: (item["playable_hand_rate"] * 10 + item["average_interruption_score"] + item["combo_line_score"] - item["brick_rate"] * 8))
    recommended = max(
        successful,
        key=lambda item: (
            item["average_score"]
            + item["playable_hand_rate"] * 8
            + item["real_average_endboard_score"] * 0.8
            + item["interruption_resilience_score"] * 0.5
            + item["follow_up_score"] * 0.4
            + item["package_quality_score"] * 0.25
            + item["graph_valid_line_rate"] * 8
            + item["resource_valid_line_rate"] * 6
            + item["typed_material_valid_rate"] * 4
            + item["cost_condition_valid_rate"] * 3
            + item["branch_valid_rate"] * 2
            + item["average_branch_score"] * 0.3
            + item["interrupted_line_success_rate"] * 6
            + item["resilience_score"] * 0.8
            + item["recovery_route_rate"] * 2
            + item["side_deck_compatibility_score"] * 0.2
            + item["matchup_coverage_score"] * 0.3
            + item["synchro_exact_level_valid_rate"] * 2
            + item["ritual_level_valid_rate"] * 1
            + item["graph_average_line_score"] * 0.5
            - item["brick_rate"] * 12
            - item["graph_average_risk_score"] * 0.4
            - item["normalized_material_failure_rate"] * 4
            - item["normalized_search_failure_rate"] * 3
            - item["normalized_cost_failure_rate"] * 3
            - item["condition_failure_rate_normalized"] * 3
            - item["reveal_cost_failure_rate"] * 2
            - item["best_line_failure_rate"] * 5
            - item["no_valid_line_rate"] * 4
            - item["no_valid_branch_rate"] * 4
            - item["history_condition_failure_rate"] * 3
            - item["average_interruption_risk"] * 0.8
            - item["ash_vulnerability_rate"] * 2
            - item["imperm_vulnerability_rate"] * 1.5
            - item["droll_vulnerability_rate"] * 1.5
        ),
    )

    return {
        "best_overall_engine": best_overall["variant"],
        "most_consistent_engine": most_consistent["variant"],
        "strongest_endboard_engine": strongest_endboard["variant"],
        "lowest_brick_engine": lowest_brick["variant"],
        "best_going_first_engine": going_first["variant"],
        "best_going_second_engine": going_second["variant"],
        "best_recommended_engine": recommended["variant"],
    }


def save_report(report: dict[str, Any]) -> Path:
    ENGINE_COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype = report["config"]["archetype"].lower().replace(" ", "_")
    mode = report["config"]["mode"]
    path = ENGINE_COMPARISONS_DIR / f"{timestamp}_{archetype}_{mode}_engine_comparison.json"
    atomic_write_json(path, normalize_report("engine_comparison", report))
    return path


def print_report(report: dict[str, Any], path: Path) -> None:
    ranking = report["ranking"]
    print("\nEngine Comparison Ranking")
    print(f"Best overall engine: {ranking['best_overall_engine']}")
    print(f"Most consistent engine: {ranking['most_consistent_engine']}")
    print(f"Strongest endboard engine: {ranking['strongest_endboard_engine']}")
    print(f"Lowest brick engine: {ranking['lowest_brick_engine']}")
    print(f"Best going-first engine: {ranking['best_going_first_engine']}")
    print(f"Best going-second engine: {ranking['best_going_second_engine']}")
    print(f"Best recommended engine: {ranking['best_recommended_engine']}")

    print("\nVariant Results")
    for variant, summary in sorted(report["variants"].items(), key=lambda item: item[1]["average_score"], reverse=True):
        print(
            f"- {variant}: avg {summary['average_score']} | best {summary['best_score']} | "
            f"playable {summary['playable_hand_rate']} | brick rate {summary['brick_rate']} | "
            f"brick {summary['average_brick_penalty']} | endboard {summary['real_average_endboard_score']} | "
            f"resilience {summary['interruption_resilience_score']} | follow-up {summary['follow_up_score']} | "
            f"package quality {summary['package_quality_score']} | graph valid {summary['graph_valid_line_rate']} | "
            f"resource valid {summary['resource_valid_line_rate']} | typed valid {summary['typed_material_valid_rate']} | "
            f"cost/cond valid {summary['cost_condition_valid_rate']} | "
            f"branch valid {summary['branch_valid_rate']} | "
            f"resilience {summary['resilience_score']} | interrupted success {summary['interrupted_line_success_rate']} | "
            f"side {summary['side_deck_compatibility_score']} | coverage {summary['matchup_coverage_score']} | "
            f"no valid {summary['no_valid_line_rate']} | norm material fail {summary['normalized_material_failure_rate']} | "
            f"graph score {summary['graph_average_line_score']}"
        )
        if summary.get("package_quota_violations"):
            print(f"  package warnings: {summary['package_quota_violations']}")

    print(f"\nSaved report: {path}")


def main() -> None:
    args = parse_args()
    if args.runs_per_engine < 1:
        raise SystemExit("--runs-per-engine must be 1 or greater.")

    startup_safety_cleanup()
    database = CardDatabase()
    database.refresh_on_startup()
    cards = database.load_cards()

    variants = {
        variant: run_variant(cards, args.archetype, args.mode, variant, args.runs_per_engine, matchup=args.matchup, going=args.going)
        for variant in ENGINE_VARIANTS
    }
    report = {
        "config": {
            "archetype": args.archetype,
            "mode": args.mode,
            "runs_per_engine": args.runs_per_engine,
            "matchup": args.matchup,
            "going": args.going,
            "variants": list(ENGINE_VARIANTS),
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ranking": rank_variants(variants),
        "variants": variants,
    }
    path = save_report(report)
    print_report(report, path)


if __name__ == "__main__":
    main()
