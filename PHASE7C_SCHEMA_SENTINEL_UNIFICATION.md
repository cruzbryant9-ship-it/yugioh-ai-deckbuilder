# Phase 7C: Schema & Sentinel Unification

Infrastructure-only phase. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression thresholds, filler-memory activation, or opponent influence activation were changed.

## Schema Changes

Opponent metric payloads now include:

- `opponent_metric_schema_version`
- `sentinel_policy_version`
- `sentinel_counts`
- `numeric_observation_counts`
- `unsupported_counts`
- `simulated_counts`
- `curated_counts`
- `inferred_counts`

Backward-compatible legacy aliases remain:

- `opponent_signal_sentinel_counts`
- `opponent_signal_numeric_counts`
- `opponent_signal_provenance_counts`

## Normalization Path

Canonical sentinel handling lives in:

```text
SystemAIYugioh/opponent_signal_sentinel.py
```

The report-facing builder path is:

```text
SystemAIYugioh/opponent_metric_builder.py
```

Canonical functions:

- `normalize_for_gate()`
- `gate_normalization_metadata()`
- `display_opponent_metric()`
- `opponent_metric_payload_metadata()`

Backward-compatible imports are preserved for older callers, but they delegate to the canonical path.

## Gate Transparency Behavior

Regression gate numeric behavior is unchanged: sentinels normalize to `0.0` for legacy gate input compatibility.

Gate reports now add:

- `gate_input_was_sentinel`
- `gate_sentinel_reasons`
- `gate_numeric_fallback_used`
- `gate_sentinel_paths`

These fields are reporting-only and do not change thresholds or pass/fail behavior.

## Reports And CLI Examples

CLI/report display now renders sentinel states as words instead of fake numeric zero:

- `not_run` -> `not run`
- `unsupported` -> `unsupported`
- `unavailable` -> `unavailable`
- `schema_missing` -> `schema missing`

Example:

```text
Graph stop rate: schema missing
Opponent brick rate: unavailable
```

## Remaining Risks

- Some non-opponent metrics still use legacy `get(..., 0)` display defaults.
- Older generated JSON reports will not contain Phase 7C schema fields until regenerated.
- Backward-compatible aliases remain intentionally, so static scans may still find old names even though they route through the canonical implementation.
