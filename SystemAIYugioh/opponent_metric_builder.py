from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from SystemAIYugioh.opponent_signal_sentinel import (
    OPPONENT_SIGNAL_AGGREGATION_KEYS,
    SENTINEL_POLICY_VERSION,
    coalesce_opponent_signal,
    gate_normalization_metadata,
    mean_observed,
    normalize_for_gate,
    numeric_counts,
    numeric_observation,
    opponent_signal_provenance,
    sentinel_display,
    provenance_counts,
    sentinel_counts,
)


OPPONENT_METRIC_KEYS = (
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
    "graph_stop_rate",
    "graph_pivot_rate",
    "graph_endboard_reduction_score",
    "graph_best_interruption_count",
    "graph_poor_interruption_count",
    "graph_timing_precision_score",
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_pivot_success_rate",
    "opponent_backup_success_rate",
    "opponent_missing_card_failures",
    "opponent_missing_extra_failures",
    "opponent_once_per_turn_failures",
    "opponent_normal_summon_failures",
    "opponent_starter_open_rate",
    "opponent_extender_open_rate",
    "opponent_interruption_open_rate",
    "opponent_brick_rate",
    "probability_weighted_resource_valid_rate",
    "probability_weighted_stop_rate",
    "probability_weighted_pivot_rate",
    "probability_weighted_backup_rate",
)
OPPONENT_METRIC_SCHEMA_VERSION = 1

NUMERIC_OPPONENT_METRIC_KEYS = tuple(
    key for key in OPPONENT_METRIC_KEYS if key not in {"opponent_missing_card_failures", "opponent_missing_extra_failures"}
)


def build_opponent_metric_bundle(
    primary: dict[str, Any] | None,
    fallback: dict[str, Any] | None = None,
    *,
    matchup: Any = None,
    curated: bool = False,
    simulated: bool = True,
    unsupported: bool = False,
    sentinel_reason: str = "",
    keys: Iterable[str] = OPPONENT_METRIC_KEYS,
) -> dict[str, Any]:
    provenance = opponent_signal_provenance(
        matchup,
        curated=curated,
        simulated=simulated,
        unsupported=unsupported,
        sentinel_reason=sentinel_reason,
    )
    bundle = {
        key: coalesce_opponent_signal(key, primary, fallback, provenance)
        for key in keys
    }
    bundle["opponent_signal_provenance"] = provenance
    bundle.update(opponent_metric_payload_metadata([bundle], keys=keys))
    return bundle


def summarize_opponent_metrics(
    records: Iterable[dict[str, Any]],
    *,
    prefix: str = "average_",
    keys: Iterable[str] = NUMERIC_OPPONENT_METRIC_KEYS,
    include_counts: bool = True,
) -> dict[str, Any]:
    rows = list(records)
    summary = {
        f"{prefix}{key}": mean_observed(rows, key, metric_digits(key))
        for key in keys
    }
    if include_counts:
        summary.update(opponent_metric_payload_metadata(rows, keys=keys))
    return summary


def opponent_metric_payload_metadata(records: Iterable[dict[str, Any]], keys: Iterable[str] = NUMERIC_OPPONENT_METRIC_KEYS) -> dict[str, Any]:
    rows = list(records)
    numeric = numeric_counts(rows, keys)
    sentinels = sentinel_counts(rows, keys)
    provenance = provenance_counts(rows)
    return {
        "opponent_metric_schema_version": OPPONENT_METRIC_SCHEMA_VERSION,
        "sentinel_policy_version": SENTINEL_POLICY_VERSION,
        "sentinel_counts": sentinels,
        "numeric_observation_counts": numeric,
        "unsupported_counts": unsupported_counts_from_sentinels(sentinels, provenance),
        "simulated_counts": provenance.get("simulated", 0),
        "curated_counts": provenance.get("curated", 0),
        "inferred_counts": provenance.get("inferred", 0),
        "opponent_signal_numeric_counts": numeric,
        "opponent_signal_sentinel_counts": sentinels,
        "opponent_signal_provenance_counts": provenance,
    }


def unsupported_counts_from_sentinels(sentinels: dict[str, dict[str, int]], provenance: dict[str, int]) -> dict[str, Any]:
    per_signal = {
        signal: counts.get("unsupported", 0)
        for signal, counts in sentinels.items()
        if counts.get("unsupported", 0)
    }
    return {"total": sum(per_signal.values()) + provenance.get("unsupported", 0), "signals": per_signal}


def metric_digits(key: str) -> int:
    if key.endswith("_count") or key.endswith("_failures"):
        return 2
    if key.endswith("_score") and not key.endswith("_rate"):
        return 4
    return 4


