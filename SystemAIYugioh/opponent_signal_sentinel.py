from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Iterable


SENTINEL_KEY = "opponent_signal_sentinel"
SENTINEL_REASONS = ("not_run", "unavailable", "unsupported", "schema_missing")
SENTINEL_POLICY_VERSION = 1

OPPONENT_SIGNAL_KEYS = (
    "choke_stop_rate",
    "opponent_recovery_rate",
    "graph_stop_rate",
    "graph_pivot_rate",
    "probability_weighted_stop_rate",
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_starter_open_rate",
    "opponent_brick_rate",
)

OPPONENT_SIGNAL_AGGREGATION_KEYS = (
    *OPPONENT_SIGNAL_KEYS,
    "opponent_extender_open_rate",
    "opponent_interruption_open_rate",
    "opponent_pivot_success_rate",
    "opponent_backup_success_rate",
    "probability_weighted_resource_valid_rate",
    "probability_weighted_pivot_rate",
    "probability_weighted_backup_rate",
)


def opponent_signal_sentinel(reason: str, detail: str = "") -> dict[str, str]:
    if reason not in SENTINEL_REASONS:
        reason = "unavailable"
    payload = {SENTINEL_KEY: reason}
    if detail:
        payload["sentinel_reason"] = detail
    return payload


def is_opponent_signal_sentinel(value: Any) -> bool:
    return isinstance(value, dict) and value.get(SENTINEL_KEY) in SENTINEL_REASONS


def sentinel_reason(value: Any) -> str | None:
    if is_opponent_signal_sentinel(value):
        return str(value.get(SENTINEL_KEY))
    return None


def sentinel_display(value: Any) -> str:
    reason = sentinel_reason(value)
    if reason == "not_run":
        return "not run"
    if reason == "schema_missing":
        return "schema missing"
    if reason in {"unavailable", "unsupported"}:
        return reason
    return str(value)


def numeric_observation(value: Any) -> float | None:
    if is_opponent_signal_sentinel(value) or value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coalesce_opponent_signal(
    key: str,
    primary: dict[str, Any] | None,
    fallback: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> Any:
    provenance = provenance or {}
    if provenance.get("unsupported"):
        return opponent_signal_sentinel("unsupported", provenance.get("sentinel_reason", "opponent model unsupported"))
    if not isinstance(primary, dict) and not isinstance(fallback, dict):
        return opponent_signal_sentinel("not_run", "opponent simulation did not run")
    if isinstance(primary, dict) and key in primary:
        return primary[key]
    if isinstance(fallback, dict) and key in fallback:
        return fallback[key]
    return opponent_signal_sentinel("schema_missing", f"{key} missing from opponent signal reports")


def opponent_signal_provenance(
    matchup: Any = None,
    *,
    curated: bool = False,
    simulated: bool = True,
    unsupported: bool = False,
    sentinel_reason: str = "",
) -> dict[str, Any]:
    inferred = not curated and matchup is not None and not unsupported
    if matchup in ("", None):
        unsupported = True
        inferred = False
        sentinel_reason = sentinel_reason or "no opponent matchup/profile supplied"
    return {
        "curated": bool(curated),
        "inferred": bool(inferred),
        "simulated": bool(simulated and not unsupported),
        "unsupported": bool(unsupported),
        "sentinel_reason": sentinel_reason,
    }


def mean_observed(records: Iterable[dict[str, Any]], key: str, digits: int = 4, *, empty: Any | None = None) -> Any:
    values = []
    for record in records:
        observed = numeric_observation(record.get(key))
        if observed is not None:
            values.append(observed)
    if not values:
        return empty if empty is not None else opponent_signal_sentinel("unavailable", f"no numeric observations for {key}")
    return round(mean(values), digits)


def sentinel_counts(records: Iterable[dict[str, Any]], keys: Iterable[str] = OPPONENT_SIGNAL_AGGREGATION_KEYS) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = {key: Counter() for key in keys}
    for record in records:
        for key in keys:
            reason = sentinel_reason(record.get(key))
            if reason:
                counts[key][reason] += 1
    return {key: dict(counter) for key, counter in counts.items() if counter}


def numeric_counts(records: Iterable[dict[str, Any]], keys: Iterable[str] = OPPONENT_SIGNAL_AGGREGATION_KEYS) -> dict[str, int]:
    counts = Counter()
    for record in records:
        for key in keys:
            if numeric_observation(record.get(key)) is not None:
                counts[key] += 1
    return dict(counts)


def provenance_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for record in records:
        provenance = record.get("opponent_signal_provenance", {})
        if not isinstance(provenance, dict):
            continue
        for key in ("curated", "inferred", "simulated", "unsupported"):
            if provenance.get(key):
                counts[key] += 1
    return dict(counts)


def normalize_for_gate(value: Any) -> Any:
    if is_opponent_signal_sentinel(value):
        return 0.0
    if isinstance(value, dict):
        return {key: normalize_for_gate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_for_gate(item) for item in value]
    return value


def gate_normalization_metadata(value: Any, path: str = "") -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    paths: list[str] = []

    def visit(item: Any, current_path: str) -> None:
        reason = sentinel_reason(item)
        if reason:
            reasons[reason] += 1
            paths.append(current_path or "<root>")
            return
        if isinstance(item, dict):
            for key, child in item.items():
                visit(child, f"{current_path}.{key}" if current_path else str(key))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{current_path}[{index}]")

    visit(value, path)
    return {
        "gate_input_was_sentinel": bool(reasons),
        "gate_sentinel_reasons": dict(reasons),
        "gate_numeric_fallback_used": bool(reasons),
        "gate_sentinel_paths": paths[:50],
    }


def normalize_sentinels_for_legacy_gates(value: Any) -> Any:
    return normalize_for_gate(value)
