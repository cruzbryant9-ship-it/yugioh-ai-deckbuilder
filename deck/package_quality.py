from __future__ import annotations

from typing import Any


def score_package_quality(
    deck: list[dict[str, Any]],
    package_metrics: dict[str, Any],
    score_breakdown: dict[str, Any],
) -> dict[str, float]:
    package_counts = package_metrics.get("package_counts", {})
    if not isinstance(package_counts, dict):
        package_counts = {}

    starter_count = _number(package_metrics.get("starter_count"))
    brick_count = _number(package_metrics.get("brick_count"))
    non_engine_count = _number(package_metrics.get("non_engine_count"))
    violations = package_metrics.get("package_quota_violations", [])
    if not isinstance(violations, list):
        violations = []

    deck_size = max(1, len(deck))
    extra_count = _number(package_counts.get("extra_deck"))
    engine_count = _number(package_counts.get("engine"))
    playable_rate = _number(score_breakdown.get("playable_hand_rate"))
    brick_rate = _number(score_breakdown.get("brick_rate"))
    combo_score = _number(score_breakdown.get("combo_line_score"))
    resilience = _number(score_breakdown.get("interruption_resilience_score"))
    follow_up = _number(score_breakdown.get("follow_up_score"))

    package_balance_score = _clamp(20.0 - abs(starter_count - 12) * 1.0 - abs(non_engine_count - 10) * 0.6)
    starter_quota_score = _clamp(min(20.0, starter_count * 1.8 + playable_rate * 5.0))
    brick_quota_score = _clamp(18.0 - max(0.0, brick_count - 5.0) * 3.0 - brick_rate * 12.0)
    non_engine_score = _clamp(min(16.0, non_engine_count * 1.2 + resilience * 0.6))
    engine_coherence_score = _clamp(min(14.0, combo_score * 0.55 + follow_up * 0.5 + (2.0 if engine_count <= 6 else 0.0)))
    extra_deck_score = _clamp(min(12.0, extra_count * 0.9 + _number(score_breakdown.get("endboard_score")) * 0.15))
    quota_violation_penalty = min(30.0, len(violations) * 6.0)

    final_score = (
        package_balance_score
        + starter_quota_score
        + brick_quota_score
        + non_engine_score
        + engine_coherence_score
        + extra_deck_score
        - quota_violation_penalty
    )

    return {
        "package_balance_score": round(package_balance_score, 2),
        "starter_quota_score": round(starter_quota_score, 2),
        "brick_quota_score": round(brick_quota_score, 2),
        "non_engine_score": round(non_engine_score, 2),
        "engine_coherence_score": round(engine_coherence_score, 2),
        "extra_deck_score": round(extra_deck_score, 2),
        "quota_violation_penalty": round(quota_violation_penalty, 2),
        "final_package_quality_score": round(max(0.0, final_score), 2),
    }


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, minimum: float = 0.0, maximum: float = 20.0) -> float:
    return max(minimum, min(maximum, value))

