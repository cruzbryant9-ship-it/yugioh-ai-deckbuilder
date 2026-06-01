from __future__ import annotations

from typing import Any


POSITIVE_SCORE_DELTA = 0.5
NEGATIVE_SCORE_DELTA = -0.5
NEUTRAL_CONFIDENCE_DELTA = -0.05


def analyze_filler_impact(
    archetype: str,
    mode: str,
    baseline_result: dict[str, Any],
    filler_result: dict[str, Any],
) -> dict[str, Any]:
    """Classify whether contextual filler was completion-only or performance relevant.

    This is intentionally observational. The result never rejects a deck and never
    changes scoring; it only records evidence for future reporting/memory.
    """

    filler_cards = list(filler_result.get("selected_fillers", []) or [])
    score_delta = round(safe_float(filler_result.get("score")) - safe_float(baseline_result.get("score")), 4)
    confidence_delta = round(safe_float(filler_result.get("confidence")) - safe_float(baseline_result.get("confidence")), 4)
    baseline_main_count = safe_int(baseline_result.get("main_count"))
    pre_filler_count = safe_int(filler_result.get("pre_contextual_filler_main_count", baseline_main_count))
    completion_required = bool(filler_cards) and (baseline_main_count < 40 or pre_filler_count < 40)
    repair_dependency = bool(filler_result.get("repair_used") or filler_result.get("contextual_filler_used") or completion_required)
    package_relief, package_worsened = compare_package_pressure(
        baseline_result.get("package_counts", {}),
        filler_result.get("package_counts", {}),
    )
    attribution = attribution_model(filler_cards)
    risk_flags = risk_flags_for(score_delta, confidence_delta, filler_result)
    if attribution["shared_attribution"]:
        risk_flags.append("shared_attribution")
    role_contribution = filler_result.get("filler_roles", {}).get("counts", {}) if isinstance(filler_result.get("filler_roles"), dict) else {}
    event_classification = classify_impact(score_delta, confidence_delta, completion_required, risk_flags)
    per_card_classification = per_card_attribution_classification(filler_cards, event_classification, attribution["shared_attribution"])
    attributed_score_delta = round(score_delta * safe_float(attribution["attribution_confidence"]), 4)
    attributed_confidence_delta = round(confidence_delta * safe_float(attribution["attribution_confidence"]), 4)
    return {
        "archetype": archetype,
        "mode": mode,
        "filler_cards": filler_cards,
        "impact_classification": per_card_classification,
        "event_impact_classification": event_classification,
        "score_delta": score_delta,
        "confidence_delta": confidence_delta,
        "attributed_score_delta": attributed_score_delta,
        "attributed_confidence_delta": attributed_confidence_delta,
        "attribution_model": attribution["attribution_model"],
        "attribution_shared": attribution["shared_attribution"],
        "attribution_confidence": attribution["attribution_confidence"],
        "completion_required": completion_required,
        "repair_dependency": repair_dependency,
        "package_pressure_relieved": package_relief,
        "package_pressure_worsened": package_worsened,
        "role_contribution": role_contribution,
        "would_be_under_40_without_filler": pre_filler_count < 40,
        "performance_positive_fillers": [card for card, value in per_card_classification.items() if value == "performance_positive"],
        "completion_only_fillers": [card for card, value in per_card_classification.items() if value == "completion_only"],
        "negative_fillers": [card for card, value in per_card_classification.items() if value in {"performance_negative", "risky"}],
        "indeterminate_fillers": [card for card, value in per_card_classification.items() if value == "indeterminate"],
        "risk_flags": sorted(set(risk_flags)),
    }


def classify_impact(score_delta: float, confidence_delta: float, completion_required: bool, risk_flags: list[str]) -> str:
    if "large_negative_score_delta" in risk_flags or "confidence_drop" in risk_flags:
        return "risky"
    if score_delta >= POSITIVE_SCORE_DELTA:
        return "performance_positive"
    if score_delta <= NEGATIVE_SCORE_DELTA:
        return "performance_negative"
    if completion_required:
        return "completion_only"
    if confidence_delta >= NEUTRAL_CONFIDENCE_DELTA:
        return "performance_neutral"
    return "risky"


def attribution_model(filler_cards: list[str]) -> dict[str, Any]:
    count = len(filler_cards)
    if count <= 0:
        return {"attribution_model": "none", "shared_attribution": False, "attribution_confidence": 0.0}
    if count == 1:
        return {"attribution_model": "single_card", "shared_attribution": False, "attribution_confidence": 1.0}
    return {"attribution_model": "shared", "shared_attribution": True, "attribution_confidence": round(1.0 / count, 4)}


def per_card_attribution_classification(filler_cards: list[str], event_classification: str, shared: bool) -> dict[str, str]:
    if not shared:
        return {card: event_classification for card in filler_cards}
    if event_classification == "completion_only":
        return {card: "completion_only" for card in filler_cards}
    if event_classification == "performance_neutral":
        return {card: "performance_neutral" for card in filler_cards}
    return {card: "indeterminate" for card in filler_cards}


def compare_package_pressure(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    relieved: dict[str, int] = {}
    worsened: dict[str, int] = {}
    keys = set(before or {}) | set(after or {})
    for key in sorted(keys):
        delta = safe_int((after or {}).get(key)) - safe_int((before or {}).get(key))
        if delta > 0 and key in {"starters_searchers", "extenders", "interruptions", "board_breakers", "recovery"}:
            relieved[key] = delta
        elif delta > 0 and key in {"garnet_brick", "payoffs"}:
            worsened[key] = delta
        elif delta < 0 and key in {"starters_searchers", "extenders", "interruptions", "board_breakers"}:
            worsened[key] = delta
    return relieved, worsened


def risk_flags_for(score_delta: float, confidence_delta: float, filler_result: dict[str, Any]) -> list[str]:
    flags = []
    if score_delta <= -2.0:
        flags.append("large_negative_score_delta")
    if score_delta < 0:
        flags.append("negative_score_delta")
    if confidence_delta < -0.1:
        flags.append("confidence_drop")
    warnings = list(filler_result.get("quota_warnings", []) or []) + list(filler_result.get("remaining_warnings", []) or [])
    if warnings:
        flags.append("quota_or_repair_warning")
    if filler_result.get("blocked_card_violations"):
        flags.append("blocked_card_violation")
    return sorted(set(flags))


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
