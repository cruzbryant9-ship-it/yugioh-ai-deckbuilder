from __future__ import annotations

from statistics import mean
from typing import Any

from deck.interaction_core_registry import interaction_core_for
from deck.semi_specialized_builder_adapter import dependency_gate_report


SENTINEL_NOT_MEASURED = "not_measured"
SENTINEL_NOT_APPLICABLE = "not_applicable"
SENTINEL_UNAVAILABLE = "unavailable"
SENTINELS = {SENTINEL_NOT_MEASURED, SENTINEL_NOT_APPLICABLE, SENTINEL_UNAVAILABLE}


def measured(value: Any) -> dict[str, Any]:
    return {"status": "measured", "value": value, "reason": None}


def sentinel(status: str, reason: str) -> dict[str, Any]:
    return {"status": status, "value": None, "reason": reason}


def telemetry_value(report: dict[str, Any], key: str, default_if_absent: Any = None, absent_status: str = SENTINEL_NOT_MEASURED) -> dict[str, Any]:
    if key in report:
        return measured(report.get(key))
    if default_if_absent is not None:
        return measured(default_if_absent)
    return sentinel(absent_status, f"{key} was not present in executed build report")


def numeric_from_value(value: dict[str, Any]) -> float | None:
    if value.get("status") != "measured":
        return None
    try:
        return float(value.get("value") or 0)
    except (TypeError, ValueError):
        return None


def bool_from_value(value: dict[str, Any]) -> bool | None:
    if value.get("status") != "measured":
        return None
    return bool(value.get("value"))


def build_dependency_telemetry(deck: list[dict[str, Any]], report: dict[str, Any], archetype: str = "Kashtira") -> dict[str, Any]:
    package_counts = report.get("package_counts", {}) or {}
    interaction_core = set(interaction_core_for(archetype))
    attempted = bool(report.get("interaction_preservation_attempted", False))
    selected_names = [str(card.get("name", "")) for card in deck if str(card.get("name", "")) in interaction_core]
    selected_count = int(report.get("interaction_candidates_selected", package_counts.get("preserved_interaction", len(selected_names)) or 0))
    rejected = report.get("interaction_candidates_rejected")
    if rejected is None:
        rejected = []
    rejection_reasons = report.get("interaction_rejection_reasons")
    if rejection_reasons is None:
        rejection_reasons = []
    safe_filler = telemetry_value(report, "safe_filler_used_count")
    repair_actions = telemetry_value(report, "repair_action_count")
    repair_used = telemetry_value(report, "repair_used")
    repair_success = telemetry_value(report, "repair_success")
    generic_fill = measured(float(package_counts.get("generic_fill", 0) or 0)) if package_counts else sentinel(SENTINEL_NOT_MEASURED, "package_counts were not present in executed build report")
    return {
        "safe_filler_used_count": safe_filler,
        "repair_used": repair_used,
        "repair_success": repair_success,
        "repair_action_count": repair_actions,
        "repair_dependency_score": dependency_score(repair_actions),
        "filler_dependency_score": dependency_score(safe_filler),
        "generic_fill_count": generic_fill,
        "interaction_preservation_attempted": measured(attempted),
        "interaction_candidates_selected_names": measured(selected_names),
        "interaction_candidates_selected": measured(selected_count),
        "interaction_candidates_rejected": measured(list(rejected)),
        "interaction_rejection_reasons": measured(list(rejection_reasons)),
    }


def dependency_score(value: dict[str, Any]) -> dict[str, Any]:
    numeric = numeric_from_value(value)
    if numeric is None:
        return sentinel(value.get("status", SENTINEL_UNAVAILABLE), value.get("reason") or "dependency value unavailable")
    return measured(round(numeric, 4))


def summarize_dependency_telemetry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    telemetry_rows = [row.get("dependency_telemetry", {}) or {} for row in rows]
    return {
        "safe_filler_used_count": summarize_metric(telemetry_rows, "safe_filler_used_count"),
        "repair_used": summarize_bool_metric(telemetry_rows, "repair_used"),
        "repair_success": summarize_bool_metric(telemetry_rows, "repair_success"),
        "repair_action_count": summarize_metric(telemetry_rows, "repair_action_count"),
        "repair_dependency_score": summarize_metric(telemetry_rows, "repair_dependency_score"),
        "filler_dependency_score": summarize_metric(telemetry_rows, "filler_dependency_score"),
        "generic_fill_count": summarize_metric(telemetry_rows, "generic_fill_count"),
        "interaction_preservation_attempted": summarize_bool_metric(telemetry_rows, "interaction_preservation_attempted"),
        "interaction_candidates_selected_names": summarize_list_metric(telemetry_rows, "interaction_candidates_selected_names"),
        "interaction_candidates_selected": summarize_metric(telemetry_rows, "interaction_candidates_selected"),
        "interaction_candidates_rejected": summarize_list_metric(telemetry_rows, "interaction_candidates_rejected"),
        "interaction_rejection_reasons": summarize_list_metric(telemetry_rows, "interaction_rejection_reasons"),
    }


