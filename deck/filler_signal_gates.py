from __future__ import annotations

from typing import Any

from deck import advisory_influence_budget as advisory_budget_module
from deck.advisory_influence_budget import AdvisoryInfluenceBudget
from deck.generic_filler_memory import (
    CONCENTRATION_WARNING_THRESHOLD,
    MIN_FILLER_ARCHETYPE_BREADTH,
    MIN_FILLER_MEMORY_USES,
    completion_bias_flag,
)


MIN_SINGLE_CARD_ATTRIBUTION_SHARE = 0.6
MAX_INDETERMINATE_SHARE = 0.25
MIN_ATTRIBUTION_CONFIDENCE = 0.75
MAX_NEGATIVE_SHARE = 0.25
MIN_AVERAGE_SCORE_DELTA = 0.0


def observation_floor(entry: dict[str, Any], minimum: int = MIN_FILLER_MEMORY_USES) -> tuple[bool, float]:
    value = safe_int(entry.get("times_used"))
    return value >= minimum, value


def archetype_breadth(entry: dict[str, Any], minimum: int = MIN_FILLER_ARCHETYPE_BREADTH) -> tuple[bool, float]:
    value = safe_int(entry.get("archetype_breadth") or len(entry.get("affected_archetypes", []) or []))
    return value >= minimum, value


def concentration_clearance(entry: dict[str, Any], max_share: float = CONCENTRATION_WARNING_THRESHOLD) -> tuple[bool, float]:
    share = dominant_archetype_share(entry)
    return share <= max_share, round(share, 4)


def attribution_majority(entry: dict[str, Any], minimum_share: float = MIN_SINGLE_CARD_ATTRIBUTION_SHARE) -> tuple[bool, float]:
    times = max(1, safe_int(entry.get("times_used")))
    share = safe_int(entry.get("single_card_attribution_count")) / times
    return share >= minimum_share, round(share, 4)


def indeterminate_suppression(entry: dict[str, Any], max_share: float = MAX_INDETERMINATE_SHARE) -> tuple[bool, float]:
    times = max(1, safe_int(entry.get("times_used")))
    share = safe_int(entry.get("indeterminate_count")) / times
    return share <= max_share, round(share, 4)


def confidence_floor(entry: dict[str, Any], minimum: float = MIN_ATTRIBUTION_CONFIDENCE) -> tuple[bool, float]:
    value = safe_float(entry.get("average_attribution_confidence"))
    return value >= minimum, round(value, 4)


def score_stability(entry: dict[str, Any], min_average_delta: float = MIN_AVERAGE_SCORE_DELTA, max_negative_share: float = MAX_NEGATIVE_SHARE) -> tuple[bool, dict[str, float]]:
    average_delta = safe_float(entry.get("average_score_delta"))
    times = max(1, safe_int(entry.get("times_used")))
    negative_share = safe_int(entry.get("performance_negative_count")) / times
    passed = average_delta >= min_average_delta and negative_share <= max_negative_share
    return passed, {"average_score_delta": round(average_delta, 4), "negative_share": round(negative_share, 4)}


