from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from data.card_limits import get_blocked_card_names, normalize_card_name, startup_safety_cleanup
from deck.builder import build_deck, score_deck_breakdown
from deck.deck_analysis import combo_report, critique_deck
from deck.deck_utils import split_deck
from deck.hand_simulator import real_combo_report
from deck.package_builder import summarize_package_metrics
from deck.package_quality import score_package_quality
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.matchup_engine_stats import load_matchup_engine_stats, recommended_variant
from deck.side_deck_planner import build_side_deck
from deck.post_side_evaluation import evaluate_post_side_plan
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.opponent_metric_builder import (
    build_opponent_metric_bundle,
    display_opponent_metric,
    numeric_observation,
    numeric_opponent_metric_keys,
    summarize_opponent_metrics,
)
from SystemAIYugioh.report_schema import normalize_report

EVALUATION_REPORTS_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "evaluation_reports"
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
    parser = argparse.ArgumentParser(description="Compare deck generation before and after learned weights.")
    parser.add_argument("--archetype", required=True, help='Archetype to evaluate, for example "Blue-Eyes".')
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--matchup", choices=list_matchup_names(), default="unknown_meta")
    parser.add_argument("--going", choices=("first", "second", "both"), default="both")
    return parser.parse_args()


def run_batch(
    database: CardDatabase,
    archetype: str,
    mode: str,
    runs: int,
    use_learning: bool,
    matchup: str = "unknown_meta",
    going: str = "both",
) -> list[dict[str, Any]]:
    results = []
    cards = database.load_cards()
    matchup_stats = load_matchup_engine_stats(archetype, mode) if use_learning else {}
    matchup_variant = recommended_variant(matchup_stats, matchup, going) if use_learning else None
    for run_number in range(1, runs + 1):
        try:
            deck, archetype_pool = build_deck(
                cards,
                archetype,
                mode=mode,
                use_learning=use_learning,
                matchup=matchup,
                going=going,
            )
            main_deck, extra_deck = split_deck(deck)
            breakdown = score_deck_breakdown(deck, archetype, mode)
            gameplay_report = real_combo_report(deck, archetype, samples=100)
            package_report = summarize_package_metrics(deck)
            package_quality = score_package_quality(deck, package_report, breakdown)
            side_report = build_side_deck(deck, archetype, get_matchup_profile(matchup), cards, going=going)
            post_side_report = evaluate_post_side_plan(deck, cards, archetype, mode, matchup, going, use_memory=True)
            no_memory_post_side = evaluate_post_side_plan(deck, cards, archetype, mode, matchup, going, use_memory=False)
            opponent_metrics = build_opponent_metric_bundle(post_side_report, side_report, matchup=matchup, simulated=True)
            result = {
                "run": run_number,
                "ok": True,
                "use_learning": use_learning,
                "matchup": matchup,
                "going": going,
                "matchup_aware_weighting_used": bool(matchup_variant),
                "matchup_recommended_engine_variant": matchup_variant,
                "final_score": breakdown["final_score"],
                "score_breakdown": breakdown,
                "archetype_pool_size": len(archetype_pool),
                "main_deck": [card["name"] for card in main_deck],
                "extra_deck": [card["name"] for card in extra_deck],
                "critique_issues": critique_deck(deck, archetype),
                "combo_report": combo_report(deck),
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
                "quota_violation_penalty": package_quality["quota_violation_penalty"],
                "package_counts": package_report["package_counts"],
                "package_starter_count": package_report["starter_count"],
                "package_brick_count": package_report["brick_count"],
                "non_engine_count": package_report["non_engine_count"],
                "package_quota_violations": package_report["package_quota_violations"],
                "blocked_card_violations": blocked_card_violations(deck),
                "side_deck_report": {
                    **side_report,
                    "side_deck": [card["name"] for card in side_report["side_deck"]],
                },
                "side_deck_score": side_report["side_deck_score"],
                "matchup_coverage_score": side_report["matchup_coverage_score"],
                "going_first_side_score": side_report["going_first_side_score"],
                "going_second_side_score": side_report["going_second_side_score"],
                **opponent_metrics,
                "post_side_report": post_side_report,
                "game1_score": post_side_report["game1_score"],
                "post_side_score": post_side_report["post_side_score"],
                "post_side_delta": post_side_report["post_side_delta"],
                "post_side_valid": post_side_report["post_side_valid"],
                "valid_candidate_rate": post_side_report.get("valid_candidate_rate", 0),
                "optimization_used": post_side_report.get("optimization_used", False),
                "post_side_memory_used": post_side_report.get("post_side_memory_used", False),
                "no_memory_post_side_score": no_memory_post_side.get("post_side_score", 0),
                "no_memory_post_side_delta": no_memory_post_side.get("post_side_delta", 0),
                "memory_post_side_delta_difference": round(post_side_report.get("post_side_delta", 0) - no_memory_post_side.get("post_side_delta", 0), 2),
            }
        except Exception as exc:
            result = {
                "run": run_number,
                "ok": False,
                "use_learning": use_learning,
                "error": str(exc),
            }
        results.append(result)
    return results