def summarize_metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = []
    sentinels: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or sentinel(SENTINEL_NOT_MEASURED, f"{key} missing from telemetry row")
        numeric = numeric_from_value(value)
        if numeric is None:
            status = str(value.get("status") or SENTINEL_UNAVAILABLE)
            sentinels[status] = sentinels.get(status, 0) + 1
            reason = str(value.get("reason") or status)
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            values.append(numeric)
    if values:
        return {
            "status": "measured",
            "average": round(mean(values), 4),
            "observations": len(values),
            "sentinel_counts": dict(sorted(sentinels.items())),
            "unavailable_reasons": dict(sorted(reasons.items())),
        }
    return {
        "status": SENTINEL_NOT_MEASURED if not sentinels else sorted(sentinels)[0],
        "average": None,
        "observations": 0,
        "sentinel_counts": dict(sorted(sentinels.items())),
        "unavailable_reasons": dict(sorted(reasons.items())),
    }


def summarize_bool_metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = []
    sentinels: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or sentinel(SENTINEL_NOT_MEASURED, f"{key} missing from telemetry row")
        bool_value = bool_from_value(value)
        if bool_value is None:
            status = str(value.get("status") or SENTINEL_UNAVAILABLE)
            sentinels[status] = sentinels.get(status, 0) + 1
            reason = str(value.get("reason") or status)
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            values.append(1.0 if bool_value else 0.0)
    if values:
        return {
            "status": "measured",
            "rate": round(mean(values), 4),
            "observations": len(values),
            "sentinel_counts": dict(sorted(sentinels.items())),
            "unavailable_reasons": dict(sorted(reasons.items())),
        }
    return {
        "status": SENTINEL_NOT_MEASURED if not sentinels else sorted(sentinels)[0],
        "rate": None,
        "observations": 0,
        "sentinel_counts": dict(sorted(sentinels.items())),
        "unavailable_reasons": dict(sorted(reasons.items())),
    }


def summarize_list_metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    items: dict[str, int] = {}
    sentinels: dict[str, int] = {}
    reasons: dict[str, int] = {}
    observations = 0
    for row in rows:
        value = row.get(key) or sentinel(SENTINEL_NOT_MEASURED, f"{key} missing from telemetry row")
        if value.get("status") != "measured":
            status = str(value.get("status") or SENTINEL_UNAVAILABLE)
            sentinels[status] = sentinels.get(status, 0) + 1
            reason = str(value.get("reason") or status)
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        observations += 1
        for item in value.get("value") or []:
            label = str(item)
            items[label] = items.get(label, 0) + 1
    return {
        "status": "measured" if observations else (SENTINEL_NOT_MEASURED if not sentinels else sorted(sentinels)[0]),
        "observations": observations,
        "items": dict(sorted(items.items())),
        "sentinel_counts": dict(sorted(sentinels.items())),
        "unavailable_reasons": dict(sorted(reasons.items())),
    }


def compare_dependency_summaries(generic: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "safe_filler_used_count": metric_delta(generic.get("safe_filler_used_count", {}), candidate.get("safe_filler_used_count", {})),
        "repair_action_count": metric_delta(generic.get("repair_action_count", {}), candidate.get("repair_action_count", {})),
        "repair_dependency_score": metric_delta(generic.get("repair_dependency_score", {}), candidate.get("repair_dependency_score", {})),
        "filler_dependency_score": metric_delta(generic.get("filler_dependency_score", {}), candidate.get("filler_dependency_score", {})),
        "generic_fill_count": metric_delta(generic.get("generic_fill_count", {}), candidate.get("generic_fill_count", {})),
        "interaction_candidates_selected": metric_delta(generic.get("interaction_candidates_selected", {}), candidate.get("interaction_candidates_selected", {})),
    }


def promotion_safety_gates(
    generic: dict[str, Any],
    candidate: dict[str, Any],
    *,
    generic_fill_delta_limit: float = 0.0,
    interaction_loss_limit: float = 0.0,
) -> dict[str, Any]:
    generic_fill_gate = generic_fill_pressure_gate(generic, candidate, generic_fill_delta_limit)
    interaction_gate = interaction_loss_gate(generic, candidate, interaction_loss_limit)
    reasons = []
    if generic_fill_gate.get("promotion_blocked"):
        reasons.append("generic_fill_pressure_increase")
    if interaction_gate.get("promotion_blocked"):
        reasons.append("interaction_loss")
    return {
        "generic_fill_gate": generic_fill_gate,
        "interaction_loss_gate": interaction_gate,
        "promotion_blocking_reasons": reasons,
        "promotion_blocked": bool(reasons),
        "lost_interaction_cards": interaction_gate.get("lost_interaction_cards", []),
        "gate_config": {
            "generic_fill_delta_limit": generic_fill_delta_limit,
            "interaction_loss_limit": interaction_loss_limit,
            "source": "executed_dependency_telemetry",
            "registry_backed": True,
        },
    }


