from __future__ import annotations

from typing import Any

COMBO_METRICS = (
    "playable_hand_rate",
    "brick_rate",
    "starter_count",
    "extender_count",
    "interruption_count",
    "average_endboard_score",
    "interruption_resilience_score",
    "follow_up_score",
)

GRAPH_METRICS = (
    "graph_stop_rate",
    "graph_pivot_rate",
    "graph_endboard_reduction_score",
    "graph_best_interruption_count",
    "graph_poor_interruption_count",
    "graph_timing_precision_score",
)

RESOURCE_METRICS = (
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_pivot_success_rate",
    "opponent_backup_success_rate",
    "opponent_missing_card_failures",
    "opponent_missing_extra_failures",
    "opponent_once_per_turn_failures",
    "opponent_normal_summon_failures",
)

SIDE_METRICS = (
    "side_deck_score",
    "matchup_coverage_score",
    "going_first_side_score",
    "going_second_side_score",
    "post_side_score",
    "post_side_delta",
    "valid_candidate_rate",
    "optimization_used",
    "post_side_memory_used",
)

OPPONENT_METRICS = (
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
)

MONTE_CARLO_PROBABILITY_METRICS = (
    "opponent_starter_open_rate",
    "opponent_extender_open_rate",
    "opponent_interruption_open_rate",
    "opponent_brick_rate",
    "probability_weighted_resource_valid_rate",
    "probability_weighted_stop_rate",
    "probability_weighted_pivot_rate",
    "probability_weighted_backup_rate",
)

MATRIX_SUMMARY_METRICS = (
    "cell_count",
    "failed_cell_count",
    "failed_run_count",
    "failure_rate",
    "average_final_score",
    "score_stddev",
    "average_post_side_score",
    "average_post_side_delta",
    "post_side_valid_rate",
    "average_valid_candidate_rate",
)

REPORT_REQUIRED_METRICS = {
    "matchup_matrix": ("summary", "rankings", "cells"),
    "post_side": ("summary", "runs"),
    "opponent_analysis": ("opponent_profile", "post_side_score", "side_in", "side_out"),
    "training": ("summary", "results"),
    "evaluation": ("comparison",),
}


def metric_group(name: str) -> tuple[str, ...]:
    groups = {
        "combo": COMBO_METRICS,
        "graph": GRAPH_METRICS,
        "resource": RESOURCE_METRICS,
        "side": SIDE_METRICS,
        "opponent": OPPONENT_METRICS,
        "probability": MONTE_CARLO_PROBABILITY_METRICS,
        "matrix_summary": MATRIX_SUMMARY_METRICS,
    }
    return groups[name]


def extract_metrics(primary: dict[str, Any], fallback: dict[str, Any] | None, keys: tuple[str, ...], default: Any = 0) -> dict[str, Any]:
    fallback = fallback or {}
    return {key: primary[key] if key in primary else fallback[key] if key in fallback else default for key in keys}


def missing_required_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]
