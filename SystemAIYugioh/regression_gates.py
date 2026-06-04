from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from SystemAIYugioh.opponent_signal_sentinel import is_opponent_signal_sentinel, sentinel_reason
from config.settings import (
    REGRESSION_MAX_BRICK_INCREASE,
    REGRESSION_MAX_SCORE_DROP,
    REGRESSION_MIN_POST_SIDE_DELTA,
    REGRESSION_MIN_VALID_CANDIDATE_RATE,
)


@dataclass(frozen=True)
class RegressionGateConfig:
    max_average_score_drop: float = REGRESSION_MAX_SCORE_DROP
    max_playable_rate_drop: float = 0.12
    max_brick_rate_increase: float = REGRESSION_MAX_BRICK_INCREASE
    max_package_violation_rate: float = 0.35
    min_package_quality_score: float = 45.0
    max_normal_summon_conflict_increase: float = 0.12
    max_once_per_turn_conflict_increase: float = 0.12
    max_dead_duplicate_rate_increase: float = 0.12
    max_payoff_enabler_mismatch_increase: float = 0.12
    max_best_line_score_drop: float = 2.0
    max_graph_valid_line_rate_drop: float = 0.12
    max_graph_line_score_drop: float = 2.0
    max_graph_failed_line_rate_increase: float = 0.15
    max_graph_risk_score_increase: float = 1.5
    max_resource_valid_line_rate_drop: float = 0.12
    max_material_failure_rate_increase: float = 0.15
    max_search_failure_rate_increase: float = 0.15
    max_extra_deck_failure_rate_increase: float = 0.15
    max_cost_failure_rate_increase: float = 0.15
    max_typed_material_valid_rate_drop: float = 0.12
    max_typed_material_failure_rate_increase: float = 0.15
    max_no_valid_line_rate_increase: float = 0.15
    max_best_line_failure_rate_increase: float = 0.15
    max_normalized_failure_rate_increase: float = 0.15
    max_cost_condition_valid_rate_drop: float = 0.12
    max_cost_condition_failure_increase: float = 0.15
    max_branch_valid_rate_drop: float = 0.15
    max_branch_failure_rate_increase: float = 0.15
    max_history_failure_rate_increase: float = 0.15
    max_resilience_score_drop: float = 1.5
    max_interrupted_success_rate_drop: float = 0.12
    max_interruption_risk_increase: float = 1.5
    max_vulnerability_rate_increase: float = 0.15
    max_side_deck_score_drop: float = 8.0
    max_matchup_coverage_drop: float = 6.0
    max_post_side_score_drop: float = 8.0
    min_post_side_delta: float = REGRESSION_MIN_POST_SIDE_DELTA
    min_post_side_valid_rate: float = 0.7
    min_valid_candidate_rate: float = REGRESSION_MIN_VALID_CANDIDATE_RATE
    min_side_optimization_success_rate: float = 0.7
    min_memory_delta_difference: float = -4.0
    max_matrix_score_stddev: float = 28.0
    max_matrix_blocked_violations: float = 0.0
    min_curated_memory_delta: float = -4.0
    min_curated_memory_valid_rate: float = 0.7
    max_choke_stop_rate_drop: float = 0.15
    max_opponent_recovery_rate_increase: float = 0.15
    max_poor_interruption_count_increase: float = 3.0
    max_timing_precision_drop: float = 0.15
    max_pivot_risk_increase: float = 0.15
    max_backup_line_success_increase: float = 0.15
    max_late_interruption_risk: float = 0.8
    max_graph_stop_rate_drop: float = 0.15
    max_graph_pivot_rate_increase: float = 0.15
    max_graph_endboard_reduction_drop: float = 0.15
    max_graph_poor_interruption_increase: float = 3.0
    min_opponent_resource_valid_rate: float = 0.35
    max_opponent_resource_failure_rate: float = 0.65


DEFAULT_CONFIG = RegressionGateConfig()

MATRIX_DEGRADATION_KEYS = (
    "score_stddev",
    "blocked_card_violation_count",
    "average_side_deck_score",
    "average_matchup_coverage_score",
    "average_resilience_score",
    "average_post_side_score",
    "average_post_side_delta",
    "post_side_valid_rate",
    "average_valid_candidate_rate",
    "side_optimization_success_rate",
    "average_memory_aided_post_side_delta",
)

TRAINING_DEGRADATION_KEYS = (
    "average_score",
    "average_package_quality_score",
    "average_side_deck_score",
    "average_matchup_coverage_score",
    "average_post_side_score",
    "average_post_side_delta",
    "post_side_valid_rate",
    "average_valid_candidate_rate",
    "side_optimization_success_rate",
    "average_memory_post_side_delta_difference",
    "average_choke_stop_rate",
    "average_opponent_recovery_rate",
    "average_poor_interruption_count",
    "average_timing_precision_score",
    "average_pivot_risk_score",
    "average_backup_line_success_rate",
    "average_late_interruption_risk",
    "average_graph_stop_rate",
    "average_graph_pivot_rate",
    "average_graph_endboard_reduction_score",
    "average_graph_poor_interruption_count",
    "average_opponent_resource_valid_rate",
    "average_opponent_resource_failure_rate",
)

REAL_COMBO_DEGRADATION_KEYS = (
    "playable_hand_rate",
    "brick_rate",
    "best_line_average_score",
    "graph_valid_line_rate",
    "graph_average_line_score",
    "graph_failed_line_rate",
    "graph_average_risk_score",
    "resource_valid_line_rate",
    "no_valid_line_rate",
    "best_line_failure_rate",
    "cost_condition_valid_rate",
    "branch_valid_rate",
    "no_valid_branch_rate",
    "resilience_score",
    "interrupted_line_success_rate",
    "average_interruption_risk",
    "typed_material_valid_rate",
)