def generic_fill_pressure_gate(generic: dict[str, Any], candidate: dict[str, Any], limit: float = 0.0) -> dict[str, Any]:
    delta = metric_delta(generic.get("generic_fill_count", {}), candidate.get("generic_fill_count", {}))
    if delta.get("status") != "measured":
        return {
            "status": delta.get("status", SENTINEL_UNAVAILABLE),
            "promotion_blocked": False,
            "flag": None,
            "reason": delta.get("reason", "generic fill dependency was not measured"),
            "delta": delta,
            "limit": float(limit),
        }
    delta_value = float(delta.get("delta", 0.0) or 0.0)
    increased = delta_value > 0.0
    blocks = delta_value > float(limit)
    return {
        "status": "measured",
        "flag": "generic_fill_pressure_increase" if increased else None,
        "promotion_blocked": blocks,
        "delta": delta,
        "limit": float(limit),
        "comparison": f"{delta_value} > {float(limit)}",
    }


def interaction_loss_gate(generic: dict[str, Any], candidate: dict[str, Any], limit: float = 0.0) -> dict[str, Any]:
    delta = metric_delta(generic.get("interaction_candidates_selected", {}), candidate.get("interaction_candidates_selected", {}))
    lost_cards = lost_interaction_cards(generic, candidate)
    if delta.get("status") != "measured":
        return {
            "status": delta.get("status", SENTINEL_UNAVAILABLE),
            "promotion_blocked": False,
            "flag": None,
            "reason": delta.get("reason", "interaction selection was not measured"),
            "lost_interaction_cards": lost_cards,
            "delta": delta,
            "limit": float(limit),
        }
    loss_count = max(0.0, -float(delta.get("delta", 0.0) or 0.0))
    blocks = loss_count > float(limit)
    return {
        "status": "measured",
        "flag": "interaction_loss" if loss_count > 0 else None,
        "promotion_blocked": blocks,
        "lost_interaction_cards": lost_cards,
        "interaction_loss_count": round(loss_count, 4),
        "delta": delta,
        "limit": float(limit),
        "comparison": f"{loss_count} > {float(limit)}",
    }


def lost_interaction_cards(generic: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    generic_items = generic.get("interaction_candidates_selected_names", {}).get("items", {}) or {}
    candidate_items = candidate.get("interaction_candidates_selected_names", {}).get("items", {}) or {}
    lost = []
    for name, generic_count in sorted(generic_items.items()):
        if float(candidate_items.get(name, 0) or 0) < float(generic_count or 0):
            lost.append(str(name))
    return lost


def metric_delta(generic: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    generic_value = generic.get("average")
    candidate_value = candidate.get("average")
    if generic_value is None or candidate_value is None:
        return {
            "status": SENTINEL_UNAVAILABLE,
            "delta": None,
            "generic_status": generic.get("status", SENTINEL_UNAVAILABLE),
            "candidate_status": candidate.get("status", SENTINEL_UNAVAILABLE),
            "reason": "generic or candidate dependency value was not measured",
        }
    return {
        "status": "measured",
        "delta": round(float(candidate_value) - float(generic_value), 4),
        "generic_value": round(float(generic_value), 4),
        "candidate_value": round(float(candidate_value), 4),
    }


def dependency_gate_status(generic: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    generic_filler = generic.get("filler_dependency_score", {}).get("average")
    generic_repair = generic.get("repair_dependency_score", {}).get("average")
    candidate_filler = candidate.get("filler_dependency_score", {}).get("average")
    candidate_repair = candidate.get("repair_dependency_score", {}).get("average")
    if None in (generic_filler, generic_repair, candidate_filler, candidate_repair):
        return {
            "status": SENTINEL_UNAVAILABLE,
            "gate_evaluated": False,
            "reason": "generic or candidate dependency score was not measured",
            "gate_report": None,
        }
    gate = dependency_gate_report(
        {"filler_dependency": generic_filler, "repair_dependency": generic_repair},
        {"filler_dependency": candidate_filler, "repair_dependency": candidate_repair},
    )
    return {
        "status": "measured",
        "gate_evaluated": True,
        "passed": not gate["failures"],
        "failures": gate["failures"],
        "gate_report": gate,
    }
