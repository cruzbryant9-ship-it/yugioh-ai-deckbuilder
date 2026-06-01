from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


CAUSE_RECOMMENDATIONS = {
    "starter_density_low": "Explore +1 to +2 starter/searcher slots and prefer cards that add from deck.",
    "extender_shortage": "Explore +1 to +2 extender slots and bias special-summon effects.",
    "payoff_overfill": "Reduce payoff quota by 1 and prefer lower-brick payoff access.",
    "brick_pressure_high": "Lower max_bricks by 1 and avoid high-level cards without self-summon text.",
    "interruption_shortage": "Explore +1 interruption/non-engine slot in meta builds.",
    "board_breaker_overfill": "Reduce board breaker quota and rebalance toward starters or interaction.",
    "repair_dependency_high": "Prefer safer ratio profiles before aggressive exploration.",
    "confidence_declining": "Favor ratios that preserve starter, extender, and skeleton coverage.",
    "quota_instability": "Avoid ratio profiles that repeatedly trigger quota warnings.",
    "ratio_overfitting": "Retest safer baseline-adjacent ratios before trusting narrow improvements.",
    "package_variance_high": "Constrain package ratio swings and retest with more runs.",
}


def diagnose_generic_trend(
    archetype: str,
    mode: str,
    benchmark_history: dict[str, Any],
    latest_result: dict[str, Any],
) -> dict[str, Any]:
    history = list(benchmark_history.get("history", [])) if isinstance(benchmark_history, dict) else []
    package_counts = normalized_package_counts(latest_result.get("tuned_package_counts", {}))
    ratio_profile = latest_result.get("best_ratio_profile", {}) if isinstance(latest_result, dict) else {}
    quota_warnings = list(latest_result.get("tuned_quota_warnings", []) or [])
    repair_warnings = [warning for warning, _count in latest_result.get("common_repair_warnings", []) or []]

    package_pressure = build_package_pressure(package_counts, ratio_profile)
    confidence_trend = classify_confidence_trend(history, latest_result)
    repair_dependency = calculate_repair_dependency(history, latest_result)
    bad_pattern_recurrence = calculate_bad_pattern_recurrence(benchmark_history, latest_result)
    package_variance = calculate_package_variance(history, package_counts)
    causes: list[str] = []

    if package_pressure["starters_searchers"] < 8 or warning_mentions(quota_warnings, ("starter", "searcher")):
        causes.append("starter_density_low")
    if package_pressure["extenders"] < 4 or warning_mentions(quota_warnings, ("extender",)):
        causes.append("extender_shortage")
    if package_pressure["payoffs"] > 5 or warning_mentions(quota_warnings, ("payoff overfill", "too many payoff")):
        causes.append("payoff_overfill")
    if package_pressure["bricks"] >= max(5, package_pressure["max_bricks"] + 1) or warning_mentions(quota_warnings + repair_warnings, ("brick", "garnet")):
        causes.append("brick_pressure_high")
    if package_pressure["interruptions"] < 6 or warning_mentions(quota_warnings, ("interruption", "non-engine")):
        causes.append("interruption_shortage")
    if package_pressure["board_breakers"] > 6:
        causes.append("board_breaker_overfill")
    if repair_dependency >= 0.35:
        causes.append("repair_dependency_high")
    if confidence_trend == "declining":
        causes.append("confidence_declining")
    if len(quota_warnings) >= 2 or warning_mentions(repair_warnings, ("quota", "below", "overfill")):
        causes.append("quota_instability")
    if bad_pattern_recurrence >= 0.25 or benchmark_history.get("trend_direction") == "noisy":
        causes.append("ratio_overfitting")
    if package_variance >= 2.0:
        causes.append("package_variance_high")

    causes = sorted(set(causes), key=causes.index)
    severity = classify_severity(causes, benchmark_history, repair_dependency, package_variance)
    recommendations = [CAUSE_RECOMMENDATIONS[cause] for cause in causes if cause in CAUSE_RECOMMENDATIONS]
    diagnosis = summarize_diagnosis(archetype, causes, benchmark_history)
    return {
        "archetype": archetype,
        "mode": mode,
        "diagnosis": diagnosis,
        "severity": severity,
        "suspected_causes": causes,
        "recommended_adjustments": recommendations,
        "package_pressure": package_pressure,
        "confidence_trend": confidence_trend,
        "repair_dependency": round(repair_dependency, 4),
        "bad_pattern_recurrence": round(bad_pattern_recurrence, 4),
    }


def normalized_package_counts(raw_counts: Any) -> dict[str, int]:
    counts = raw_counts if isinstance(raw_counts, dict) else {}
    starters = count_any(counts, ("starters_searchers", "starters", "searchers", "starter", "searcher"))
    bricks = count_any(counts, ("garnet_brick", "bricks", "brick", "garnets"))
    return {
        "starters_searchers": starters,
        "extenders": count_any(counts, ("extenders", "extender")),
        "payoffs": count_any(counts, ("payoffs", "payoff")),
        "interruptions": count_any(counts, ("interruptions", "interruption", "non_engine", "handtraps")),
        "board_breakers": count_any(counts, ("board_breakers", "board_breaker")),
        "bricks": bricks,
        "core": count_any(counts, ("core",)),
        "recovery": count_any(counts, ("recovery",)),
    }