def observed_metric_totals(records: Iterable[dict[str, Any]], keys: Iterable[str]) -> tuple[Counter[str], Counter[str]]:
    totals: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for record in records:
        for key in keys:
            observed = numeric_observation(record.get(key))
            if observed is not None:
                totals[key] += observed
                counts[key] += 1
    return totals, counts


def observed_average_from_totals(totals: Counter[str], counts: Counter[str], key: str, digits: int = 4) -> Any:
    if counts[key]:
        return round(totals[key] / counts[key], digits)
    return mean_observed([], key, digits)


def aggregate_flat_counts(records: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        values = record.get(key, {})
        if isinstance(values, dict):
            for name, count in values.items():
                try:
                    counts[str(name)] += int(count)
                except (TypeError, ValueError):
                    continue
    return dict(counts)


def aggregate_nested_counts(records: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        values = record.get(key, {})
        if not isinstance(values, dict):
            continue
        for signal, signal_counts in values.items():
            if not isinstance(signal_counts, dict):
                continue
            for reason, count in signal_counts.items():
                try:
                    counts[str(signal)][str(reason)] += int(count)
                except (TypeError, ValueError):
                    continue
    return {signal: dict(signal_counts) for signal, signal_counts in counts.items()}


def aggregate_opponent_count_reports(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    legacy_sentinels = aggregate_nested_counts(rows, "opponent_signal_sentinel_counts")
    legacy_numeric = aggregate_flat_counts(rows, "opponent_signal_numeric_counts")
    legacy_provenance = aggregate_flat_counts(rows, "opponent_signal_provenance_counts")
    return {
        "opponent_metric_schema_version": OPPONENT_METRIC_SCHEMA_VERSION,
        "sentinel_policy_version": SENTINEL_POLICY_VERSION,
        "sentinel_counts": aggregate_nested_counts(rows, "sentinel_counts") or legacy_sentinels,
        "numeric_observation_counts": aggregate_flat_counts(rows, "numeric_observation_counts") or legacy_numeric,
        "unsupported_counts": aggregate_nested_unsupported_counts(rows),
        "simulated_counts": sum_int_field(rows, "simulated_counts") or legacy_provenance.get("simulated", 0),
        "curated_counts": sum_int_field(rows, "curated_counts") or legacy_provenance.get("curated", 0),
        "inferred_counts": sum_int_field(rows, "inferred_counts") or legacy_provenance.get("inferred", 0),
        "opponent_signal_sentinel_counts": aggregate_nested_counts(rows, "opponent_signal_sentinel_counts"),
        "opponent_signal_numeric_counts": aggregate_flat_counts(rows, "opponent_signal_numeric_counts"),
        "opponent_signal_provenance_counts": aggregate_flat_counts(rows, "opponent_signal_provenance_counts"),
    }


def normalize_opponent_metrics_for_gates(value: Any) -> Any:
    return normalize_for_gate(value)


def opponent_gate_normalization_metadata(value: Any) -> dict[str, Any]:
    return gate_normalization_metadata(value)


def display_opponent_metric(value: Any) -> str:
    return sentinel_display(value)


def opponent_metric_report_fields(records: Iterable[dict[str, Any]], keys: Iterable[str] = NUMERIC_OPPONENT_METRIC_KEYS) -> dict[str, Any]:
    return opponent_metric_payload_metadata(records, keys=keys)


def opponent_metric_keys() -> tuple[str, ...]:
    return OPPONENT_METRIC_KEYS


def numeric_opponent_metric_keys() -> tuple[str, ...]:
    return NUMERIC_OPPONENT_METRIC_KEYS


def sentinel_coverage_keys() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*OPPONENT_SIGNAL_AGGREGATION_KEYS, *NUMERIC_OPPONENT_METRIC_KEYS)))


def sum_int_field(records: Iterable[dict[str, Any]], key: str) -> int:
    total = 0
    for record in records:
        try:
            total += int(record.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def aggregate_nested_unsupported_counts(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    signals: Counter[str] = Counter()
    total = 0
    for record in records:
        counts = record.get("unsupported_counts", {})
        if not isinstance(counts, dict):
            continue
        try:
            total += int(counts.get("total", 0) or 0)
        except (TypeError, ValueError):
            pass
        nested = counts.get("signals", {})
        if isinstance(nested, dict):
            for signal, count in nested.items():
                try:
                    signals[str(signal)] += int(count)
                except (TypeError, ValueError):
                    continue
    return {"total": total, "signals": dict(signals)}