def blocked_card_violations(deck: list[dict[str, Any]]) -> list[str]:
    blocked_names = get_blocked_card_names()
    violations = []
    counts = Counter(card.get("name", "") for card in deck)
    for card in deck:
        card_name = str(card.get("name", ""))
        if normalize_card_name(card_name) in blocked_names or get_card_limit(card) == 0:
            violations.append(card_name)
        if counts[card_name] > get_card_limit(card):
            violations.append(f"{card_name} over limit")
    return sorted(set(violations))


def summarize_batch(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if result.get("ok")]
    failed = [result for result in results if not result.get("ok")]

    if not successful:
        return {
            "successful_runs": 0,
            "failed_runs": len(failed),
            "average_score": 0,
            "average_score_breakdown": {},
            "best_score": 0,
            "best_deck": {"main_deck": [], "extra_deck": []},
            "average_combo_values": {},
            "most_common_cards": [],
            "most_common_main_deck_cards": [],
            "most_common_extra_deck_cards": [],
            "most_common_critique_issues": [],
            "blocked_card_violations": [],
        }

    best = max(successful, key=lambda result: result["final_score"])
    all_cards = Counter(card for result in successful for card in result["main_deck"] + result["extra_deck"])
    main_cards = Counter(card for result in successful for card in result["main_deck"])
    extra_cards = Counter(card for result in successful for card in result["extra_deck"])
    critiques = Counter(issue for result in successful for issue in result["critique_issues"])
    violations = Counter(violation for result in successful for violation in result["blocked_card_violations"])
    combo_totals: Counter[str] = Counter()
    real_combo_totals: Counter[str] = Counter()
    package_totals: Counter[str] = Counter()
    package_violation_counter: Counter[str] = Counter()
    package_quality_total = 0.0
    package_quality_count = 0
    side_metric_totals: Counter[str] = Counter()
    side_metric_counts: Counter[str] = Counter()
    post_side_totals: Counter[str] = Counter()
    post_side_valid_count = 0
    valid_candidate_rate_total = 0.0
    optimization_success_count = 0
    memory_used_count = 0
    memory_delta_difference_total = 0.0
    breakdown_totals: Counter[str] = Counter()
    breakdown_counts: Counter[str] = Counter()

    for result in successful:
        combo = result.get("combo_report", {})
        if isinstance(combo, dict):
            for key, value in combo.items():
                combo_totals[str(key)] += float(value)
        real_combo = result.get("real_combo_report", {})
        if isinstance(real_combo, dict):
            for key in (
                "playable_hand_rate",
                "brick_rate",
                "combo_line_score",
                "average_endboard_score",
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
                real_combo_totals[str(key)] += float(real_combo.get(key, 0) or 0)
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
        for key in ("game1_score", "post_side_score", "post_side_delta"):
            post_side_totals[key] += float(result.get(key, 0) or 0)
        if result.get("post_side_valid"):
            post_side_valid_count += 1
        valid_candidate_rate_total += float(result.get("valid_candidate_rate", 0) or 0)
        if result.get("optimization_used"):
            optimization_success_count += 1
        if result.get("post_side_memory_used"):
            memory_used_count += 1
        memory_delta_difference_total += float(result.get("memory_post_side_delta_difference", 0) or 0)
        breakdown = result.get("score_breakdown", {})
        if isinstance(breakdown, dict):
            for key, value in breakdown.items():
                try:
                    breakdown_totals[str(key)] += float(value)
                    breakdown_counts[str(key)] += 1
                except (TypeError, ValueError):
                    continue

    def side_average(key: str, digits: int = 4) -> Any:
        if key in numeric_opponent_metric_keys():
            return summarize_opponent_metrics(successful, prefix="", keys=(key,), include_counts=False)[key]
        count = side_metric_counts[key]
        return round(side_metric_totals[key] / count, digits) if count else 0

    return {
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "average_score": round(mean(result["final_score"] for result in successful), 2),
        "average_score_breakdown": {
            key: round(value / breakdown_counts[key], 2)
            for key, value in breakdown_totals.items()
            if breakdown_counts[key]
        },
        "best_score": best["final_score"],
        "best_deck": {
            "main_deck": best["main_deck"],
            "extra_deck": best["extra_deck"],
        },
        "average_combo_values": {
            key: round(value / len(successful), 2)
            for key, value in combo_totals.items()
        },
        "average_real_combo_values": {
            key: round(value / len(successful), 4)
            for key, value in real_combo_totals.items()
        },
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
        "average_game1_score": round(post_side_totals["game1_score"] / len(successful), 2),
        "average_post_side_score": round(post_side_totals["post_side_score"] / len(successful), 2),
        "average_post_side_delta": round(post_side_totals["post_side_delta"] / len(successful), 2),
        "post_side_valid_rate": round(post_side_valid_count / len(successful), 4),
        "average_valid_candidate_rate": round(valid_candidate_rate_total / len(successful), 4),
        "side_optimization_success_rate": round(optimization_success_count / len(successful), 4),
        "post_side_memory_used_rate": round(memory_used_count / len(successful), 4),
        "average_memory_post_side_delta_difference": round(memory_delta_difference_total / len(successful), 2),
        "matchup_weighting_used": any(bool(result.get("matchup_aware_weighting_used")) for result in successful),
        "most_common_cards": all_cards.most_common(20),
        "most_common_main_deck_cards": main_cards.most_common(15),
        "most_common_extra_deck_cards": extra_cards.most_common(15),
        "most_common_critique_issues": critiques.most_common(15),
        "blocked_card_violations": violations.most_common(),
    }


def compare_summaries(baseline: dict[str, Any], learned: dict[str, Any]) -> dict[str, Any]:
    baseline_average = float(baseline.get("average_score", 0) or 0)
    learned_average = float(learned.get("average_score", 0) or 0)
    improvement = 0.0
    if baseline_average:
        improvement = ((learned_average - baseline_average) / baseline_average) * 100

    baseline_cards = Counter(dict(baseline.get("most_common_cards", [])))
    learned_cards = Counter(dict(learned.get("most_common_cards", [])))
    favored = (learned_cards - baseline_cards).most_common(15)
    avoided = (baseline_cards - learned_cards).most_common(15)
    baseline_real = baseline.get("average_real_combo_values", {})
    learned_real = learned.get("average_real_combo_values", {})

    return {
        "baseline_average_score": baseline_average,
        "learned_average_score": learned_average,
        "improvement_percentage": round(improvement, 2),
        "best_baseline_score": baseline.get("best_score", 0),
        "best_learned_score": learned.get("best_score", 0),
        "baseline_playable_hand_rate": _real_metric(baseline_real, "playable_hand_rate"),
        "learned_playable_hand_rate": _real_metric(learned_real, "playable_hand_rate"),
        "baseline_brick_rate": _real_metric(baseline_real, "brick_rate"),
        "learned_brick_rate": _real_metric(learned_real, "brick_rate"),
        "baseline_combo_line_score": _real_metric(baseline_real, "combo_line_score"),
        "learned_combo_line_score": _real_metric(learned_real, "combo_line_score"),
        "baseline_endboard_score": _real_metric(baseline_real, "average_endboard_score"),
        "learned_endboard_score": _real_metric(learned_real, "average_endboard_score"),
        "baseline_interruption_resilience": _real_metric(baseline_real, "interruption_resilience_score"),
        "learned_interruption_resilience": _real_metric(learned_real, "interruption_resilience_score"),
        "baseline_follow_up_score": _real_metric(baseline_real, "follow_up_score"),
        "learned_follow_up_score": _real_metric(learned_real, "follow_up_score"),
        "baseline_no_valid_line_rate": _real_metric(baseline_real, "no_valid_line_rate"),
        "learned_no_valid_line_rate": _real_metric(learned_real, "no_valid_line_rate"),
        "baseline_normalized_search_failure_rate": _real_metric(baseline_real, "normalized_search_failure_rate"),
        "learned_normalized_search_failure_rate": _real_metric(learned_real, "normalized_search_failure_rate"),
        "baseline_normalized_cost_failure_rate": _real_metric(baseline_real, "normalized_cost_failure_rate"),
        "learned_normalized_cost_failure_rate": _real_metric(learned_real, "normalized_cost_failure_rate"),
        "learning_improves_real_combo_metrics": real_combo_improved(baseline_real, learned_real),
        "baseline_package_quality_score": float(baseline.get("average_package_quality_score", 0) or 0),
        "learned_package_quality_score": float(learned.get("average_package_quality_score", 0) or 0),
        "baseline_side_deck_score": float(baseline.get("average_side_deck_score", 0) or 0),
        "learned_side_deck_score": float(learned.get("average_side_deck_score", 0) or 0),
        "baseline_matchup_coverage": float(baseline.get("average_matchup_coverage_score", 0) or 0),
        "learned_matchup_coverage": float(learned.get("average_matchup_coverage_score", 0) or 0),
        "baseline_going_first_side_score": float(baseline.get("average_going_first_side_score", 0) or 0),
        "learned_going_first_side_score": float(learned.get("average_going_first_side_score", 0) or 0),
        "baseline_going_second_side_score": float(baseline.get("average_going_second_side_score", 0) or 0),
        "learned_going_second_side_score": float(learned.get("average_going_second_side_score", 0) or 0),
        "learned_choke_stop_rate": _summary_metric(learned, "average_choke_stop_rate"),
        "learned_opponent_recovery_rate": _summary_metric(learned, "average_opponent_recovery_rate"),
        "learned_choke_coverage_score": _summary_metric(learned, "average_choke_coverage_score"),
        "learned_poor_interruption_count": _summary_metric(learned, "average_poor_interruption_count"),
        "learned_timing_precision_score": _summary_metric(learned, "average_timing_precision_score"),
        "learned_pivot_risk_score": _summary_metric(learned, "average_pivot_risk_score"),
        "learned_backup_line_success_rate": _summary_metric(learned, "average_backup_line_success_rate"),
        "learned_graph_stop_rate": _summary_metric(learned, "average_graph_stop_rate"),
        "learned_graph_pivot_rate": _summary_metric(learned, "average_graph_pivot_rate"),
        "learned_graph_endboard_reduction_score": _summary_metric(learned, "average_graph_endboard_reduction_score"),
        "learned_graph_timing_precision_score": _summary_metric(learned, "average_graph_timing_precision_score"),
        "learned_opponent_resource_valid_rate": _summary_metric(learned, "average_opponent_resource_valid_rate"),
        "learned_opponent_resource_failure_rate": _summary_metric(learned, "average_opponent_resource_failure_rate"),
        "baseline_game1_score": float(baseline.get("average_game1_score", 0) or 0),
        "learned_game1_score": float(learned.get("average_game1_score", 0) or 0),
        "baseline_post_side_score": float(baseline.get("average_post_side_score", 0) or 0),
        "learned_post_side_score": float(learned.get("average_post_side_score", 0) or 0),
        "baseline_post_side_delta": float(baseline.get("average_post_side_delta", 0) or 0),
        "learned_post_side_delta": float(learned.get("average_post_side_delta", 0) or 0),
        "baseline_post_side_valid_rate": float(baseline.get("post_side_valid_rate", 0) or 0),
        "learned_post_side_valid_rate": float(learned.get("post_side_valid_rate", 0) or 0),
        "baseline_valid_candidate_rate": float(baseline.get("average_valid_candidate_rate", 0) or 0),
        "learned_valid_candidate_rate": float(learned.get("average_valid_candidate_rate", 0) or 0),
        "baseline_side_optimization_success_rate": float(baseline.get("side_optimization_success_rate", 0) or 0),
        "learned_side_optimization_success_rate": float(learned.get("side_optimization_success_rate", 0) or 0),
        "learned_post_side_memory_used_rate": float(learned.get("post_side_memory_used_rate", 0) or 0),
        "learned_memory_post_side_delta_difference": float(learned.get("average_memory_post_side_delta_difference", 0) or 0),
        "matchup_aware_weighting_used": bool(learned.get("matchup_weighting_used")),
        "regression_risk_summary": regression_risk_summary(baseline, learned, improvement),
        "cards_learning_favored": favored,
        "cards_learning_avoided": avoided,
    }


def _real_metric(metrics: Any, key: str) -> float:
    if not isinstance(metrics, dict):
        return 0.0
    try:
        return float(metrics.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _summary_metric(metrics: dict[str, Any], key: str) -> float:
    observed = numeric_observation(metrics.get(key))
    return observed if observed is not None else 0.0


def real_combo_improved(baseline: Any, learned: Any) -> bool:
    playable_delta = _real_metric(learned, "playable_hand_rate") - _real_metric(baseline, "playable_hand_rate")
    combo_delta = _real_metric(learned, "combo_line_score") - _real_metric(baseline, "combo_line_score")
    brick_delta = _real_metric(learned, "brick_rate") - _real_metric(baseline, "brick_rate")
    return playable_delta >= 0 and combo_delta >= 0 and brick_delta <= 0


def regression_risk_summary(baseline: dict[str, Any], learned: dict[str, Any], score_improvement: float) -> dict[str, Any]:
    baseline_real = baseline.get("average_real_combo_values", {})
    learned_real = learned.get("average_real_combo_values", {})
    score_better = score_improvement >= 0
    playable_better = _real_metric(learned_real, "playable_hand_rate") >= _real_metric(baseline_real, "playable_hand_rate")
    brick_better = _real_metric(learned_real, "brick_rate") <= _real_metric(baseline_real, "brick_rate")
    package_better = float(learned.get("average_package_quality_score", 0) or 0) >= float(baseline.get("average_package_quality_score", 0) or 0)
    no_valid_better = _real_metric(learned_real, "no_valid_line_rate") <= _real_metric(baseline_real, "no_valid_line_rate")
    normalized_failures_better = (
        _real_metric(learned_real, "normalized_search_failure_rate")
        + _real_metric(learned_real, "normalized_cost_failure_rate")
        + _real_metric(learned_real, "normalized_material_failure_rate")
    ) <= (
        _real_metric(baseline_real, "normalized_search_failure_rate")
        + _real_metric(baseline_real, "normalized_cost_failure_rate")
        + _real_metric(baseline_real, "normalized_material_failure_rate")
    )
    positives = sum((score_better, playable_better, brick_better, package_better, no_valid_better, normalized_failures_better))
    recommendation = "accept" if positives >= 3 else "retest" if positives == 2 else "reject"
    return {
        "learned_better_than_baseline": score_better,
        "learned_worse_than_baseline": not score_better,
        "package_quality_improved": package_better,
        "brick_rate_improved": brick_better,
        "playable_rate_improved": playable_better,
        "no_valid_line_rate_improved": no_valid_better,
        "normalized_failures_improved": normalized_failures_better,
        "recommendation": recommendation,
    }


def save_report(report: dict[str, Any]) -> Path:
    EVALUATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype = report["config"]["archetype"].lower().replace(" ", "_")
    mode = report["config"]["mode"]
    path = EVALUATION_REPORTS_DIR / f"{timestamp}_{archetype}_{mode}_learning_eval.json"
    atomic_write_json(path, normalize_report("evaluation", report))
    return path


def print_report(report: dict[str, Any], path: Path) -> None:
    comparison = report["comparison"]
    baseline = report["baseline_summary"]
    learned = report["learned_summary"]

    print("\nLearning Evaluation Report")
    print(f"Baseline average score: {comparison['baseline_average_score']}")
    print(f"Learned average score: {comparison['learned_average_score']}")
    print(f"Improvement percentage: {comparison['improvement_percentage']}%")
    print(f"Baseline best score: {comparison['best_baseline_score']}")
    print(f"Learned best score: {comparison['best_learned_score']}")
    print(f"Learning improves real combo metrics: {comparison['learning_improves_real_combo_metrics']}")
    print(f"Baseline package quality: {comparison['baseline_package_quality_score']}")
    print(f"Learned package quality: {comparison['learned_package_quality_score']}")
    print(f"Baseline side deck score: {comparison['baseline_side_deck_score']}")
    print(f"Learned side deck score: {comparison['learned_side_deck_score']}")
    print(f"Baseline matchup coverage: {comparison['baseline_matchup_coverage']}")
    print(f"Learned matchup coverage: {comparison['learned_matchup_coverage']}")
    print(f"Learned choke stop rate: {display_opponent_metric(comparison.get('learned_choke_stop_rate'))}")
    print(f"Learned opponent recovery rate: {display_opponent_metric(comparison.get('learned_opponent_recovery_rate'))}")
    print(f"Learned timing precision score: {comparison.get('learned_timing_precision_score', 0)}")
    print(f"Learned pivot risk score: {comparison.get('learned_pivot_risk_score', 0)}")
    print(f"Learned graph stop rate: {display_opponent_metric(comparison.get('learned_graph_stop_rate'))}")
    print(f"Learned graph pivot rate: {display_opponent_metric(comparison.get('learned_graph_pivot_rate'))}")
    print(f"Matchup-aware weighting used: {comparison['matchup_aware_weighting_used']}")
    print(f"Baseline post-side score: {comparison['baseline_post_side_score']}")
    print(f"Learned post-side score: {comparison['learned_post_side_score']}")
    print(f"Baseline post-side delta: {comparison['baseline_post_side_delta']}")
    print(f"Learned post-side delta: {comparison['learned_post_side_delta']}")
    print(f"Learned post-side valid rate: {comparison['learned_post_side_valid_rate']}")
    print(f"Learned valid candidate rate: {comparison['learned_valid_candidate_rate']}")
    print(f"Learned side optimization success rate: {comparison['learned_side_optimization_success_rate']}")
    print(f"Learned post-side memory used rate: {comparison['learned_post_side_memory_used_rate']}")
    print(f"Memory vs no-memory post-side delta difference: {comparison['learned_memory_post_side_delta_difference']}")
    print(f"Regression recommendation: {comparison['regression_risk_summary']['recommendation']}")

    print("\nReal combo metrics:")
    print(f"- playable hand rate: baseline {comparison['baseline_playable_hand_rate']} | learned {comparison['learned_playable_hand_rate']}")
    print(f"- brick rate: baseline {comparison['baseline_brick_rate']} | learned {comparison['learned_brick_rate']}")
    print(f"- combo line score: baseline {comparison['baseline_combo_line_score']} | learned {comparison['learned_combo_line_score']}")
    print(f"- endboard score: baseline {comparison['baseline_endboard_score']} | learned {comparison['learned_endboard_score']}")
    print(f"- interruption resilience: baseline {comparison['baseline_interruption_resilience']} | learned {comparison['learned_interruption_resilience']}")
    print(f"- follow-up score: baseline {comparison['baseline_follow_up_score']} | learned {comparison['learned_follow_up_score']}")

    print("\nPackage counts:")
    print(f"- baseline: {baseline.get('package_counts', {})}")
    print(f"- learned: {learned.get('package_counts', {})}")

    print("\nPackage quota violations:")
    print(f"- baseline: {baseline.get('package_quota_violations', []) or 'None'}")
    print(f"- learned: {learned.get('package_quota_violations', []) or 'None'}")

    print("\nAverage combo values:")
    for key in sorted(set(baseline["average_combo_values"]) | set(learned["average_combo_values"])):
        print(f"- {key}: baseline {baseline['average_combo_values'].get(key, 0)} | learned {learned['average_combo_values'].get(key, 0)}")

    print("\nAverage score breakdown:")
    for key in sorted(set(baseline["average_score_breakdown"]) | set(learned["average_score_breakdown"])):
        print(f"- {key}: baseline {baseline['average_score_breakdown'].get(key, 0)} | learned {learned['average_score_breakdown'].get(key, 0)}")

    print("\nCards learning favored:")
    for card, count in comparison["cards_learning_favored"]:
        print(f"- {card}: +{count}")

    print("\nCards learning avoided:")
    for card, count in comparison["cards_learning_avoided"]:
        print(f"- {card}: -{count}")

    print("\nMost common learned critique issues:")
    for issue, count in learned["most_common_critique_issues"]:
        print(f"- {issue}: {count}")

    print("\nBlocked-card violations:")
    all_violations = baseline["blocked_card_violations"] + learned["blocked_card_violations"]
    if all_violations:
        for violation, count in all_violations:
            print(f"- {violation}: {count}")
    else:
        print("- None")

    print("\nBest baseline deck")
    print("Main Deck:")
    for card in baseline["best_deck"]["main_deck"]:
        print(f"- {card}")
    print("Extra Deck:")
    for card in baseline["best_deck"]["extra_deck"]:
        print(f"- {card}")

    print("\nBest learned deck")
    print("Main Deck:")
    for card in learned["best_deck"]["main_deck"]:
        print(f"- {card}")
    print("Extra Deck:")
    for card in learned["best_deck"]["extra_deck"]:
        print(f"- {card}")

    print(f"\nSaved report: {path}")


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")

    database = CardDatabase()
    startup_safety_cleanup()
    try:
        database.refresh_on_startup()
    except RuntimeError:
        pass

    baseline_results = run_batch(database, args.archetype, args.mode, args.runs, use_learning=False, matchup=args.matchup, going=args.going)
    learned_results = run_batch(database, args.archetype, args.mode, args.runs, use_learning=True, matchup=args.matchup, going=args.going)
    baseline_summary = summarize_batch(baseline_results)
    learned_summary = summarize_batch(learned_results)
    comparison = compare_summaries(baseline_summary, learned_summary)

    report = {
        "config": {
            "archetype": args.archetype,
            "mode": args.mode,
            "runs": args.runs,
            "matchup": args.matchup,
            "going": args.going,
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison": comparison,
        "baseline_summary": baseline_summary,
        "learned_summary": learned_summary,
        "baseline_runs": baseline_results,
        "learned_runs": learned_results,
    }
    path = save_report(report)
    print_report(report, path)


if __name__ == "__main__":
    main()