class NumericGateValue(float):
    def __new__(cls, value: float, state: str, reason: str = ""):
        obj = float.__new__(cls, value)
        obj.state = state
        obj.reason = reason
        return obj

    @property
    def value(self) -> float:
        return float(self)

    @property
    def is_numeric(self) -> bool:
        return self.state == "numeric"

    @property
    def is_zero(self) -> bool:
        return self.is_numeric and self.value == 0.0


def evaluate_matchup_matrix_update(
    matrix_summary: dict[str, Any],
    previous_profile: dict[str, Any],
    config: RegressionGateConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    reasons: list[str] = []
    metric_degradation_reasons = _metric_degradation_reasons(
        matrix_summary,
        previous_profile.get("summary", {}) if isinstance(previous_profile, dict) else {},
        MATRIX_DEGRADATION_KEYS,
    )
    score_stddev = _number(matrix_summary.get("score_stddev"))
    if score_stddev > config.max_matrix_score_stddev:
        reasons.append(f"matrix average is too unstable: score stddev {score_stddev} > {config.max_matrix_score_stddev}")

    blocked = _number(matrix_summary.get("blocked_card_violation_count"))
    if blocked > config.max_matrix_blocked_violations:
        reasons.append("blocked-card violations detected in matchup matrix")

    previous_summary = previous_profile.get("summary", {}) if isinstance(previous_profile, dict) else {}
    if not isinstance(previous_summary, dict):
        previous_summary = {}

    side_score = _number(matrix_summary.get("average_side_deck_score"))
    previous_side_score = _number(previous_summary.get("average_side_deck_score"))
    if _dropped_below(side_score, previous_side_score, config.max_side_deck_score_drop):
        reasons.append(f"matrix side deck score dropped too far: {side_score} < {round(previous_side_score - config.max_side_deck_score_drop, 2)}")

    coverage = _number(matrix_summary.get("average_matchup_coverage_score"))
    previous_coverage = _number(previous_summary.get("average_matchup_coverage_score"))
    if _dropped_below(coverage, previous_coverage, config.max_matchup_coverage_drop):
        reasons.append(f"matrix matchup coverage dropped too far: {coverage} < {round(previous_coverage - config.max_matchup_coverage_drop, 2)}")

    resilience = _number(matrix_summary.get("average_resilience_score"))
    previous_resilience = _number(previous_summary.get("average_resilience_score"))
    if _dropped_below(resilience, previous_resilience, config.max_resilience_score_drop):
        reasons.append(f"matrix resilience dropped too far: {resilience} < {round(previous_resilience - config.max_resilience_score_drop, 2)}")

    post_side_score = _number(matrix_summary.get("average_post_side_score"))
    previous_post_side_score = _number(previous_summary.get("average_post_side_score"))
    if _dropped_below(post_side_score, previous_post_side_score, config.max_post_side_score_drop):
        reasons.append(f"matrix post-side score dropped too far: {post_side_score} < {round(previous_post_side_score - config.max_post_side_score_drop, 2)}")
    if _below_threshold(_number(matrix_summary.get("average_post_side_delta")), config.min_post_side_delta):
        reasons.append("matrix post-side delta is strongly negative")
    if _below_threshold(_number(matrix_summary.get("post_side_valid_rate")), config.min_post_side_valid_rate):
        reasons.append("matrix side plans are invalid too often")
    if _below_threshold(_number(matrix_summary.get("average_valid_candidate_rate")), config.min_valid_candidate_rate):
        reasons.append("matrix valid side-plan candidate rate is too low")
    if _below_threshold(_number(matrix_summary.get("side_optimization_success_rate")), config.min_side_optimization_success_rate):
        reasons.append("matrix side optimization fails too often")
    if _below_threshold(_number(matrix_summary.get("average_memory_aided_post_side_delta")), config.min_memory_delta_difference):
        reasons.append("matrix side memory worsened post-side results too much")

    return {
        "accepted": not reasons,
        "reasons": reasons,
        "reporting_reasons": metric_degradation_reasons,
        "metric_degradation_reasons": metric_degradation_reasons,
        "metrics": {
            "score_stddev": score_stddev,
            "blocked_card_violation_count": blocked,
            "average_side_deck_score": side_score,
            "average_matchup_coverage_score": coverage,
            "average_resilience_score": resilience,
            "average_post_side_score": post_side_score,
            "average_post_side_delta": _number(matrix_summary.get("average_post_side_delta")),
            "post_side_valid_rate": _number(matrix_summary.get("post_side_valid_rate")),
            "average_valid_candidate_rate": _number(matrix_summary.get("average_valid_candidate_rate")),
            "side_optimization_success_rate": _number(matrix_summary.get("side_optimization_success_rate")),
            "average_memory_aided_post_side_delta": _number(matrix_summary.get("average_memory_aided_post_side_delta")),
        },
    }


def evaluate_training_batch(
    summary: dict[str, Any],
    previous_profile: dict[str, Any],
    config: RegressionGateConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    reasons: list[str] = []
    metric_degradation_reasons = _metric_degradation_reasons(summary, previous_profile, TRAINING_DEGRADATION_KEYS)
    successful_runs = _number(summary.get("successful_runs"))
    if successful_runs <= 0:
        reasons.append("no successful training runs")

    average_score = _number(summary.get("average_score"))
    previous_average = _number(previous_profile.get("average_score"))
    if _dropped_below(average_score, previous_average, config.max_average_score_drop):
        reasons.append(
            f"average score dropped too far: {average_score} < {round(previous_average - config.max_average_score_drop, 2)}"
        )

    real_metrics = summary.get("average_real_combo_values", {})
    if not isinstance(real_metrics, dict):
        real_metrics = {}
    previous_real = previous_profile.get("average_real_combo_report_values", {})
    if not isinstance(previous_real, dict):
        previous_real = {}
    metric_degradation_reasons.extend(
        _metric_degradation_reasons(real_metrics, previous_real, REAL_COMBO_DEGRADATION_KEYS, prefix="average_real_combo_values.")
    )

    playable_rate = _number(real_metrics.get("playable_hand_rate"))
    previous_playable = _number(previous_real.get("playable_hand_rate"))
    if _dropped_below(playable_rate, previous_playable, config.max_playable_rate_drop):
        reasons.append(
            f"playable hand rate dropped too far: {playable_rate} < {round(previous_playable - config.max_playable_rate_drop, 4)}"
        )

    brick_rate = _number(real_metrics.get("brick_rate"))
    previous_brick = _number(previous_real.get("brick_rate"))
    if _increased_above(brick_rate, previous_brick, config.max_brick_rate_increase):
        reasons.append(
            f"brick rate increased too far: {brick_rate} > {round(previous_brick + config.max_brick_rate_increase, 4)}"
        )

    blocked_violations = summary.get("blocked_card_violations", [])
    if blocked_violations:
        reasons.append("blocked-card violations detected")
    side_plan_violations = summary.get("side_plan_blocked_card_violations", [])
    if side_plan_violations:
        reasons.append("side plan blocked-card violations detected")

    package_violations = summary.get("package_quota_violations", [])
    violation_count = sum(_number(item[1]) for item in package_violations if isinstance(item, (list, tuple)) and len(item) > 1)
    violation_rate = violation_count / max(successful_runs, 1.0)
    if violation_rate > config.max_package_violation_rate:
        reasons.append(f"package quota violations too frequent: {round(violation_rate, 4)}")

    package_quality_score = _number(summary.get("average_package_quality_score"))
    if _below_threshold(package_quality_score, config.min_package_quality_score):
        reasons.append(
            f"package quality too low: {package_quality_score} < {config.min_package_quality_score}"
        )
    side_score = _number(summary.get("average_side_deck_score"))
    previous_side_score = _number(previous_profile.get("average_side_deck_score"))
    if _dropped_below(side_score, previous_side_score, config.max_side_deck_score_drop):
        reasons.append(f"side deck score dropped too far: {side_score} < {round(previous_side_score - config.max_side_deck_score_drop, 2)}")
    matchup_coverage = _number(summary.get("average_matchup_coverage_score"))
    previous_matchup_coverage = _number(previous_profile.get("average_matchup_coverage_score"))
    if _dropped_below(matchup_coverage, previous_matchup_coverage, config.max_matchup_coverage_drop):
        reasons.append(f"matchup coverage score dropped too far: {matchup_coverage} < {round(previous_matchup_coverage - config.max_matchup_coverage_drop, 2)}")

    post_side_score = _number(summary.get("average_post_side_score"))
    previous_post_side_score = _number(previous_profile.get("average_post_side_score"))
    if _dropped_below(post_side_score, previous_post_side_score, config.max_post_side_score_drop):
        reasons.append(f"post-side score dropped too far: {post_side_score} < {round(previous_post_side_score - config.max_post_side_score_drop, 2)}")
    if _below_threshold(_number(summary.get("average_post_side_delta")), config.min_post_side_delta):
        reasons.append("post-side delta is strongly negative")
    post_side_valid_rate = _number(summary.get("post_side_valid_rate"))
    if _is_numeric(post_side_valid_rate) and post_side_valid_rate < config.min_post_side_valid_rate:
        reasons.append(f"side plan validity too low: {post_side_valid_rate} < {config.min_post_side_valid_rate}")
    if _below_threshold(_number(summary.get("average_valid_candidate_rate")), config.min_valid_candidate_rate):
        reasons.append("valid side-plan candidate rate is too low")
    if _below_threshold(_number(summary.get("side_optimization_success_rate")), config.min_side_optimization_success_rate):
        reasons.append("side optimization fails too often")
    if _below_threshold(_number(summary.get("average_memory_post_side_delta_difference")), config.min_memory_delta_difference):
        reasons.append("side memory worsened evaluation versus no-memory baseline")
    previous_choke_stop = _number(previous_profile.get("average_choke_stop_rate"))
    choke_stop = _number(summary.get("average_choke_stop_rate"))
    if _dropped_below(choke_stop, previous_choke_stop, config.max_choke_stop_rate_drop):
        reasons.append("choke stop rate dropped too much")
    previous_recovery = _number(previous_profile.get("average_opponent_recovery_rate"))
    recovery = _number(summary.get("average_opponent_recovery_rate"))
    if _increased_above(recovery, previous_recovery, config.max_opponent_recovery_rate_increase):
        reasons.append("opponent recovery rate rose too much")
    previous_poor = _number(previous_profile.get("average_poor_interruption_count"))
    poor = _number(summary.get("average_poor_interruption_count"))
    if _increased_above(poor, previous_poor, config.max_poor_interruption_count_increase):
        reasons.append("poor interruption count rose too much")
    previous_timing = _number(previous_profile.get("average_timing_precision_score"))
    timing = _number(summary.get("average_timing_precision_score"))
    if _dropped_below(timing, previous_timing, config.max_timing_precision_drop):
        reasons.append("timing precision score dropped too much")
    previous_pivot = _number(previous_profile.get("average_pivot_risk_score"))
    pivot = _number(summary.get("average_pivot_risk_score"))
    if _increased_above(pivot, previous_pivot, config.max_pivot_risk_increase):
        reasons.append("pivot risk score rose too much")
    previous_backup = _number(previous_profile.get("average_backup_line_success_rate"))
    backup = _number(summary.get("average_backup_line_success_rate"))
    if _increased_above(backup, previous_backup, config.max_backup_line_success_increase):
        reasons.append("backup line success rate rose too much")
    if _above_threshold(_number(summary.get("average_late_interruption_risk")), config.max_late_interruption_risk):
        reasons.append("side plans rely too heavily on late timing windows")
    previous_graph_stop = _number(previous_profile.get("average_graph_stop_rate"))
    graph_stop = _number(summary.get("average_graph_stop_rate"))
    if _dropped_below(graph_stop, previous_graph_stop, config.max_graph_stop_rate_drop):
        reasons.append("graph stop rate dropped too much")
    previous_graph_pivot = _number(previous_profile.get("average_graph_pivot_rate"))
    graph_pivot = _number(summary.get("average_graph_pivot_rate"))
    if _increased_above(graph_pivot, previous_graph_pivot, config.max_graph_pivot_rate_increase):
        reasons.append("graph pivot rate rose too much")
    previous_graph_reduction = _number(previous_profile.get("average_graph_endboard_reduction_score"))
    graph_reduction = _number(summary.get("average_graph_endboard_reduction_score"))
    if _dropped_below(graph_reduction, previous_graph_reduction, config.max_graph_endboard_reduction_drop):
        reasons.append("graph endboard reduction score dropped too much")
    previous_graph_poor = _number(previous_profile.get("average_graph_poor_interruption_count"))
    graph_poor = _number(summary.get("average_graph_poor_interruption_count"))
    if _increased_above(graph_poor, previous_graph_poor, config.max_graph_poor_interruption_increase):
        reasons.append("graph poor interruption count rose too much")
    resource_valid = _number(summary.get("average_opponent_resource_valid_rate"))
    resource_failure = _number(summary.get("average_opponent_resource_failure_rate"))
    if _is_numeric(resource_valid) and resource_valid < config.min_opponent_resource_valid_rate:
        reasons.append("opponent resource valid rate dropped below sanity threshold")
    if _above_threshold(resource_failure, config.max_opponent_resource_failure_rate):
        reasons.append("opponent graph resource failures exceed sanity threshold")

    conflict_checks = (
        ("normal_summon_conflict_rate", config.max_normal_summon_conflict_increase, "normal summon conflict rate"),
        ("once_per_turn_conflict_rate", config.max_once_per_turn_conflict_increase, "once-per-turn conflict rate"),
        ("dead_duplicate_rate", config.max_dead_duplicate_rate_increase, "dead duplicate rate"),
        ("payoff_without_enabler_rate", config.max_payoff_enabler_mismatch_increase, "payoff without enabler rate"),
        ("enabler_without_payoff_rate", config.max_payoff_enabler_mismatch_increase, "enabler without payoff rate"),
    )
    for key, threshold, label in conflict_checks:
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, threshold):
            reasons.append(f"{label} rose too much: {current} > {round(previous + threshold, 4)}")

    best_line_score = _number(real_metrics.get("best_line_average_score"))
    previous_best_line_score = _number(previous_real.get("best_line_average_score"))
    if _dropped_below(best_line_score, previous_best_line_score, config.max_best_line_score_drop):
        reasons.append(
            f"best-line average score dropped too far: {best_line_score} < {round(previous_best_line_score - config.max_best_line_score_drop, 2)}"
        )

    graph_valid_rate = _number(real_metrics.get("graph_valid_line_rate"))
    previous_graph_valid = _number(previous_real.get("graph_valid_line_rate"))
    if _dropped_below(graph_valid_rate, previous_graph_valid, config.max_graph_valid_line_rate_drop):
        reasons.append(f"graph valid line rate dropped too far: {graph_valid_rate} < {round(previous_graph_valid - config.max_graph_valid_line_rate_drop, 4)}")
    graph_line_score = _number(real_metrics.get("graph_average_line_score"))
    previous_graph_line_score = _number(previous_real.get("graph_average_line_score"))
    if _dropped_below(graph_line_score, previous_graph_line_score, config.max_graph_line_score_drop):
        reasons.append(f"graph line score dropped too far: {graph_line_score} < {round(previous_graph_line_score - config.max_graph_line_score_drop, 2)}")
    graph_failed_rate = _number(real_metrics.get("graph_failed_line_rate"))
    previous_graph_failed = _number(previous_real.get("graph_failed_line_rate"))
    if _increased_above(graph_failed_rate, previous_graph_failed, config.max_graph_failed_line_rate_increase):
        reasons.append(f"graph failed line rate rose too much: {graph_failed_rate} > {round(previous_graph_failed + config.max_graph_failed_line_rate_increase, 4)}")
    graph_risk = _number(real_metrics.get("graph_average_risk_score"))
    previous_graph_risk = _number(previous_real.get("graph_average_risk_score"))
    if _increased_above(graph_risk, previous_graph_risk, config.max_graph_risk_score_increase):
        reasons.append(f"graph risk rose too much: {graph_risk} > {round(previous_graph_risk + config.max_graph_risk_score_increase, 2)}")
    failure_reason = real_metrics.get("most_common_graph_failure_reason")
    if isinstance(failure_reason, str) and "active lock invalidates" in failure_reason:
        reasons.append(f"major graph structural failure: {failure_reason}")

    resource_valid = _number(real_metrics.get("resource_valid_line_rate"))
    previous_resource_valid = _number(previous_real.get("resource_valid_line_rate"))
    if _dropped_below(resource_valid, previous_resource_valid, config.max_resource_valid_line_rate_drop):
        reasons.append(f"resource valid line rate dropped too far: {resource_valid} < {round(previous_resource_valid - config.max_resource_valid_line_rate_drop, 4)}")
    no_valid_line_rate = _number(real_metrics.get("no_valid_line_rate"))
    previous_no_valid_line_rate = _number(previous_real.get("no_valid_line_rate"))
    if _increased_above(no_valid_line_rate, previous_no_valid_line_rate, config.max_no_valid_line_rate_increase):
        reasons.append(f"no-valid-line rate rose too much: {no_valid_line_rate} > {round(previous_no_valid_line_rate + config.max_no_valid_line_rate_increase, 4)}")

    best_line_failure_rate = _number(real_metrics.get("best_line_failure_rate"))
    previous_best_line_failure_rate = _number(previous_real.get("best_line_failure_rate"))
    if _increased_above(best_line_failure_rate, previous_best_line_failure_rate, config.max_best_line_failure_rate_increase):
        reasons.append(f"best-line failure rate rose too much: {best_line_failure_rate} > {round(previous_best_line_failure_rate + config.max_best_line_failure_rate_increase, 4)}")

    normalized_failure_checks = (
        ("normalized_material_failure_rate", config.max_normalized_failure_rate_increase, "normalized material failure rate"),
        ("normalized_search_failure_rate", config.max_normalized_failure_rate_increase, "normalized search failure rate"),
        ("normalized_extra_deck_failure_rate", config.max_normalized_failure_rate_increase, "normalized extra deck failure rate"),
        ("normalized_cost_failure_rate", config.max_normalized_failure_rate_increase, "normalized cost failure rate"),
    )
    for key, threshold, label in normalized_failure_checks:
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, threshold):
            reasons.append(f"{label} rose too much: {current} > {round(previous + threshold, 4)}")
    cost_condition_valid = _number(real_metrics.get("cost_condition_valid_rate"))
    previous_cost_condition_valid = _number(previous_real.get("cost_condition_valid_rate"))
    if _dropped_below(cost_condition_valid, previous_cost_condition_valid, config.max_cost_condition_valid_rate_drop):
        reasons.append(f"cost/condition valid rate dropped too far: {cost_condition_valid} < {round(previous_cost_condition_valid - config.max_cost_condition_valid_rate_drop, 4)}")
    for key, label in (
        ("cost_failure_rate_normalized", "normalized cost failure rate"),
        ("condition_failure_rate_normalized", "normalized condition failure rate"),
        ("reveal_cost_failure_rate", "reveal cost failure rate"),
        ("discard_cost_failure_rate", "discard cost failure rate"),
        ("gy_condition_failure_rate", "GY condition failure rate"),
        ("control_condition_failure_rate", "control condition failure rate"),
    ):
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, config.max_cost_condition_failure_increase):
            reasons.append(f"{label} rose too much: {current} > {round(previous + config.max_cost_condition_failure_increase, 4)}")
    branch_valid = _number(real_metrics.get("branch_valid_rate"))
    previous_branch_valid = _number(previous_real.get("branch_valid_rate"))
    if _dropped_below(branch_valid, previous_branch_valid, config.max_branch_valid_rate_drop):
        reasons.append(f"branch valid rate dropped too far: {branch_valid} < {round(previous_branch_valid - config.max_branch_valid_rate_drop, 4)}")
    no_valid_branch = _number(real_metrics.get("no_valid_branch_rate"))
    previous_no_valid_branch = _number(previous_real.get("no_valid_branch_rate"))
    if _increased_above(no_valid_branch, previous_no_valid_branch, config.max_branch_failure_rate_increase):
        reasons.append(f"no-valid-branch rate rose too much: {no_valid_branch} > {round(previous_no_valid_branch + config.max_branch_failure_rate_increase, 4)}")
    for key, label in (
        ("history_condition_failure_rate", "history condition failure rate"),
        ("summon_history_failure_rate", "summon history failure rate"),
        ("gy_history_failure_rate", "GY history failure rate"),
        ("activation_history_failure_rate", "activation history failure rate"),
        ("resolution_history_failure_rate", "resolution history failure rate"),
    ):
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, config.max_history_failure_rate_increase):
            reasons.append(f"{label} rose too much: {current} > {round(previous + config.max_history_failure_rate_increase, 4)}")
    resilience_score = _number(real_metrics.get("resilience_score"))
    previous_resilience_score = _number(previous_real.get("resilience_score"))
    if _dropped_below(resilience_score, previous_resilience_score, config.max_resilience_score_drop):
        reasons.append(f"resilience score dropped too far: {resilience_score} < {round(previous_resilience_score - config.max_resilience_score_drop, 2)}")
    interrupted_success = _number(real_metrics.get("interrupted_line_success_rate"))
    previous_interrupted_success = _number(previous_real.get("interrupted_line_success_rate"))
    if _dropped_below(interrupted_success, previous_interrupted_success, config.max_interrupted_success_rate_drop):
        reasons.append(f"interrupted line success rate dropped too far: {interrupted_success} < {round(previous_interrupted_success - config.max_interrupted_success_rate_drop, 4)}")
    interruption_risk = _number(real_metrics.get("average_interruption_risk"))
    previous_interruption_risk = _number(previous_real.get("average_interruption_risk"))
    if _increased_above(interruption_risk, previous_interruption_risk, config.max_interruption_risk_increase):
        reasons.append(f"average interruption risk rose too much: {interruption_risk} > {round(previous_interruption_risk + config.max_interruption_risk_increase, 2)}")
    for key, label in (
        ("ash_vulnerability_rate", "Ash vulnerability rate"),
        ("imperm_vulnerability_rate", "Imperm vulnerability rate"),
        ("droll_vulnerability_rate", "Droll vulnerability rate"),
    ):
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, config.max_vulnerability_rate_increase):
            reasons.append(f"{label} rose too much: {current} > {round(previous + config.max_vulnerability_rate_increase, 4)}")
    typed_valid = _number(real_metrics.get("typed_material_valid_rate"))
    previous_typed_valid = _number(previous_real.get("typed_material_valid_rate"))
    if _dropped_below(typed_valid, previous_typed_valid, config.max_typed_material_valid_rate_drop):
        reasons.append(f"typed material valid rate dropped too far: {typed_valid} < {round(previous_typed_valid - config.max_typed_material_valid_rate_drop, 4)}")
    for key, label in (
        ("synchro_material_failure_rate", "synchro material failure rate"),
        ("fusion_material_failure_rate", "fusion material failure rate"),
        ("ritual_material_failure_rate", "ritual material failure rate"),
        ("named_material_failure_rate", "named material failure rate"),
    ):
        current = _number(real_metrics.get(key))
        previous = _number(previous_real.get(key))
        if _increased_above(current, previous, config.max_typed_material_failure_rate_increase):
            reasons.append(f"{label} rose too much: {current} > {round(previous + config.max_typed_material_failure_rate_increase, 4)}")

    return {
        "accepted": not reasons,
        "reasons": reasons,
        "reporting_reasons": metric_degradation_reasons,
        "metric_degradation_reasons": metric_degradation_reasons,
        "metrics": {
            "average_score": average_score,
            "previous_average_score": previous_average,
            "playable_hand_rate": playable_rate,
            "previous_playable_hand_rate": previous_playable,
            "brick_rate": brick_rate,
            "previous_brick_rate": previous_brick,
            "package_violation_rate": round(violation_rate, 4),
            "package_quality_score": package_quality_score,
            "side_deck_score": side_score,
            "matchup_coverage_score": matchup_coverage,
            "post_side_score": post_side_score,
            "post_side_delta": _number(summary.get("average_post_side_delta")),
            "post_side_valid_rate": post_side_valid_rate,
            "valid_candidate_rate": _number(summary.get("average_valid_candidate_rate")),
            "side_optimization_success_rate": _number(summary.get("side_optimization_success_rate")),
            "memory_post_side_delta_difference": _number(summary.get("average_memory_post_side_delta_difference")),
            "choke_stop_rate": _number(summary.get("average_choke_stop_rate")),
            "opponent_recovery_rate": _number(summary.get("average_opponent_recovery_rate")),
            "poor_interruption_count": _number(summary.get("average_poor_interruption_count")),
            "timing_precision_score": _number(summary.get("average_timing_precision_score")),
            "pivot_risk_score": _number(summary.get("average_pivot_risk_score")),
            "backup_line_success_rate": _number(summary.get("average_backup_line_success_rate")),
            "late_interruption_risk": _number(summary.get("average_late_interruption_risk")),
            "graph_stop_rate": _number(summary.get("average_graph_stop_rate")),
            "graph_pivot_rate": _number(summary.get("average_graph_pivot_rate")),
            "graph_endboard_reduction_score": _number(summary.get("average_graph_endboard_reduction_score")),
            "graph_poor_interruption_count": _number(summary.get("average_graph_poor_interruption_count")),
            "opponent_resource_valid_rate": resource_valid,
            "opponent_resource_failure_rate": resource_failure,
            "normal_summon_conflict_rate": _number(real_metrics.get("normal_summon_conflict_rate")),
            "once_per_turn_conflict_rate": _number(real_metrics.get("once_per_turn_conflict_rate")),
            "dead_duplicate_rate": _number(real_metrics.get("dead_duplicate_rate")),
            "payoff_without_enabler_rate": _number(real_metrics.get("payoff_without_enabler_rate")),
            "enabler_without_payoff_rate": _number(real_metrics.get("enabler_without_payoff_rate")),
            "best_line_average_score": best_line_score,
            "graph_valid_line_rate": graph_valid_rate,
            "graph_average_line_score": graph_line_score,
            "graph_failed_line_rate": graph_failed_rate,
            "optional_line_failure_rate": _number(real_metrics.get("optional_line_failure_rate")),
            "best_line_failure_rate": best_line_failure_rate,
            "no_valid_line_rate": no_valid_line_rate,
            "graph_average_risk_score": graph_risk,
            "resource_valid_line_rate": resource_valid,
            "missing_material_rate": _number(real_metrics.get("missing_material_rate")),
            "missing_search_target_rate": _number(real_metrics.get("missing_search_target_rate")),
            "missing_extra_deck_rate": _number(real_metrics.get("missing_extra_deck_rate")),
            "cost_failure_rate": _number(real_metrics.get("cost_failure_rate")),
            "normalized_material_failure_rate": _number(real_metrics.get("normalized_material_failure_rate")),
            "normalized_search_failure_rate": _number(real_metrics.get("normalized_search_failure_rate")),
            "normalized_extra_deck_failure_rate": _number(real_metrics.get("normalized_extra_deck_failure_rate")),
            "normalized_cost_failure_rate": _number(real_metrics.get("normalized_cost_failure_rate")),
            "cost_condition_valid_rate": cost_condition_valid,
            "cost_failure_rate_normalized": _number(real_metrics.get("cost_failure_rate_normalized")),
            "condition_failure_rate_normalized": _number(real_metrics.get("condition_failure_rate_normalized")),
            "reveal_cost_failure_rate": _number(real_metrics.get("reveal_cost_failure_rate")),
            "discard_cost_failure_rate": _number(real_metrics.get("discard_cost_failure_rate")),
            "gy_condition_failure_rate": _number(real_metrics.get("gy_condition_failure_rate")),
            "control_condition_failure_rate": _number(real_metrics.get("control_condition_failure_rate")),
            "branch_valid_rate": branch_valid,
            "no_valid_branch_rate": no_valid_branch,
            "average_branch_score": _number(real_metrics.get("average_branch_score")),
            "history_condition_failure_rate": _number(real_metrics.get("history_condition_failure_rate")),
            "summon_history_failure_rate": _number(real_metrics.get("summon_history_failure_rate")),
            "gy_history_failure_rate": _number(real_metrics.get("gy_history_failure_rate")),
            "activation_history_failure_rate": _number(real_metrics.get("activation_history_failure_rate")),
            "resolution_history_failure_rate": _number(real_metrics.get("resolution_history_failure_rate")),
            "resilience_score": resilience_score,
            "interrupted_line_success_rate": interrupted_success,
            "average_interruption_risk": interruption_risk,
            "ash_vulnerability_rate": _number(real_metrics.get("ash_vulnerability_rate")),
            "imperm_vulnerability_rate": _number(real_metrics.get("imperm_vulnerability_rate")),
            "droll_vulnerability_rate": _number(real_metrics.get("droll_vulnerability_rate")),
            "typed_material_valid_rate": typed_valid,
            "synchro_material_failure_rate": _number(real_metrics.get("synchro_material_failure_rate")),
            "fusion_material_failure_rate": _number(real_metrics.get("fusion_material_failure_rate")),
            "ritual_material_failure_rate": _number(real_metrics.get("ritual_material_failure_rate")),
            "named_material_failure_rate": _number(real_metrics.get("named_material_failure_rate")),
        },
        "config": {
            "max_average_score_drop": config.max_average_score_drop,
            "max_playable_rate_drop": config.max_playable_rate_drop,
            "max_brick_rate_increase": config.max_brick_rate_increase,
            "max_package_violation_rate": config.max_package_violation_rate,
            "min_package_quality_score": config.min_package_quality_score,
            "max_normal_summon_conflict_increase": config.max_normal_summon_conflict_increase,
            "max_once_per_turn_conflict_increase": config.max_once_per_turn_conflict_increase,
            "max_dead_duplicate_rate_increase": config.max_dead_duplicate_rate_increase,
            "max_payoff_enabler_mismatch_increase": config.max_payoff_enabler_mismatch_increase,
            "max_best_line_score_drop": config.max_best_line_score_drop,
            "max_graph_valid_line_rate_drop": config.max_graph_valid_line_rate_drop,
            "max_graph_line_score_drop": config.max_graph_line_score_drop,
            "max_graph_failed_line_rate_increase": config.max_graph_failed_line_rate_increase,
            "max_graph_risk_score_increase": config.max_graph_risk_score_increase,
            "max_resource_valid_line_rate_drop": config.max_resource_valid_line_rate_drop,
            "max_material_failure_rate_increase": config.max_material_failure_rate_increase,
            "max_search_failure_rate_increase": config.max_search_failure_rate_increase,
            "max_extra_deck_failure_rate_increase": config.max_extra_deck_failure_rate_increase,
            "max_cost_failure_rate_increase": config.max_cost_failure_rate_increase,
            "max_typed_material_valid_rate_drop": config.max_typed_material_valid_rate_drop,
            "max_typed_material_failure_rate_increase": config.max_typed_material_failure_rate_increase,
            "max_no_valid_line_rate_increase": config.max_no_valid_line_rate_increase,
            "max_best_line_failure_rate_increase": config.max_best_line_failure_rate_increase,
            "max_normalized_failure_rate_increase": config.max_normalized_failure_rate_increase,
            "max_cost_condition_valid_rate_drop": config.max_cost_condition_valid_rate_drop,
            "max_cost_condition_failure_increase": config.max_cost_condition_failure_increase,
            "max_branch_valid_rate_drop": config.max_branch_valid_rate_drop,
            "max_branch_failure_rate_increase": config.max_branch_failure_rate_increase,
            "max_history_failure_rate_increase": config.max_history_failure_rate_increase,
            "max_resilience_score_drop": config.max_resilience_score_drop,
            "max_interrupted_success_rate_drop": config.max_interrupted_success_rate_drop,
            "max_interruption_risk_increase": config.max_interruption_risk_increase,
            "max_vulnerability_rate_increase": config.max_vulnerability_rate_increase,
            "max_side_deck_score_drop": config.max_side_deck_score_drop,
            "max_matchup_coverage_drop": config.max_matchup_coverage_drop,
            "max_post_side_score_drop": config.max_post_side_score_drop,
            "min_post_side_delta": config.min_post_side_delta,
            "min_post_side_valid_rate": config.min_post_side_valid_rate,
            "min_valid_candidate_rate": config.min_valid_candidate_rate,
            "min_side_optimization_success_rate": config.min_side_optimization_success_rate,
            "min_memory_delta_difference": config.min_memory_delta_difference,
            "min_curated_memory_delta": config.min_curated_memory_delta,
            "min_curated_memory_valid_rate": config.min_curated_memory_valid_rate,
            "max_choke_stop_rate_drop": config.max_choke_stop_rate_drop,
            "max_opponent_recovery_rate_increase": config.max_opponent_recovery_rate_increase,
            "max_poor_interruption_count_increase": config.max_poor_interruption_count_increase,
            "max_timing_precision_drop": config.max_timing_precision_drop,
            "max_pivot_risk_increase": config.max_pivot_risk_increase,
            "max_backup_line_success_increase": config.max_backup_line_success_increase,
            "max_late_interruption_risk": config.max_late_interruption_risk,
            "max_graph_stop_rate_drop": config.max_graph_stop_rate_drop,
            "max_graph_pivot_rate_increase": config.max_graph_pivot_rate_increase,
            "max_graph_endboard_reduction_drop": config.max_graph_endboard_reduction_drop,
            "max_graph_poor_interruption_increase": config.max_graph_poor_interruption_increase,
            "min_opponent_resource_valid_rate": config.min_opponent_resource_valid_rate,
            "max_opponent_resource_failure_rate": config.max_opponent_resource_failure_rate,
        },
    }


