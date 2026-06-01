from __future__ import annotations

import argparse
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.builder import build_deck, card_role_flags, detect_card_engines, detect_deck_engines, is_extra_deck_card, score_deck_breakdown
from deck.deck_analysis import combo_report, critique_deck
from deck.deck_utils import split_deck
from deck.hand_simulator import real_combo_report
from deck.package_builder import summarize_package_metrics
from deck.package_quality import score_package_quality
from deck.post_side_memory import update_post_side_memory
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.matchup_engine_stats import load_matchup_engine_stats, recommended_variant
from deck.side_deck_planner import build_side_deck
from deck.post_side_evaluation import evaluate_post_side_plan
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.opponent_metric_builder import (
    OPPONENT_METRIC_KEYS,
    build_opponent_metric_bundle,
    display_opponent_metric,
    normalize_opponent_metrics_for_gates,
    opponent_gate_normalization_metadata,
    numeric_observation,
    numeric_opponent_metric_keys,
    observed_metric_totals,
    summarize_opponent_metrics,
)
from SystemAIYugioh.report_schema import normalize_report
from SystemAIYugioh.regression_gates import evaluate_training_batch
from SystemAIYugioh.runtime_context import DEFAULT_RUNTIME_CONTEXT, RuntimeContext

TRAINING_RUNS_DIR = Path("SystemAIYugioh") / "data" / "training_runs"
LEARNED_CARD_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learned_card_stats.json"
LEARNING_TUNING_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learning_tuning.json"
LEARNED_ENGINE_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learned_engine_stats.json"
TUNING_STEP = 0.01
MAX_TUNING_ADJUSTMENT = 0.12
MAX_ENGINE_ADJUSTMENT = 0.10
SIDE_METRIC_KEYS = (
    "side_deck_score",
    "matchup_coverage_score",
    "going_first_side_score",
    "going_second_side_score",
    "choke_stop_rate",
    "opponent_recovery_rate",
    "choke_coverage_score",
    "best_interruption_overlap",
    "poor_interruption_count",
    "timing_precision_score",
    "pivot_risk_score",
    "best_timing_window_count",
    "late_interruption_risk",
    "early_interruption_risk",
    "backup_line_success_rate",
    "graph_stop_rate",
    "graph_pivot_rate",
    "graph_endboard_reduction_score",
    "graph_best_interruption_count",
    "graph_poor_interruption_count",
    "graph_timing_precision_score",
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_pivot_success_rate",
    "opponent_backup_success_rate",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated autonomous deck-builder evaluations.")
    parser.add_argument("--archetype", required=True, help='Archetype to build, for example "Blue-Eyes".')
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--matchup", choices=list_matchup_names(), default="unknown_meta")
    parser.add_argument("--going", choices=("first", "second", "both"), default="both")
    return parser.parse_args()


def score_deck(deck: list[dict[str, Any]], mode: str) -> float:
    return score_deck_breakdown(deck, "", mode)["final_score"]


def run_single_evaluation(
    database: CardDatabase,
    archetype: str,
    mode: str,
    run_number: int,
    matchup: str = "unknown_meta",
    going: str = "both",
) -> dict[str, Any]:
    cards = DEFAULT_RUNTIME_CONTEXT.cards(refresh=True)
    matchup_stats = load_matchup_engine_stats(archetype, mode)
    matchup_variant = recommended_variant(matchup_stats, matchup, going)
    deck, archetype_pool = build_deck(cards, archetype, mode=mode, matchup=matchup, going=going)
    main_deck, extra_deck = split_deck(deck)
    score_breakdown = score_deck_breakdown(deck, archetype, mode)
    final_score = score_breakdown["final_score"]
    gameplay_report = real_combo_report(deck, archetype, samples=100)
    package_report = summarize_package_metrics(deck)
    package_quality = score_package_quality(deck, package_report, score_breakdown)
    side_report = build_side_deck(deck, archetype, get_matchup_profile(matchup), cards, going=going)
    post_side_report = evaluate_post_side_plan(deck, cards, archetype, mode, matchup, going)
    opponent_metrics = build_opponent_metric_bundle(post_side_report, side_report, matchup=matchup, simulated=True)

    return {
        "run": run_number,
        "ok": True,
        "archetype": archetype,
        "mode": mode,
        "matchup": matchup,
        "going": going,
        "matchup_aware_weighting_used": bool(matchup_variant),
        "matchup_recommended_engine_variant": matchup_variant,
        "final_score": final_score,
        "score_breakdown": score_breakdown,
        "detected_engines": detect_deck_engines(deck),
        "archetype_pool_size": len(archetype_pool),
        "main_deck": [card["name"] for card in main_deck],
        "extra_deck": [card["name"] for card in extra_deck],
        "critique_issues": critique_deck(deck, archetype),
        "combo_report": combo_report(deck),
        "real_combo_report": gameplay_report,
        "playable_hand_rate": gameplay_report["playable_hand_rate"],
        "brick_rate": gameplay_report["brick_rate"],
        "most_common_combo_lines": gameplay_report["most_common_combo_lines"],
        "best_line_frequency": gameplay_report["best_line_frequency"],
        "average_endboard_score": gameplay_report["average_endboard_score"],
        "interruption_resilience_score": gameplay_report["interruption_resilience_score"],
        "follow_up_score": gameplay_report["follow_up_score"],
        "package_report": package_report,
        "package_quality": package_quality,
        "package_quality_score": package_quality["final_package_quality_score"],
        "quota_violation_penalty": package_quality["quota_violation_penalty"],
        "package_counts": package_report["package_counts"],
        "chosen_engine_variant": package_report["chosen_engine_variant"],
        "package_starter_count": package_report["starter_count"],
        "package_brick_count": package_report["brick_count"],
        "non_engine_count": package_report["non_engine_count"],
        "package_quota_violations": package_report["package_quota_violations"],
        "side_deck_report": {
            **side_report,
            "side_deck": [card["name"] for card in side_report["side_deck"]],
        },
        "side_deck_score": side_report["side_deck_score"],
        "matchup_coverage_score": side_report["matchup_coverage_score"],
        "going_first_side_score": side_report["going_first_side_score"],
        "going_second_side_score": side_report["going_second_side_score"],
        **opponent_metrics,
        "recommended_side_cards": [card["name"] for card in side_report["side_deck"]],
        "post_side_report": post_side_report,
        "game1_score": post_side_report["game1_score"],
        "post_side_score": post_side_report["post_side_score"],
        "post_side_delta": post_side_report["post_side_delta"],
        "post_side_valid": post_side_report["post_side_valid"],
        "side_cards_used": post_side_report["side_cards_used"],
        "cards_sided_out": post_side_report["cards_sided_out"],
        "side_optimization": {
            "candidate_count": post_side_report.get("candidate_count", 0),
            "valid_candidate_count": post_side_report.get("valid_candidate_count", 0),
            "valid_candidate_rate": post_side_report.get("valid_candidate_rate", 0),
            "optimization_used": post_side_report.get("optimization_used", False),
            "post_side_memory_used": post_side_report.get("post_side_memory_used", False),
            "best_side_in": post_side_report.get("best_side_in", []),
            "best_side_out": post_side_report.get("best_side_out", []),
            "rejection_reasons": post_side_report.get("rejection_reasons", {}),
        },
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if result.get("ok")]
    failed = [result for result in results if not result.get("ok")]

    if not successful:
        return {
            "successful_runs": 0,
            "failed_runs": len(failed),
            "best_score": 0,
            "average_score": 0,
            "average_score_breakdown": {},
            "most_common_main_deck_cards": [],
            "most_common_extra_deck_cards": [],
            "most_common_critique_issues": [],
            "best_deck_list": {"main_deck": [], "extra_deck": []},
        }

    best = max(successful, key=lambda result: result["final_score"])
    main_counter = Counter(card for result in successful for card in result["main_deck"])
    extra_counter = Counter(card for result in successful for card in result["extra_deck"])
    critique_counter = Counter(issue for result in successful for issue in result["critique_issues"])
    breakdown_totals: Counter[str] = Counter()
    breakdown_counts: Counter[str] = Counter()
    real_combo_totals: Counter[str] = Counter()
    line_counter: Counter[str] = Counter()
    best_line_counter: Counter[str] = Counter()
    package_totals: Counter[str] = Counter()
    package_violation_counter: Counter[str] = Counter()
    package_quality_total = 0.0
    package_quality_count = 0
    side_metric_totals: Counter[str] = Counter()
    side_metric_counts: Counter[str] = Counter()
    side_metric_counts: Counter[str] = Counter()
    side_card_counter: Counter[str] = Counter()
    post_side_totals: Counter[str] = Counter()
    post_side_valid_count = 0
    optimization_success_count = 0
    memory_used_count = 0
    valid_candidate_rate_total = 0.0
    for result in successful:
        breakdown = result.get("score_breakdown", {})
        if isinstance(breakdown, dict):
            for key, value in breakdown.items():
                try:
                    breakdown_totals[key] += float(value)
                    breakdown_counts[key] += 1
                except (TypeError, ValueError):
                    continue
        gameplay = result.get("real_combo_report", {})
        if isinstance(gameplay, dict):
            for key in (
                "playable_hand_rate",
                "brick_rate",
                "average_brick_count",
                "average_starter_count",
                "average_extender_count",
                "average_interruption_count",
                "average_endboard_score",
                "combo_line_score",
                "interruption_resilience_score",
                "follow_up_score",
                "recovery_route_frequency",
                "normal_summon_conflict_rate",
                "once_per_turn_conflict_rate",
                "dead_duplicate_rate",
                "payoff_without_enabler_rate",
                "enabler_without_payoff_rate",
                "best_line_average_score",
                "graph_valid_line_rate",
                "graph_average_line_score",
                "graph_average_payoff_score",
                "graph_average_resource_score",
                "graph_average_risk_score",
                "graph_failed_line_rate",
                "optional_line_failure_rate",
                "best_line_failure_rate",
                "no_valid_line_rate",
                "branch_valid_rate",
                "no_valid_branch_rate",
                "average_branch_score",
                "interruption_window_count",
                "average_interruption_risk",
                "ash_vulnerability_rate",
                "imperm_vulnerability_rate",
                "veiler_vulnerability_rate",
                "droll_vulnerability_rate",
                "crow_vulnerability_rate",
                "nibiru_vulnerability_rate",
                "recovery_route_rate",
                "interrupted_line_success_rate",
                "resilience_score",
                "resource_valid_line_rate",
                "missing_material_rate",
                "missing_search_target_rate",
                "missing_extra_deck_rate",
                "cost_failure_rate",
                "normalized_search_failure_rate",
                "normalized_cost_failure_rate",
                "normalized_material_failure_rate",
                "normalized_extra_deck_failure_rate",
                "cost_condition_valid_rate",
                "cost_failure_rate_normalized",
                "condition_failure_rate_normalized",
                "reveal_cost_failure_rate",
                "discard_cost_failure_rate",
                "gy_condition_failure_rate",
                "control_condition_failure_rate",
                "history_condition_failure_rate",
                "summon_history_failure_rate",
                "gy_history_failure_rate",
                "activation_history_failure_rate",
                "resolution_history_failure_rate",
                "normal_summon_failure_rate",
                "once_per_turn_failure_rate",
                "typed_material_valid_rate",
                "synchro_material_failure_rate",
                "fusion_material_failure_rate",
                "ritual_material_failure_rate",
                "link_material_failure_rate",
                "named_material_failure_rate",
                "synchro_exact_level_valid_rate",
                "synchro_level_failure_rate",
                "ritual_level_valid_rate",
                "ritual_level_failure_rate",
                "xyz_material_valid_rate",
                "link_material_valid_rate",
            ):
                try:
                    real_combo_totals[key] += float(gameplay.get(key, 0) or 0)
                except (TypeError, ValueError):
                    continue
            line_counter.update(dict(gameplay.get("most_common_combo_lines", [])))
            best_line_counter.update(dict(gameplay.get("best_line_frequency", [])))
        package_report = result.get("package_report", {})
        if isinstance(package_report, dict):
            package_totals.update(package_report.get("package_counts", {}))
            package_violation_counter.update(str(item) for item in package_report.get("package_quota_violations", []))
        if "package_quality_score" in result:
            package_quality_total += float(result.get("package_quality_score", 0) or 0)
            package_quality_count += 1
        for key in SIDE_METRIC_KEYS:
            observed = numeric_observation(result.get(key))
            if observed is not None:
                side_metric_totals[key] += observed
                side_metric_counts[key] += 1
        side_card_counter.update(str(card) for card in result.get("recommended_side_cards", []))
        for key in ("game1_score", "post_side_score", "post_side_delta"):
            try:
                post_side_totals[key] += float(result.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue
        if result.get("post_side_valid"):
            post_side_valid_count += 1
        optimization = result.get("side_optimization", {})
        if isinstance(optimization, dict):
            if optimization.get("optimization_used"):
                optimization_success_count += 1
            if optimization.get("post_side_memory_used"):
                memory_used_count += 1
            try:
                valid_candidate_rate_total += float(optimization.get("valid_candidate_rate", 0) or 0)
            except (TypeError, ValueError):
                pass

    def side_average(key: str, digits: int = 4) -> Any:
        if key in numeric_opponent_metric_keys():
            return summarize_opponent_metrics(successful, prefix="", keys=(key,), include_counts=False)[key]
        count = side_metric_counts[key]
        return round(side_metric_totals[key] / count, digits) if count else 0

    return {
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "best_score": best["final_score"],
        "average_score": round(mean(result["final_score"] for result in successful), 2),
        "average_score_breakdown": {
            key: round(breakdown_totals[key] / breakdown_counts[key], 2)
            for key in breakdown_totals
            if breakdown_counts[key]
        },
        "most_common_main_deck_cards": main_counter.most_common(15),
        "most_common_extra_deck_cards": extra_counter.most_common(15),
        "most_common_critique_issues": critique_counter.most_common(15),
        "average_real_combo_values": {
            key: round(value / len(successful), 4)
            for key, value in real_combo_totals.items()
        },
        "most_common_combo_lines": line_counter.most_common(10),
        "best_line_frequency": best_line_counter.most_common(10),
        "package_counts": dict(sorted(package_totals.items())),
        "package_quota_violations": package_violation_counter.most_common(10),
        "average_package_quality_score": round(package_quality_total / package_quality_count, 2) if package_quality_count else 0,
        "average_side_deck_score": side_average("side_deck_score", 2),
        "average_matchup_coverage_score": side_average("matchup_coverage_score", 2),
        "average_going_first_side_score": side_average("going_first_side_score", 2),
        "average_going_second_side_score": side_average("going_second_side_score", 2),
        "average_choke_stop_rate": side_average("choke_stop_rate", 4),
        "average_opponent_recovery_rate": side_average("opponent_recovery_rate", 4),
        "average_choke_coverage_score": side_average("choke_coverage_score", 2),
        "average_best_interruption_overlap": side_average("best_interruption_overlap", 2),
        "average_poor_interruption_count": side_average("poor_interruption_count", 2),
        "average_timing_precision_score": side_average("timing_precision_score", 4),
        "average_pivot_risk_score": side_average("pivot_risk_score", 4),
        "average_best_timing_window_count": side_average("best_timing_window_count", 2),
        "average_late_interruption_risk": side_average("late_interruption_risk", 4),
        "average_early_interruption_risk": side_average("early_interruption_risk", 4),
        "average_backup_line_success_rate": side_average("backup_line_success_rate", 4),
        "average_graph_stop_rate": side_average("graph_stop_rate", 4),
        "average_graph_pivot_rate": side_average("graph_pivot_rate", 4),
        "average_graph_endboard_reduction_score": side_average("graph_endboard_reduction_score", 4),
        "average_graph_best_interruption_count": side_average("graph_best_interruption_count", 2),
        "average_graph_poor_interruption_count": side_average("graph_poor_interruption_count", 2),
        "average_graph_timing_precision_score": side_average("graph_timing_precision_score", 4),
        "average_opponent_resource_valid_rate": side_average("opponent_resource_valid_rate", 4),
        "average_opponent_resource_failure_rate": side_average("opponent_resource_failure_rate", 4),
        "average_opponent_pivot_success_rate": side_average("opponent_pivot_success_rate", 4),
        "average_opponent_backup_success_rate": side_average("opponent_backup_success_rate", 4),
        **summarize_opponent_metrics(successful, keys=(), include_counts=True),
        "recommended_side_cards": side_card_counter.most_common(15),
        "average_game1_score": round(post_side_totals["game1_score"] / len(successful), 2),
        "average_post_side_score": round(post_side_totals["post_side_score"] / len(successful), 2),
        "average_post_side_delta": round(post_side_totals["post_side_delta"] / len(successful), 2),
        "post_side_valid_rate": round(post_side_valid_count / len(successful), 4),
        "average_valid_candidate_rate": round(valid_candidate_rate_total / len(successful), 4),
        "side_optimization_success_rate": round(optimization_success_count / len(successful), 4),
        "post_side_memory_used_rate": round(memory_used_count / len(successful), 4),
        "matchup_weighting": [bool(result.get("matchup_aware_weighting_used")) for result in successful],
        "best_deck_list": {
            "main_deck": best["main_deck"],
            "extra_deck": best["extra_deck"],
        },
    }


def save_training_run(payload: dict[str, Any]) -> Path:
    TRAINING_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype = payload["config"]["archetype"].lower().replace(" ", "_")
    mode = payload["config"]["mode"]
    path = TRAINING_RUNS_DIR / f"{timestamp}_{archetype}_{mode}.json"
    atomic_write_json(path, normalize_report("training", payload))
    return path


def load_json_file(path: Path, default: Any) -> Any:
    return safe_load_json(path, default)


def successful_results_from_payload(payload: Any, archetype: str, mode: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    config = payload.get("config", {})
    if not isinstance(config, dict):
        return []
    if str(config.get("archetype", "")).casefold() != archetype.casefold():
        return []
    if config.get("mode") != mode:
        return []

    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        return []

    successful = []
    for result in runs:
        if is_valid_successful_result(result):
            successful.append(result)
    return successful


def is_valid_successful_result(result: Any) -> bool:
    if not isinstance(result, dict) or not result.get("ok"):
        return False
    required = ("final_score", "main_deck", "extra_deck", "critique_issues", "combo_report")
    if any(key not in result for key in required):
        return False
    if not isinstance(result["main_deck"], list) or not isinstance(result["extra_deck"], list):
        return False
    try:
        float(result["final_score"])
    except (TypeError, ValueError):
        return False
    return True


def deck_engine_names(result: dict[str, Any], card_lookup: dict[str, dict[str, Any]] | None = None) -> set[str]:
    if card_lookup is not None:
        engines = set()
        deck_names = list(result.get("main_deck", [])) + list(result.get("extra_deck", []))
        for card_name in deck_names:
            card = card_lookup.get(str(card_name))
            if card:
                engines.update(detect_card_engines(card))
        return engines

    engines = result.get("detected_engines", {})
    if isinstance(engines, dict):
        return {str(engine) for engine in engines}
    if isinstance(engines, list):
        return {str(engine) for engine in engines}
    return set()


def collect_historical_successes(
    archetype: str,
    mode: str,
    current_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    successful = [result for result in current_results if is_valid_successful_result(result)]
    if TRAINING_RUNS_DIR.exists():
        for path in TRAINING_RUNS_DIR.glob("*.json"):
            payload = load_json_file(path, {})
            successful.extend(successful_results_from_payload(payload, archetype, mode))
    return successful


def build_learned_profile(archetype: str, mode: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if is_valid_successful_result(result)]
    if not successful:
        return {
            "archetype": archetype,
            "mode": mode,
            "total_runs": 0,
            "average_score": 0,
            "best_score": 0,
            "best_deck_list": {"main_deck": [], "extra_deck": []},
            "card_appearance_counts": {},
            "card_average_score_when_included": {},
            "cards_appearing_in_top_10_percent_decks": {},
            "cards_appearing_often_in_bottom_25_percent_decks": {},
            "most_common_critique_issues": {},
            "average_combo_report_values": {},
            "average_real_combo_report_values": {},
            "average_side_deck_score": 0,
            "average_matchup_coverage_score": 0,
            "average_going_first_side_score": 0,
            "average_going_second_side_score": 0,
            "average_game1_score": 0,
            "average_post_side_score": 0,
            "average_post_side_delta": 0,
            "post_side_valid_rate": 0,
            "average_valid_candidate_rate": 0,
            "side_optimization_success_rate": 0,
        }

    ranked = sorted(successful, key=lambda result: float(result["final_score"]), reverse=True)
    best = ranked[0]
    scores = [float(result["final_score"]) for result in successful]
    top_count = max(1, math.ceil(len(ranked) * 0.10))
    bottom_count = max(1, math.ceil(len(ranked) * 0.25))
    top_decks = ranked[:top_count]
    bottom_decks = ranked[-bottom_count:]

    appearance_counts: Counter[str] = Counter()
    score_totals: Counter[str] = Counter()
    score_seen_counts: Counter[str] = Counter()
    top_counts: Counter[str] = Counter()
    bottom_counts: Counter[str] = Counter()
    critique_counts: Counter[str] = Counter()
    combo_totals: Counter[str] = Counter()
    real_combo_totals: Counter[str] = Counter()
    side_metric_totals: Counter[str] = Counter()
    post_side_totals: Counter[str] = Counter()
    post_side_valid_count = 0
    optimization_success_count = 0
    memory_used_count = 0
    valid_candidate_rate_total = 0.0

    for result in successful:
        deck_cards = list(result["main_deck"]) + list(result["extra_deck"])
        unique_cards = set(str(card) for card in deck_cards)
        appearance_counts.update(str(card) for card in deck_cards)
        for card in unique_cards:
            score_totals[card] += float(result["final_score"])
            score_seen_counts[card] += 1
        critique_counts.update(str(issue) for issue in result.get("critique_issues", []))
        combo_report = result.get("combo_report", {})
        if isinstance(combo_report, dict):
            for key, value in combo_report.items():
                try:
                    combo_totals[str(key)] += float(value)
                except (TypeError, ValueError):
                    continue
        real_report = result.get("real_combo_report", {})
        if isinstance(real_report, dict):
            for key, value in real_report.items():
                if key in {"most_common_combo_lines", "best_line_frequency", "choke_point_frequency"}:
                    continue
                try:
                    real_combo_totals[str(key)] += float(value)
                except (TypeError, ValueError):
                    continue
        for key in SIDE_METRIC_KEYS:
            observed = numeric_observation(result.get(key))
            if observed is not None:
                side_metric_totals[key] += observed
                side_metric_counts[key] += 1
        for key in ("game1_score", "post_side_score", "post_side_delta"):
            try:
                post_side_totals[key] += float(result.get(key, 0) or 0)
            except (TypeError, ValueError):
                continue
        if result.get("post_side_valid"):
            post_side_valid_count += 1
        optimization = result.get("side_optimization", {})
        if isinstance(optimization, dict):
            if optimization.get("optimization_used"):
                optimization_success_count += 1
            if optimization.get("post_side_memory_used"):
                memory_used_count += 1
            try:
                valid_candidate_rate_total += float(optimization.get("valid_candidate_rate", 0) or 0)
            except (TypeError, ValueError):
                pass

    for result in top_decks:
        top_counts.update(set(str(card) for card in result["main_deck"] + result["extra_deck"]))

    for result in bottom_decks:
        bottom_counts.update(set(str(card) for card in result["main_deck"] + result["extra_deck"]))

    average_score = mean(scores)
    frequent_bottom_threshold = max(1, math.ceil(bottom_count * 0.5))
    bottom_often = {
        card: count
        for card, count in bottom_counts.most_common()
        if count >= frequent_bottom_threshold
        and card not in top_counts
        and score_totals[card] / score_seen_counts[card] <= average_score
    }

    def side_average(key: str, digits: int = 4) -> Any:
        if key in numeric_opponent_metric_keys():
            return summarize_opponent_metrics(successful, prefix="", keys=(key,), include_counts=False)[key]
        count = side_metric_counts[key]
        return round(side_metric_totals[key] / count, digits) if count else 0

    return {
        "archetype": archetype,
        "mode": mode,
        "total_runs": len(successful),
        "average_score": round(average_score, 2),
        "best_score": best["final_score"],
        "best_deck_list": {
            "main_deck": best["main_deck"],
            "extra_deck": best["extra_deck"],
        },
        "card_appearance_counts": dict(appearance_counts.most_common()),
        "card_average_score_when_included": {
            card: round(score_totals[card] / score_seen_counts[card], 2)
            for card in score_seen_counts
        },
        "cards_appearing_in_top_10_percent_decks": dict(top_counts.most_common()),
        "cards_appearing_often_in_bottom_25_percent_decks": bottom_often,
        "most_common_critique_issues": dict(critique_counts.most_common(25)),
        "average_combo_report_values": {
            key: round(value / len(successful), 2)
            for key, value in combo_totals.items()
        },
        "average_real_combo_report_values": {
            key: round(value / len(successful), 4)
            for key, value in real_combo_totals.items()
        },
        "average_side_deck_score": side_average("side_deck_score", 2),
        "average_matchup_coverage_score": side_average("matchup_coverage_score", 2),
        "average_going_first_side_score": side_average("going_first_side_score", 2),
        "average_going_second_side_score": side_average("going_second_side_score", 2),
        "average_choke_stop_rate": side_average("choke_stop_rate", 4),
        "average_opponent_recovery_rate": side_average("opponent_recovery_rate", 4),
        "average_choke_coverage_score": side_average("choke_coverage_score", 2),
        "average_best_interruption_overlap": side_average("best_interruption_overlap", 2),
        "average_poor_interruption_count": side_average("poor_interruption_count", 2),
        "average_timing_precision_score": side_average("timing_precision_score", 4),
        "average_pivot_risk_score": side_average("pivot_risk_score", 4),
        "average_best_timing_window_count": side_average("best_timing_window_count", 2),
        "average_late_interruption_risk": side_average("late_interruption_risk", 4),
        "average_early_interruption_risk": side_average("early_interruption_risk", 4),
        "average_backup_line_success_rate": side_average("backup_line_success_rate", 4),
        "average_graph_stop_rate": side_average("graph_stop_rate", 4),
        "average_graph_pivot_rate": side_average("graph_pivot_rate", 4),
        "average_graph_endboard_reduction_score": side_average("graph_endboard_reduction_score", 4),
        "average_graph_best_interruption_count": side_average("graph_best_interruption_count", 2),
        "average_graph_poor_interruption_count": side_average("graph_poor_interruption_count", 2),
        "average_graph_timing_precision_score": side_average("graph_timing_precision_score", 4),
        "average_opponent_resource_valid_rate": side_average("opponent_resource_valid_rate", 4),
        "average_opponent_resource_failure_rate": side_average("opponent_resource_failure_rate", 4),
        "average_opponent_pivot_success_rate": side_average("opponent_pivot_success_rate", 4),
        "average_opponent_backup_success_rate": side_average("opponent_backup_success_rate", 4),
        "average_game1_score": round(post_side_totals["game1_score"] / len(successful), 2),
        "average_post_side_score": round(post_side_totals["post_side_score"] / len(successful), 2),
        "average_post_side_delta": round(post_side_totals["post_side_delta"] / len(successful), 2),
        "post_side_valid_rate": round(post_side_valid_count / len(successful), 4),
        "average_valid_candidate_rate": round(valid_candidate_rate_total / len(successful), 4),
        "side_optimization_success_rate": round(optimization_success_count / len(successful), 4),
        "post_side_memory_used_rate": round(memory_used_count / len(successful), 4),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def save_learned_profile(archetype: str, mode: str, profile: dict[str, Any]) -> bool:
    learned_stats = load_json_file(LEARNED_CARD_STATS_PATH, {})
    if not isinstance(learned_stats, dict):
        learned_stats = {}

    profiles = learned_stats.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        learned_stats["profiles"] = profiles

    archetype_key = archetype.casefold()
    mode_profiles = profiles.setdefault(archetype_key, {})
    if not isinstance(mode_profiles, dict):
        mode_profiles = {}
        profiles[archetype_key] = mode_profiles

    mode_profiles[mode] = profile
    learned_stats["version"] = 1
    learned_stats["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    LEARNED_CARD_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LEARNED_CARD_STATS_PATH, learned_stats)
    return True


def build_learning_tuning_profile(
    archetype: str,
    mode: str,
    results: list[dict[str, Any]],
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [
        result
        for result in results
        if is_valid_successful_result(result) and isinstance(result.get("score_breakdown"), dict)
    ]
    card_lookup = {str(card.get("name", "")): card for card in cards}

    if not successful:
        return {
            "archetype": archetype,
            "mode": mode,
            "total_runs_analyzed": 0,
            "card_adjustments": {},
            "card_reasons": {},
            "weakness_counts": {},
        }

    average_score = mean(float(result["final_score"]) for result in successful)
    average_brick_penalty = mean(_score_value(result.get("score_breakdown", {}), "brick_penalty") for result in successful)
    adjustments: Counter[str] = Counter()
    weakness_counts: Counter[str] = Counter()
    card_reasons: dict[str, Counter[str]] = {}

    for result in successful:
        breakdown = result.get("score_breakdown", {})
        if not isinstance(breakdown, dict):
            continue

        deck_names = [str(card) for card in result.get("main_deck", []) + result.get("extra_deck", [])]
        final_score = float(result.get("final_score", 0) or 0)

        high_brick_threshold = max(5.0, average_brick_penalty + 1.0)
        if final_score >= average_score and _score_value(breakdown, "brick_penalty") >= high_brick_threshold:
            weakness_counts["high_brick_penalty"] += 1
            for card_name in deck_names:
                card = card_lookup.get(card_name)
                if card and "brick" in card_role_flags(card):
                    add_tuning_signal(adjustments, card_reasons, card_name, "brick_penalty", -TUNING_STEP)

        if _score_value(breakdown, "starter_score") < 16:
            weakness_counts["low_starter_score"] += 1
            for card_name, card in card_lookup.items():
                if _same_archetype(card, archetype) and "starter" in card_role_flags(card):
                    add_tuning_signal(adjustments, card_reasons, card_name, "starter_shortage", TUNING_STEP)

        if _score_value(breakdown, "interruption_score") < 18:
            weakness_counts["low_interruption_score"] += 1
            for card_name, card in card_lookup.items():
                if _same_archetype(card, archetype) and "interruption" in card_role_flags(card):
                    add_tuning_signal(adjustments, card_reasons, card_name, "interruption_shortage", TUNING_STEP)

        if _score_value(breakdown, "endboard_score") < 15:
            weakness_counts["low_endboard_score"] += 1
            for card_name, card in card_lookup.items():
                if _same_archetype(card, archetype) and "endboard" in card_role_flags(card):
                    add_tuning_signal(adjustments, card_reasons, card_name, "endboard_shortage", TUNING_STEP)

    capped_adjustments = {
        card: round(max(-MAX_TUNING_ADJUSTMENT, min(MAX_TUNING_ADJUSTMENT, value)), 4)
        for card, value in adjustments.items()
        if value
    }

    return {
        "archetype": archetype,
        "mode": mode,
        "total_runs_analyzed": len(successful),
        "average_score_analyzed": round(average_score, 2),
        "card_adjustments": dict(sorted(capped_adjustments.items())),
        "card_reasons": {
            card: dict(reasons)
            for card, reasons in sorted(card_reasons.items())
            if card in capped_adjustments
        },
        "weakness_counts": dict(weakness_counts),
        "max_adjustment": MAX_TUNING_ADJUSTMENT,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def add_tuning_signal(
    adjustments: Counter[str],
    card_reasons: dict[str, Counter[str]],
    card_name: str,
    reason: str,
    value: float,
) -> None:
    adjustments[card_name] += value
    card_reasons.setdefault(card_name, Counter())[reason] += 1


def save_learning_tuning_profile(archetype: str, mode: str, profile: dict[str, Any]) -> bool:
    tuning_stats = load_json_file(LEARNING_TUNING_PATH, {})
    if not isinstance(tuning_stats, dict):
        tuning_stats = {}

    profiles = tuning_stats.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        tuning_stats["profiles"] = profiles

    archetype_key = archetype.casefold()
    mode_profiles = profiles.setdefault(archetype_key, {})
    if not isinstance(mode_profiles, dict):
        mode_profiles = {}
        profiles[archetype_key] = mode_profiles

    mode_profiles[mode] = profile
    tuning_stats["version"] = 1
    tuning_stats["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    LEARNING_TUNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LEARNING_TUNING_PATH, tuning_stats)
    return True


def build_engine_profile(
    archetype: str,
    mode: str,
    results: list[dict[str, Any]],
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    successful = [result for result in results if is_valid_successful_result(result)]
    if not successful:
        return empty_engine_profile(archetype, mode)

    card_lookup = {str(card.get("name", "")): card for card in cards}
    ranked = sorted(successful, key=lambda result: float(result["final_score"]), reverse=True)
    top_count = max(1, math.ceil(len(ranked) * 0.10))
    bottom_count = max(1, math.ceil(len(ranked) * 0.25))
    top_decks = ranked[:top_count]
    bottom_decks = ranked[-bottom_count:]
    global_average = mean(float(result["final_score"]) for result in successful)

    appearance_counts: Counter[str] = Counter()
    score_totals: Counter[str] = Counter()
    best_scores: dict[str, float] = {}
    top_counts: Counter[str] = Counter()
    bottom_counts: Counter[str] = Counter()
    brick_totals: Counter[str] = Counter()
    endboard_totals: Counter[str] = Counter()
    interruption_totals: Counter[str] = Counter()

    for result in successful:
        engines = deck_engine_names(result, card_lookup)
        breakdown = result.get("score_breakdown", {})
        for engine in engines:
            score = float(result["final_score"])
            appearance_counts[engine] += 1
            score_totals[engine] += score
            best_scores[engine] = max(best_scores.get(engine, score), score)
            brick_totals[engine] += _score_value(breakdown, "brick_penalty")
            endboard_totals[engine] += _score_value(breakdown, "endboard_score")
            interruption_totals[engine] += _score_value(breakdown, "interruption_score")

    for result in top_decks:
        top_counts.update(deck_engine_names(result, card_lookup))
    for result in bottom_decks:
        bottom_counts.update(deck_engine_names(result, card_lookup))

    average_score_per_engine = {
        engine: round(score_totals[engine] / appearance_counts[engine], 2)
        for engine in appearance_counts
    }
    average_brick = {
        engine: round(brick_totals[engine] / appearance_counts[engine], 2)
        for engine in appearance_counts
    }
    average_endboard = {
        engine: round(endboard_totals[engine] / appearance_counts[engine], 2)
        for engine in appearance_counts
    }
    average_interruption = {
        engine: round(interruption_totals[engine] / appearance_counts[engine], 2)
        for engine in appearance_counts
    }
    engine_adjustments = build_engine_adjustments(
        appearance_counts,
        average_score_per_engine,
        average_brick,
        top_counts,
        bottom_counts,
        global_average,
    )

    return {
        "archetype": archetype,
        "mode": mode,
        "total_runs": len(successful),
        "detected_engines": sorted(appearance_counts),
        "average_score_per_engine": average_score_per_engine,
        "best_score_per_engine": {engine: round(score, 2) for engine, score in sorted(best_scores.items())},
        "engine_appearance_count": dict(appearance_counts.most_common()),
        "top_deck_engine_counts": dict(top_counts.most_common()),
        "bottom_deck_engine_counts": dict(bottom_counts.most_common()),
        "average_brick_penalty_per_engine": average_brick,
        "average_endboard_score_per_engine": average_endboard,
        "average_interruption_score_per_engine": average_interruption,
        "engine_adjustments": engine_adjustments,
        "global_average_score": round(global_average, 2),
        "max_adjustment": MAX_ENGINE_ADJUSTMENT,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def empty_engine_profile(archetype: str, mode: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "mode": mode,
        "total_runs": 0,
        "detected_engines": [],
        "average_score_per_engine": {},
        "best_score_per_engine": {},
        "engine_appearance_count": {},
        "top_deck_engine_counts": {},
        "bottom_deck_engine_counts": {},
        "average_brick_penalty_per_engine": {},
        "average_endboard_score_per_engine": {},
        "average_interruption_score_per_engine": {},
        "engine_adjustments": {},
    }


def build_engine_adjustments(
    appearance_counts: Counter[str],
    average_scores: dict[str, float],
    average_brick: dict[str, float],
    top_counts: Counter[str],
    bottom_counts: Counter[str],
    global_average: float,
) -> dict[str, float]:
    adjustments = {}
    total_runs = max(1, sum(appearance_counts.values()))
    average_brick_baseline = mean(average_brick.values()) if average_brick else 0

    for engine, appearances in appearance_counts.items():
        score_delta = (average_scores[engine] - global_average) / max(abs(global_average), 1)
        top_rate = top_counts[engine] / max(appearances, 1)
        bottom_rate = bottom_counts[engine] / max(appearances, 1)
        adjustment = score_delta * 0.25
        adjustment += top_rate * 0.04
        adjustment -= bottom_rate * 0.04
        if average_brick.get(engine, 0) > average_brick_baseline + 1:
            adjustment -= 0.03
        if appearances < max(2, total_runs * 0.03):
            adjustment *= 0.5
        adjustments[engine] = round(max(-MAX_ENGINE_ADJUSTMENT, min(MAX_ENGINE_ADJUSTMENT, adjustment)), 4)

    return dict(sorted(adjustments.items()))


def save_engine_profile(archetype: str, mode: str, profile: dict[str, Any]) -> bool:
    engine_stats = load_json_file(LEARNED_ENGINE_STATS_PATH, {})
    if not isinstance(engine_stats, dict):
        engine_stats = {}

    profiles = engine_stats.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        engine_stats["profiles"] = profiles

    archetype_key = archetype.casefold()
    mode_profiles = profiles.setdefault(archetype_key, {})
    if not isinstance(mode_profiles, dict):
        mode_profiles = {}
        profiles[archetype_key] = mode_profiles

    mode_profiles[mode] = profile
    engine_stats["version"] = 1
    engine_stats["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    LEARNED_ENGINE_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LEARNED_ENGINE_STATS_PATH, engine_stats)
    return True


def _same_archetype(card: dict[str, Any], archetype: str) -> bool:
    return bool(card.get("archetype") and archetype.lower() in str(card.get("archetype", "")).lower())


def _score_value(breakdown: dict[str, Any], key: str) -> float:
    try:
        return float(breakdown.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def learned_summary(profile: dict[str, Any]) -> dict[str, list[tuple[str, int]]]:
    top_cards = Counter(profile.get("cards_appearing_in_top_10_percent_decks", {}))
    avoid_cards = Counter(profile.get("cards_appearing_often_in_bottom_25_percent_decks", {}))
    issues = Counter(profile.get("most_common_critique_issues", {}))
    return {
        "top_learned_cards": top_cards.most_common(10),
        "cards_to_avoid": avoid_cards.most_common(10),
        "most_common_issues": issues.most_common(10),
    }


def tuning_summary(profile: dict[str, Any]) -> dict[str, list[tuple[str, float]]]:
    adjustments = profile.get("card_adjustments", {})
    if not isinstance(adjustments, dict):
        return {"boosted": [], "reduced": []}
    boosted = sorted(
        ((card, value) for card, value in adjustments.items() if value > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:10]
    reduced = sorted(
        ((card, value) for card, value in adjustments.items() if value < 0),
        key=lambda item: item[1],
    )[:10]
    return {"boosted": boosted, "reduced": reduced}


def engine_summary(profile: dict[str, Any]) -> dict[str, list[tuple[str, float]]]:
    average_scores = profile.get("average_score_per_engine", {})
    adjustments = profile.get("engine_adjustments", {})
    if not isinstance(average_scores, dict):
        average_scores = {}
    if not isinstance(adjustments, dict):
        adjustments = {}
    top_engines = sorted(average_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    avoid_engines = sorted(adjustments.items(), key=lambda item: item[1])[:10]
    return {
        "top_engines": top_engines,
        "engines_to_avoid": [(engine, value) for engine, value in avoid_engines if value < 0],
        "engine_average_scores": top_engines,
    }


def print_summary(
    summary: dict[str, Any],
    path: Path,
    learning_summary: dict[str, list[tuple[str, int]]],
    learned_stats_saved: bool,
    tuning_info: dict[str, list[tuple[str, float]]],
    tuning_saved: bool,
    engine_info: dict[str, list[tuple[str, float]]],
    engine_stats_saved: bool,
) -> None:
    print("\nTraining Summary")
    print(f"Best score: {summary['best_score']}")
    print(f"Average score: {summary['average_score']}")
    print(f"Successful runs: {summary['successful_runs']}")
    print(f"Failed runs: {summary['failed_runs']}")
    matchup_weighted = sum(1 for result in summary.get("matchup_weighting", []) if result)
    if "matchup_weighting" in summary:
        print(f"Matchup-aware weighting used in runs: {matchup_weighted}/{summary['successful_runs']}")
    print("\nAverage score breakdown:")
    for key, value in summary.get("average_score_breakdown", {}).items():
        print(f"- {key}: {value}")
    print("\nMost common main deck cards:")
    for card, count in summary["most_common_main_deck_cards"]:
        print(f"- {card}: {count}")
    print("\nMost common extra deck cards:")
    for card, count in summary["most_common_extra_deck_cards"]:
        print(f"- {card}: {count}")
    print("\nMost common critique issues:")
    for issue, count in summary["most_common_critique_issues"]:
        print(f"- {issue}: {count}")
    print("\nReal combo metrics:")
    for key, value in summary.get("average_real_combo_values", {}).items():
        print(f"- {key}: {value}")
    print("\nMost common combo lines:")
    for line, count in summary.get("most_common_combo_lines", []):
        print(f"- {line}: {count}")
    print("\nBest line frequency:")
    for line, count in summary.get("best_line_frequency", []):
        print(f"- {line}: {count}")
    print("\nPackage counts:")
    for package_type, count in summary.get("package_counts", {}).items():
        print(f"- {package_type}: {count}")
    print("\nPackage quota violations:")
    violations = summary.get("package_quota_violations", [])
    if violations:
        for violation, count in violations:
            print(f"- {violation}: {count}")
    else:
        print("- None")
    print(f"\nAverage package quality score: {summary.get('average_package_quality_score', 0)}")
    print("\nSide deck metrics:")
    print(f"- side deck score: {summary.get('average_side_deck_score', 0)}")
    print(f"- matchup coverage: {summary.get('average_matchup_coverage_score', 0)}")
    print(f"- going first side score: {summary.get('average_going_first_side_score', 0)}")
    print(f"- going second side score: {summary.get('average_going_second_side_score', 0)}")
    print(f"- choke stop rate: {display_opponent_metric(summary.get('average_choke_stop_rate'))}")
    print(f"- opponent recovery rate: {display_opponent_metric(summary.get('average_opponent_recovery_rate'))}")
    print(f"- choke coverage score: {summary.get('average_choke_coverage_score', 0)}")
    print(f"- timing precision score: {summary.get('average_timing_precision_score', 0)}")
    print(f"- pivot risk score: {summary.get('average_pivot_risk_score', 0)}")
    print(f"- graph stop rate: {display_opponent_metric(summary.get('average_graph_stop_rate'))}")
    print(f"- graph pivot rate: {display_opponent_metric(summary.get('average_graph_pivot_rate'))}")
    print(f"- opponent resource valid rate: {display_opponent_metric(summary.get('average_opponent_resource_valid_rate'))}")
    print(f"- opponent resource failure rate: {display_opponent_metric(summary.get('average_opponent_resource_failure_rate'))}")
    print("\nRecommended side cards:")
    for card, count in summary.get("recommended_side_cards", []):
        print(f"- {card}: {count}")
    print("\nPost-side metrics:")
    print(f"- game 1 score: {summary.get('average_game1_score', 0)}")
    print(f"- post-side score: {summary.get('average_post_side_score', 0)}")
    print(f"- post-side delta: {summary.get('average_post_side_delta', 0)}")
    print(f"- post-side valid rate: {summary.get('post_side_valid_rate', 0)}")
    print(f"- valid candidate rate: {summary.get('average_valid_candidate_rate', 0)}")
    print(f"- optimization success rate: {summary.get('side_optimization_success_rate', 0)}")
    print(f"- post-side memory used rate: {summary.get('post_side_memory_used_rate', 0)}")
    print("\nTop learned cards:")
    for card, count in learning_summary["top_learned_cards"]:
        print(f"- {card}: {count}")
    print("\nCards to avoid:")
    for card, count in learning_summary["cards_to_avoid"]:
        print(f"- {card}: {count}")
    print("\nMost common learned issues:")
    for issue, count in learning_summary["most_common_issues"]:
        print(f"- {issue}: {count}")
    print("\nAuto-tuning boosts:")
    for card, value in tuning_info["boosted"]:
        print(f"- {card}: +{value}")
    print("\nAuto-tuning reductions:")
    for card, value in tuning_info["reduced"]:
        print(f"- {card}: {value}")
    print("\nTop engines:")
    for engine, score in engine_info["top_engines"]:
        print(f"- {engine}: {score}")
    print("\nEngines to avoid:")
    for engine, value in engine_info["engines_to_avoid"]:
        print(f"- {engine}: {value}")
    print("\nEngine average scores:")
    for engine, score in engine_info["engine_average_scores"]:
        print(f"- {engine}: {score}")
    print("\nBest deck list:")
    print("Main Deck:")
    for card in summary["best_deck_list"]["main_deck"]:
        print(f"- {card}")
    print("Extra Deck:")
    for card in summary["best_deck_list"]["extra_deck"]:
        print(f"- {card}")
    print(f"\nSaved results: {path}")
    print(f"Learned stats saved: {learned_stats_saved}")
    print(f"Learned stats path: {LEARNED_CARD_STATS_PATH}")
    print(f"Learning tuning saved: {tuning_saved}")
    print(f"Learning tuning path: {LEARNING_TUNING_PATH}")
    print(f"Engine stats saved: {engine_stats_saved}")
    print(f"Engine stats path: {LEARNED_ENGINE_STATS_PATH}")


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")

    startup_safety_cleanup()
    database = CardDatabase()
    results = []

    for run_number in range(1, args.runs + 1):
        try:
            result = run_single_evaluation(database, args.archetype, args.mode, run_number, matchup=args.matchup, going=args.going)
        except Exception as exc:
            result = {
                "run": run_number,
                "ok": False,
                "archetype": args.archetype,
                "mode": args.mode,
                "error": str(exc),
            }
        results.append(result)

    summary = summarize_results(results)
    payload = {
        "config": {
            "archetype": args.archetype,
            "mode": args.mode,
            "runs": args.runs,
            "matchup": args.matchup,
            "going": args.going,
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "runs": results,
    }
    historical_results = collect_historical_successes(args.archetype, args.mode, results)
    existing_learned_stats = load_json_file(LEARNED_CARD_STATS_PATH, {})
    existing_profile = (
        existing_learned_stats.get("profiles", {})
        .get(args.archetype.casefold(), {})
        .get(args.mode, {})
        if isinstance(existing_learned_stats, dict)
        else {}
    )
    gate_metadata = opponent_gate_normalization_metadata(summary)
    gate_summary = normalize_opponent_metrics_for_gates(summary)
    gate_result = evaluate_training_batch(gate_summary, existing_profile if isinstance(existing_profile, dict) else {})
    gate_result.update(gate_metadata)
    learned_profile = build_learned_profile(args.archetype, args.mode, historical_results)
    cards = database.load_cards()
    tuning_profile = build_learning_tuning_profile(args.archetype, args.mode, historical_results, cards)
    engine_profile = build_engine_profile(args.archetype, args.mode, historical_results, cards)
    if gate_result["accepted"]:
        learned_stats_saved = save_learned_profile(args.archetype, args.mode, learned_profile)
        tuning_saved = save_learning_tuning_profile(args.archetype, args.mode, tuning_profile)
        engine_stats_saved = save_engine_profile(args.archetype, args.mode, engine_profile)
        post_side_memory_profile = update_post_side_memory(
            args.archetype,
            args.mode,
            args.matchup,
            args.going,
            [result for result in results if result.get("ok")],
        )
        post_side_memory_saved = bool(post_side_memory_profile)
    else:
        learned_stats_saved = False
        tuning_saved = False
        engine_stats_saved = False
        post_side_memory_saved = False
    payload["regression_gate"] = gate_result
    path = save_training_run(payload)
    if gate_result["accepted"]:
        print("\nRegression gate: accepted learning update")
    else:
        print("\nRegression gate: rejected learning update")
        for reason in gate_result["reasons"]:
            print(f"- {reason}")
    print_summary(
        summary,
        path,
        learned_summary(learned_profile),
        learned_stats_saved,
        tuning_summary(tuning_profile),
        tuning_saved,
        engine_summary(engine_profile),
        engine_stats_saved,
    )
    print(f"Post-side memory saved: {post_side_memory_saved}")


if __name__ == "__main__":
    main()