def build_package_pressure(package_counts: dict[str, int], ratio_profile: Any) -> dict[str, Any]:
    ratio = ratio_profile if isinstance(ratio_profile, dict) else {}
    pressure = dict(package_counts)
    pressure["payoffs"] = max(int(pressure.get("payoffs", 0)), safe_int(ratio.get("payoffs", 0)))
    pressure["board_breakers"] = max(int(pressure.get("board_breakers", 0)), safe_int(ratio.get("board_breakers", 0)))
    pressure["target_starters_searchers"] = safe_int(ratio.get("starters_searchers", 0))
    pressure["target_extenders"] = safe_int(ratio.get("extenders", 0))
    pressure["target_interruptions"] = safe_int(ratio.get("interruptions", 0))
    pressure["max_bricks"] = safe_int(ratio.get("max_bricks", 4)) or 4
    pressure["brick_pressure"] = round(safe_ratio(pressure.get("bricks", 0), max(1, pressure["max_bricks"])), 4)
    return pressure


def classify_confidence_trend(history: list[dict[str, Any]], latest_result: dict[str, Any]) -> str:
    values = [safe_float(entry.get("confidence_delta")) for entry in history[-6:] if "confidence_delta" in entry]
    if "confidence_delta" in latest_result:
        values.append(safe_float(latest_result.get("confidence_delta")))
    if not values:
        return "stable"
    recent = values[-3:]
    average_delta = mean(recent)
    if average_delta < -0.08:
        return "declining"
    if average_delta > 0.08:
        return "improving"
    return "stable"


def calculate_repair_dependency(history: list[dict[str, Any]], latest_result: dict[str, Any]) -> float:
    repair_rates = [safe_float(entry.get("repair_success_rate")) for entry in history[-5:] if "repair_success_rate" in entry]
    repair_actions = [safe_float(entry.get("average_repair_actions")) for entry in history[-5:] if "average_repair_actions" in entry]
    if "repair_success_rate" in latest_result:
        repair_rates.append(safe_float(latest_result.get("repair_success_rate")))
    if "average_repair_actions" in latest_result:
        repair_actions.append(safe_float(latest_result.get("average_repair_actions")))
    reliability_gap = 1.0 - mean(repair_rates) if repair_rates else 0.0
    action_pressure = min(1.0, (mean(repair_actions) / 4.0) if repair_actions else 0.0)
    fallback_pressure = min(1.0, safe_float(latest_result.get("fallback_used_count")) / max(1.0, safe_float(latest_result.get("variant_count", 1))))
    return max(0.0, min(1.0, reliability_gap * 0.55 + action_pressure * 0.35 + fallback_pressure * 0.10))


def calculate_bad_pattern_recurrence(benchmark_history: dict[str, Any], latest_result: dict[str, Any]) -> float:
    bad_patterns = benchmark_history.get("bad_ratio_patterns", []) if isinstance(benchmark_history, dict) else []
    total_runs = max(1, safe_int(benchmark_history.get("total_benchmark_runs", 0)))
    latest_key = ratio_profile_key(latest_result.get("best_ratio_profile", {}))
    recurring_bad = 0
    for entry in bad_patterns:
        if ratio_profile_key(entry.get("ratio_profile", {})) == latest_key:
            recurring_bad += 1
    return min(1.0, max(len(bad_patterns) / total_runs, recurring_bad / 3 if latest_key != "none" else 0.0))


def calculate_package_variance(history: list[dict[str, Any]], latest_counts: dict[str, int]) -> float:
    rows = []
    for entry in history[-8:]:
        counts = normalized_package_counts(entry.get("tuned_package_counts", {}))
        if any(counts.values()):
            rows.append(counts)
    if any(latest_counts.values()):
        rows.append(latest_counts)
    if len(rows) < 3:
        return 0.0
    deviations = []
    for key in ("starters_searchers", "extenders", "payoffs", "interruptions", "board_breakers", "bricks"):
        values = [safe_float(row.get(key)) for row in rows]
        if len(values) >= 3:
            deviations.append(pstdev(values))
    return mean(deviations) if deviations else 0.0


def classify_severity(causes: list[str], benchmark_history: dict[str, Any], repair_dependency: float, package_variance: float) -> str:
    high_causes = {"repair_dependency_high", "confidence_declining", "brick_pressure_high", "ratio_overfitting"}
    if len(causes) >= 4 or len(high_causes.intersection(causes)) >= 2:
        return "high"
    if benchmark_history.get("trend_direction") == "declining" and causes:
        return "high"
    if len(causes) >= 2 or repair_dependency >= 0.35 or package_variance >= 2.0:
        return "medium"
    return "low"


def summarize_diagnosis(archetype: str, causes: list[str], benchmark_history: dict[str, Any]) -> str:
    trend = benchmark_history.get("trend_direction", "stable") if isinstance(benchmark_history, dict) else "stable"
    if not causes:
        return f"{archetype} trend looks {trend}; no major package pressure detected."
    readable = ", ".join(cause.replace("_", " ") for cause in causes[:3])
    if len(causes) > 3:
        readable += f", and {len(causes) - 3} more"
    return f"{archetype} trend is {trend}; likely pressure from {readable}."


def warning_mentions(warnings: list[Any], terms: tuple[str, ...]) -> bool:
    text = " ".join(str(warning).casefold() for warning in warnings)
    return any(term.casefold() in text for term in terms)


def count_any(counts: dict[str, Any], keys: tuple[str, ...]) -> int:
    return sum(safe_int(counts.get(key, 0)) for key in keys)


def ratio_profile_key(profile: Any) -> str:
    if not isinstance(profile, dict) or not profile:
        return "none"
    return "|".join(f"{key}:{profile[key]}" for key in sorted(profile))


def safe_ratio(numerator: Any, denominator: Any) -> float:
    bottom = safe_float(denominator)
    if bottom == 0:
        return 0.0
    return safe_float(numerator) / bottom


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
