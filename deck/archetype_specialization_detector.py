from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from deck.archetype_role_inference import infer_archetype_roles
from deck.generic_benchmark_memory import load_generic_benchmark_history
from deck.generic_filler_memory import load_generic_filler_memory
from deck.generic_ratio_memory import load_generic_ratio_memory
from SystemAIYugioh.card_database import CardDatabase


GATE_THRESHOLDS = {
    "minimum_benchmark_runs": 20,
    "average_tuned_improvement": 0.25,
    "repair_success_rate": 0.9,
    "rejected_deck_rate": 0.05,
    "quota_warning_rate": 0.25,
    "generic_confidence_score": 0.6,
    "role_inference_confidence": 0.55,
    "package_stability": 0.55,
    "ratio_memory_stability": 0.5,
    "repair_dependency": 3.0,
    "filler_dependency": 0.35,
}

CRITICAL_GATES = {
    "minimum_benchmark_runs",
    "blocked_card_clean",
}


def evaluate_specialization_candidate(
    archetype: str,
    mode: str = "meta",
    *,
    evidence_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = evidence_override or collect_specialization_evidence(archetype, mode)
    gates = evaluate_gates(evidence)
    passed = [name for name, result in gates.items() if result["passed"]]
    failed = [name for name, result in gates.items() if not result["passed"]]
    readiness_score = round(sum(result["score"] for result in gates.values()) / max(1, len(gates)), 2)
    critical_failed = [gate for gate in failed if gate in CRITICAL_GATES]
    if critical_failed or readiness_score < 55:
        status = "not_ready"
    elif not failed and readiness_score >= 80:
        status = "ready"
    else:
        status = "watchlist"
    return {
        "archetype": archetype,
        "mode": mode,
        "candidate_status": status,
        "readiness_score": readiness_score,
        "passed_gates": passed,
        "failed_gates": failed,
        "warnings": warnings_for(evidence, gates),
        "evidence": evidence,
        "gate_details": gates,
        "recommended_next_action": recommended_next_action(status, failed),
    }


def collect_specialization_evidence(archetype: str, mode: str) -> dict[str, Any]:
    benchmark = load_generic_benchmark_history(archetype, mode)
    ratio = load_generic_ratio_memory(archetype, mode)
    filler = load_generic_filler_memory(archetype, mode)
    cards = CardDatabase().load_cards()
    roles = infer_archetype_roles(cards, archetype)
    history = [entry for entry in benchmark.get("history", []) if isinstance(entry, dict)]
    runs = int(benchmark.get("total_benchmark_runs", len(history)) or 0)
    repair_rates = [safe_float(value) for value in benchmark.get("repair_success_rate_history", []) if value is not None]
    quota_warning_count = sum(
        len(entry.get("normal_quota_warnings", []) or []) + len(entry.get("tuned_quota_warnings", []) or [])
        for entry in history
    )
    blocked_violations = collect_blocked_violations(history)
    package_stability = package_stability_score(history)
    ratio_stability = ratio_memory_stability(ratio)
    role_confidence = average_role_confidence(roles)
    role_coverage = sum(1 for count in roles.get("role_counts", {}).values() if int(count or 0) > 0)
    filler_dependency = filler_dependency_score(filler)
    generic_confidence = average(ratio.get("confidence_trends", []))
    return {
        "benchmark_runs": runs,
        "average_tuned_improvement": safe_float(benchmark.get("average_improvement")),
        "repair_success_rate": average(repair_rates),
        "average_repair_actions": safe_float(benchmark.get("average_repair_actions")),
        "rejected_deck_count": int(benchmark.get("rejected_deck_count", 0) or 0),
        "rejected_deck_rate": int(benchmark.get("rejected_deck_count", 0) or 0) / max(1, runs),
        "quota_warning_count": quota_warning_count,
        "quota_warning_rate": quota_warning_count / max(1, runs),
        "generic_confidence_score": generic_confidence,
        "role_inference_confidence": role_confidence,
        "role_coverage_count": role_coverage,
        "archetype_card_count": int(roles.get("card_count", 0) or 0),
        "package_stability": package_stability,
        "ratio_memory_stability": ratio_stability,
        "benchmark_trend": str(benchmark.get("trend_direction", "stable")),
        "blocked_card_violations": blocked_violations,
        "filler_dependency": filler_dependency,
        "filler_observation_count": filler_observation_count(filler),
        "tuning_hurt_count": int(benchmark.get("tuning_hurt_count", 0) or 0),
        "best_improvement": safe_float(benchmark.get("best_improvement")),
        "worst_improvement": safe_float(benchmark.get("worst_improvement")),
    }


def evaluate_gates(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "minimum_benchmark_runs": min_gate(evidence, "benchmark_runs", GATE_THRESHOLDS["minimum_benchmark_runs"]),
        "average_tuned_improvement": min_gate(evidence, "average_tuned_improvement", GATE_THRESHOLDS["average_tuned_improvement"]),
        "repair_success_rate": min_gate(evidence, "repair_success_rate", GATE_THRESHOLDS["repair_success_rate"]),
        "rejected_deck_rate": max_gate(evidence, "rejected_deck_rate", GATE_THRESHOLDS["rejected_deck_rate"]),
        "quota_warning_rate": max_gate(evidence, "quota_warning_rate", GATE_THRESHOLDS["quota_warning_rate"]),
        "generic_confidence_score": min_gate(evidence, "generic_confidence_score", GATE_THRESHOLDS["generic_confidence_score"]),
        "role_inference_confidence": min_gate(evidence, "role_inference_confidence", GATE_THRESHOLDS["role_inference_confidence"]),
        "archetype_breadth": min_gate(evidence, "archetype_card_count", 8),
        "package_stability": min_gate(evidence, "package_stability", GATE_THRESHOLDS["package_stability"]),
        "ratio_memory_stability": min_gate(evidence, "ratio_memory_stability", GATE_THRESHOLDS["ratio_memory_stability"]),
        "benchmark_trend_not_declining": {
            "passed": evidence.get("benchmark_trend") not in {"declining"},
            "value": evidence.get("benchmark_trend"),
            "threshold": "not declining",
            "score": 100.0 if evidence.get("benchmark_trend") not in {"declining"} else 0.0,
        },
        "blocked_card_clean": {
            "passed": not evidence.get("blocked_card_violations"),
            "value": len(evidence.get("blocked_card_violations", []) or []),
            "threshold": 0,
            "score": 100.0 if not evidence.get("blocked_card_violations") else 0.0,
        },
        "low_repair_dependency": max_gate(evidence, "average_repair_actions", GATE_THRESHOLDS["repair_dependency"]),
        "filler_dependency_not_excessive": max_gate(evidence, "filler_dependency", GATE_THRESHOLDS["filler_dependency"]),
    }


def min_gate(evidence: dict[str, Any], key: str, threshold: float) -> dict[str, Any]:
    value = safe_float(evidence.get(key))
    return {
        "passed": value >= threshold,
        "value": round(value, 4),
        "threshold": threshold,
        "score": round(min(100.0, max(0.0, value / max(threshold, 0.0001) * 100.0)), 2),
    }


def max_gate(evidence: dict[str, Any], key: str, threshold: float) -> dict[str, Any]:
    value = safe_float(evidence.get(key))
    passed = value <= threshold
    score = 100.0 if value <= threshold else max(0.0, 100.0 - ((value - threshold) / max(threshold, 0.0001) * 100.0))
    return {"passed": passed, "value": round(value, 4), "threshold": threshold, "score": round(score, 2)}


def package_stability_score(history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    keys = ("starters_searchers", "extenders", "payoffs", "interruptions", "board_breakers", "max_bricks")
    scores = []
    for key in keys:
        values = []
        for entry in history[-50:]:
            profile = entry.get("best_ratio_profile", {})
            if isinstance(profile, dict) and key in profile:
                values.append(safe_float(profile.get(key)))
        if len(values) < 2:
            continue
        avg = max(1.0, average(values))
        scores.append(max(0.0, 1.0 - pstdev(values) / avg))
    return round(average(scores), 4) if scores else 0.0


def ratio_memory_stability(ratio: dict[str, Any]) -> float:
    counts = [int(value or 0) for value in (ratio.get("ratio_score_counts", {}) or {}).values()]
    if not counts:
        return 0.0
    total = sum(counts)
    top_share = max(counts) / max(1, total)
    confidence = average(ratio.get("confidence_trends", []))
    return round((top_share * 0.7) + (confidence * 0.3), 4)


def average_role_confidence(roles: dict[str, Any]) -> float:
    cards = roles.get("cards", {})
    if not isinstance(cards, dict):
        return 0.0
    return average([safe_float(row.get("confidence")) for row in cards.values() if isinstance(row, dict)])


def filler_dependency_score(filler: dict[str, Any]) -> float:
    fillers = filler.get("fillers", {}) if isinstance(filler, dict) else {}
    if not isinstance(fillers, dict) or not fillers:
        return 0.0
    total = sum(int(row.get("times_used", 0) or 0) for row in fillers.values() if isinstance(row, dict))
    completion = sum(int(row.get("completion_only_count", 0) or 0) for row in fillers.values() if isinstance(row, dict))
    negative = sum(int(row.get("performance_negative_count", 0) or 0) for row in fillers.values() if isinstance(row, dict))
    return round((completion + negative) / max(1, total), 4)


def filler_observation_count(filler: dict[str, Any]) -> int:
    fillers = filler.get("fillers", {}) if isinstance(filler, dict) else {}
    if not isinstance(fillers, dict):
        return 0
    return sum(int(row.get("times_used", 0) or 0) for row in fillers.values() if isinstance(row, dict))


def collect_blocked_violations(history: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for entry in history:
        for key, value in entry.items():
            if "blocked" in str(key).casefold() and value:
                violations.append(f"{key}: {value}")
        for warning_key in ("normal_quota_warnings", "tuned_quota_warnings", "common_repair_warnings"):
            for warning in entry.get(warning_key, []) or []:
                if "blocked" in str(warning).casefold():
                    violations.append(str(warning))
    return violations[:20]


def warnings_for(evidence: dict[str, Any], gates: dict[str, dict[str, Any]]) -> list[str]:
    warnings = []
    for name, result in gates.items():
        if not result["passed"]:
            warnings.append(f"{name} failed: {result['value']} vs {result['threshold']}")
    if evidence.get("tuning_hurt_count", 0):
        warnings.append(f"tuning hurt in {evidence['tuning_hurt_count']} historical runs")
    return warnings


def recommended_next_action(status: str, failed_gates: list[str]) -> str:
    if status == "ready":
        return "Review manually for Phase 8C semi-specialization design; do not auto-promote."
    if "minimum_benchmark_runs" in failed_gates:
        return "Collect more generic benchmark runs before considering specialization."
    if "blocked_card_clean" in failed_gates:
        return "Investigate blocked-card contamination before any specialization work."
    if "low_repair_dependency" in failed_gates:
        return "Improve generic legality/repair stability before specialization."
    return "Keep on watchlist and continue generic training/evaluation."


def average(values: list[Any]) -> float:
    numeric = [safe_float(value) for value in values if value is not None]
    return round(mean(numeric), 4) if numeric else 0.0


def safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