def provenance_clean(entry: dict[str, Any], provenance: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    provenance = provenance if isinstance(provenance, dict) else entry.get("last_observation_provenance", {})
    times = safe_int(entry.get("times_used"))
    legal = safe_int(entry.get("legal_observation_count"))
    illegal = safe_int(entry.get("illegal_observation_count"))
    validator_generated = bool((provenance or {}).get("validator_generated"))
    passed = legal >= times and illegal == 0 and not validator_generated
    return passed, {
        "legal_observation_count": legal,
        "illegal_observation_count": illegal,
        "times_used": times,
        "validator_generated": validator_generated,
    }


def advisory_budget_available(budget_summary: dict[str, Any] | None = None) -> tuple[bool, float]:
    if budget_summary is None:
        budget_summary = AdvisoryInfluenceBudget().summary()
    if not budget_summary.get("enabled", True):
        return False, 0.0
    remaining = safe_float(budget_summary.get("remaining"))
    return remaining > 0, round(remaining, 6)


def kill_switch_enabled() -> tuple[bool, bool]:
    # Gate passes only when the global kill switch is not active.
    return not advisory_budget_module.ADVISORY_KILL_SWITCH, bool(advisory_budget_module.ADVISORY_KILL_SWITCH)


def completion_bias_suppression(entry: dict[str, Any]) -> tuple[bool, bool]:
    biased = bool(entry.get("completion_bias_flag")) or completion_bias_flag(entry)
    return not biased, biased


def evaluate_filler_signal_eligibility(
    card_name: str,
    entry: dict[str, Any],
    *,
    provenance: dict[str, Any] | None = None,
    budget_summary: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or {}
    checks = {
        "observation_floor": observation_floor(entry, safe_int(thresholds.get("min_observations", MIN_FILLER_MEMORY_USES))),
        "archetype_breadth": archetype_breadth(entry, safe_int(thresholds.get("min_archetype_breadth", MIN_FILLER_ARCHETYPE_BREADTH))),
        "concentration_clearance": concentration_clearance(entry, safe_float(thresholds.get("max_concentration", CONCENTRATION_WARNING_THRESHOLD))),
        "attribution_majority": attribution_majority(entry, safe_float(thresholds.get("min_single_card_attribution_share", MIN_SINGLE_CARD_ATTRIBUTION_SHARE))),
        "indeterminate_suppression": indeterminate_suppression(entry, safe_float(thresholds.get("max_indeterminate_share", MAX_INDETERMINATE_SHARE))),
        "confidence_floor": confidence_floor(entry, safe_float(thresholds.get("min_attribution_confidence", MIN_ATTRIBUTION_CONFIDENCE))),
        "score_stability": score_stability(
            entry,
            safe_float(thresholds.get("min_average_score_delta", MIN_AVERAGE_SCORE_DELTA)),
            safe_float(thresholds.get("max_negative_share", MAX_NEGATIVE_SHARE)),
        ),
        "provenance_clean": provenance_clean(entry, provenance),
        "advisory_budget_available": advisory_budget_available(budget_summary),
        "kill_switch_enabled": kill_switch_enabled(),
        "completion_bias_suppression": completion_bias_suppression(entry),
    }
    passed = [name for name, (ok, _score) in checks.items() if ok]
    failed = [name for name, (ok, _score) in checks.items() if not ok]
    gate_scores = {name: score for name, (_ok, score) in checks.items()}
    warnings = warnings_for(card_name, entry, failed, gate_scores)
    return {
        "card": card_name,
        "eligible": not failed,
        "passed_gates": passed,
        "failed_gates": failed,
        "gate_scores": gate_scores,
        "warnings": warnings,
    }


def warnings_for(card_name: str, entry: dict[str, Any], failed: list[str], scores: dict[str, Any]) -> list[str]:
    warnings = []
    if "concentration_clearance" in failed:
        dominant = dominant_archetype(entry)
        warnings.append(f"{card_name} is concentrated in {dominant} at {scores.get('concentration_clearance')}")
    if "attribution_majority" in failed:
        warnings.append(f"{card_name} lacks enough single-card attribution.")
    if "indeterminate_suppression" in failed:
        warnings.append(f"{card_name} has too much indeterminate attribution.")
    if "completion_bias_suppression" in failed:
        warnings.append(f"{card_name} is completion-biased.")
    if "confidence_floor" in failed:
        warnings.append(f"{card_name} has weak attribution confidence.")
    if "score_stability" in failed:
        warnings.append(f"{card_name} has unstable or negative score evidence.")
    if "provenance_clean" in failed:
        warnings.append(f"{card_name} has invalid provenance or illegal observations.")
    if "advisory_budget_available" in failed:
        warnings.append(f"{card_name} has no advisory budget available.")
    if "kill_switch_enabled" in failed:
        warnings.append(f"{card_name} is blocked by the advisory kill switch.")
    if "observation_floor" in failed:
        warnings.append(f"{card_name} has insufficient observations.")
    if "archetype_breadth" in failed:
        warnings.append(f"{card_name} lacks cross-archetype breadth.")
    return warnings


def dominant_archetype_share(entry: dict[str, Any]) -> float:
    observations = entry.get("archetype_observations", {}) or {}
    total = sum(safe_int(value) for value in observations.values())
    if total <= 0:
        return 0.0
    return max(safe_int(value) for value in observations.values()) / total


def dominant_archetype(entry: dict[str, Any]) -> str:
    observations = entry.get("archetype_observations", {}) or {}
    if not observations:
        return "unknown"
    return max(observations.items(), key=lambda item: safe_int(item[1]))[0]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