def evaluate_curated_opponent_memory_update(
    summary: dict[str, Any],
    no_memory_summary: dict[str, Any] | None = None,
    config: RegressionGateConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    reasons: list[str] = []
    blocked = _number(summary.get("blocked_card_violation_count"))
    if blocked > config.max_matrix_blocked_violations:
        reasons.append("blocked-card violations detected")
    if summary.get("blocked_card_violations") or summary.get("blocked_card_violations_after_siding"):
        reasons.append("blocked cards appeared in curated opponent memory candidate")

    post_side_delta = _number(summary.get("average_post_side_delta", summary.get("post_side_delta")))
    if post_side_delta < config.min_curated_memory_delta:
        reasons.append("curated opponent post-side delta is too negative")
    valid_rate = _number(summary.get("post_side_valid_rate", 1.0 if summary.get("post_side_valid", True) else 0.0))
    if valid_rate < config.min_curated_memory_valid_rate:
        reasons.append("curated opponent side plan validity is too low")

    resilience = _number(summary.get("average_resilience_score", summary.get("resilience_score")))
    no_memory_resilience = _number(summary.get("no_memory_resilience_score"))
    if _dropped_below(resilience, no_memory_resilience, config.max_resilience_score_drop):
        reasons.append("curated opponent resilience dropped too much")

    if no_memory_summary:
        no_memory_delta = _number(no_memory_summary.get("average_post_side_delta", no_memory_summary.get("post_side_delta")))
        if post_side_delta < no_memory_delta + config.min_memory_delta_difference:
            reasons.append("curated memory performed worse than no-memory baseline")
    if _below_threshold(_number(summary.get("average_choke_stop_rate", summary.get("choke_stop_rate"))), 0) and summary:
        reasons.append("choke stop rate is invalid")
    if _above_threshold(_number(summary.get("average_poor_interruption_count", summary.get("poor_interruption_count"))), 20):
        reasons.append("post-side memory recommends poor interruptions too often")
    if _above_threshold(_number(summary.get("average_late_interruption_risk", summary.get("late_interruption_risk"))), config.max_late_interruption_risk):
        reasons.append("curated memory relies too heavily on poor timing windows")

    return {
        "accepted": not reasons,
        "reasons": reasons,
        "metrics": {
            "post_side_delta": post_side_delta,
            "post_side_valid_rate": valid_rate,
            "blocked_card_violation_count": blocked,
        },
    }


def _number(value: Any) -> NumericGateValue:
    if isinstance(value, NumericGateValue):
        return value
    if is_opponent_signal_sentinel(value):
        return NumericGateValue(0.0, "sentinel", sentinel_reason(value) or "sentinel")
    if value is None:
        return NumericGateValue(0.0, "missing", "missing")
    if isinstance(value, bool):
        return NumericGateValue(1.0 if value else 0.0, "numeric")
    try:
        return NumericGateValue(float(value), "numeric")
    except (TypeError, ValueError):
        return NumericGateValue(0.0, "schema_mismatch", type(value).__name__)


def _is_numeric(value: Any) -> bool:
    return _number(value).is_numeric


def _below_threshold(value: Any, threshold: float) -> bool:
    current = _number(value)
    return current.is_numeric and current < threshold


def _above_threshold(value: Any, threshold: float) -> bool:
    current = _number(value)
    return current.is_numeric and current > threshold


def _dropped_below(current_value: Any, previous_value: Any, allowed_drop: float) -> bool:
    current = _number(current_value)
    previous = _number(previous_value)
    return current.is_numeric and previous.is_numeric and current < previous - allowed_drop


def _increased_above(current_value: Any, previous_value: Any, allowed_increase: float) -> bool:
    current = _number(current_value)
    previous = _number(previous_value)
    return current.is_numeric and previous.is_numeric and current > previous + allowed_increase


def _metric_degradation_reasons(
    current: dict[str, Any],
    previous: dict[str, Any],
    keys: tuple[str, ...],
    *,
    prefix: str = "",
) -> list[str]:
    if not isinstance(current, dict) or not isinstance(previous, dict):
        return []
    reasons: list[str] = []
    for key in keys:
        previous_state = _number(previous.get(key))
        current_state = _number(current.get(key))
        if previous_state.is_numeric and not current_state.is_numeric:
            label = f"{prefix}{key}" if prefix else key
            reasons.append(
                f"metric degradation: {label} was historically numeric but is now {current_state.state}"
                + (f" ({current_state.reason})" if current_state.reason else "")
            )
    return reasons


def classify_gate_numeric_value(value: Any) -> dict[str, Any]:
    observed = _number(value)
    return {
        "state": observed.state,
        "value": float(observed),
        "is_zero": observed.is_zero,
        "is_numeric": observed.is_numeric,
        "reason": observed.reason,
    }
