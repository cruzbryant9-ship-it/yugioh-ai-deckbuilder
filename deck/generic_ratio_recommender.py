from __future__ import annotations

from typing import Any

from deck.generic_deck_builder import GENERIC_QUOTAS


LOW_PRESSURE_ORDER = ("board_breakers", "payoffs", "recovery", "extenders", "interruptions", "starters_searchers")


def recommend_ratio_adjustments(
    archetype: str,
    mode: str,
    diagnosis: dict[str, Any],
    current_ratio: dict[str, Any],
) -> dict[str, Any]:
    base = normalize_ratio(mode, current_ratio)
    causes = list(diagnosis.get("suspected_causes", []) or []) if isinstance(diagnosis, dict) else []
    recommendations: list[dict[str, Any]] = []

    if "starter_density_low" in causes:
        for amount in (1, 2, 3):
            profile = adjust_with_offset(base, {"starters_searchers": amount}, prefer_reduce=("board_breakers", "payoffs", "recovery"))
            add_recommendation(recommendations, profile, f"Increase starter/searcher density by {amount}.", ["starter_density_low"], "low" if amount <= 2 else "medium")

    if "extender_shortage" in causes:
        for amount in (1, 2):
            profile = adjust_with_offset(base, {"extenders": amount}, prefer_reduce=("board_breakers", "payoffs"))
            add_recommendation(recommendations, profile, f"Increase extender density by {amount}.", ["extender_shortage"], "low")

    if "payoff_overfill" in causes:
        for amount in (1, 2):
            profile = apply_deltas(base, {"payoffs": -amount, "starters_searchers": 1})
            add_recommendation(recommendations, profile, f"Reduce payoff count by {amount} and refill with access.", ["payoff_overfill"], "low")

    if "brick_pressure_high" in causes:
        profile = apply_deltas(base, {"max_bricks": -1, "payoffs": -1, "starters_searchers": 1})
        add_recommendation(recommendations, profile, "Lower brick ceiling and reduce payoff pressure.", ["brick_pressure_high"], "low")
        profile = apply_deltas(base, {"max_bricks": -2, "payoffs": -1, "extenders": 1})
        add_recommendation(recommendations, profile, "Aggressively lower brick ceiling while adding an extender.", ["brick_pressure_high"], "medium")

    if "interruption_shortage" in causes:
        for amount in (1, 2, 3):
            profile = adjust_with_offset(base, {"interruptions": amount}, prefer_reduce=("board_breakers", "payoffs", "recovery"))
            add_recommendation(recommendations, profile, f"Increase non-engine interruption count by {amount}.", ["interruption_shortage"], "low" if amount <= 2 else "medium")

    if "board_breaker_overfill" in causes:
        profile = apply_deltas(base, {"board_breakers": -1, "starters_searchers": 1})
        add_recommendation(recommendations, profile, "Reduce board breakers and refill with starter access.", ["board_breaker_overfill"], "low")
        profile = apply_deltas(base, {"board_breakers": -2, "interruptions": 1, "extenders": 1})
        add_recommendation(recommendations, profile, "Convert excess board breakers into interaction and extenders.", ["board_breaker_overfill"], "medium")

    if "repair_dependency_high" in causes:
        profile = safer_balanced_ratio(base)
        add_recommendation(recommendations, profile, "Use a safer balanced ratio to reduce repair dependence.", ["repair_dependency_high"], "low")

    if "ratio_overfitting" in causes:
        add_recommendation(recommendations, apply_deltas(base, {"max_bricks": -1}), "Retest a small conservative change around the current ratio.", ["ratio_overfitting"], "low")
        add_recommendation(recommendations, normalize_ratio(mode, {}), "Retest the baseline-like ratio to guard against overfitting.", ["ratio_overfitting"], "low")

    if "quota_instability" in causes:
        add_recommendation(recommendations, safer_balanced_ratio(normalize_ratio(mode, {})), "Retest a conservative baseline-like profile for quota stability.", ["quota_instability"], "low")

    if not recommendations:
        add_recommendation(recommendations, apply_deltas(base, {"starters_searchers": 1, "interruptions": 1, "payoffs": -1}), "Low-risk access and interaction retest.", causes or ["general"], "low")

    return {
        "archetype": archetype,
        "mode": mode,
        "source_diagnosis": diagnosis,
        "current_ratio": base,
        "recommendations": recommendations[:8],
    }


def add_recommendation(
    recommendations: list[dict[str, Any]],
    ratio_profile: dict[str, int],
    reason: str,
    causes: list[str],
    risk_level: str,
) -> None:
    key = ratio_key(ratio_profile)
    if any(ratio_key(row.get("ratio_profile", {})) == key for row in recommendations):
        return
    recommendations.append(
        {
            "ratio_profile": ratio_profile,
            "reason": reason,
            "diagnosis_causes": causes,
            "risk_level": risk_level,
        }
    )


def adjust_with_offset(base: dict[str, int], increases: dict[str, int], prefer_reduce: tuple[str, ...]) -> dict[str, int]:
    deltas = dict(increases)
    total_added = sum(max(0, value) for value in increases.values())
    for key in prefer_reduce:
        if total_added <= 0:
            break
        if key == "max_bricks":
            continue
        reducible = max(0, base.get(key, 0) - minimum_quota(key))
        if reducible <= 0:
            continue
        amount = min(total_added, reducible)
        deltas[key] = deltas.get(key, 0) - amount
        total_added -= amount
    return apply_deltas(base, deltas)


def safer_balanced_ratio(base: dict[str, int]) -> dict[str, int]:
    return apply_deltas(
        base,
        {
            "starters_searchers": 1,
            "extenders": 1,
            "interruptions": 1,
            "payoffs": -1,
            "board_breakers": -1,
            "max_bricks": -1,
        },
    )


def normalize_ratio(mode: str, ratio: dict[str, Any]) -> dict[str, int]:
    base = dict(GENERIC_QUOTAS.get(mode, GENERIC_QUOTAS["meta"]))
    if isinstance(ratio, dict):
        for key, value in ratio.items():
            if key in base:
                base[key] = bounded_value(key, value)
    return base


def apply_deltas(base: dict[str, int], deltas: dict[str, int]) -> dict[str, int]:
    profile = dict(base)
    for key, delta in deltas.items():
        if key not in profile:
            continue
        profile[key] = bounded_value(key, profile[key] + int(delta))
    return profile


def bounded_value(key: str, value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    if key == "max_bricks":
        return max(2, min(6, number))
    return max(minimum_quota(key), min(16, number))


def minimum_quota(key: str) -> int:
    if key == "starters_searchers":
        return 6
    if key == "extenders":
        return 3
    if key == "interruptions":
        return 4
    if key == "payoffs":
        return 1
    return 0


def ratio_key(profile: dict[str, Any]) -> str:
    if not isinstance(profile, dict) or not profile:
        return "none"
    return "|".join(f"{key}:{profile[key]}" for key in sorted(profile))
