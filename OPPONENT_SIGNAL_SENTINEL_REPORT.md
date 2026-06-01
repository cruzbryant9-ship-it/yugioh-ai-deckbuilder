# Stabilization L: Opponent Signal Sentinel Integrity

This pass adds sentinel-aware opponent signal plumbing without changing gameplay scoring, deck construction, authored Blue-Eyes behavior, opponent influence, regression gate thresholds, or curated-opponent defaults.

## Sentinel Model

Opponent signal gaps now use explicit JSON-safe sentinel objects instead of silently collapsing to `0.0`.

Supported sentinels:

- `not_run`: opponent simulation did not execute.
- `unavailable`: aggregation had no numeric observations.
- `unsupported`: the opponent model/profile is not supported for the current path.
- `schema_missing`: the expected signal key was missing from the source report.

Measured numeric `0.0` is still preserved as a real observation.

## Numeric Signals

Sentinel-aware aggregation covers the required opponent signals:

- `choke_stop_rate`
- `opponent_recovery_rate`
- `graph_stop_rate`
- `graph_pivot_rate`
- `probability_weighted_stop_rate`
- `opponent_resource_valid_rate`
- `opponent_resource_failure_rate`
- `opponent_starter_open_rate`
- `opponent_brick_rate`

The same helper also supports adjacent opponent probability/resource signals used by matchup and post-side reports.

## Sentinel Counts

Reports now expose sentinel count buckets where aggregation happens:

- `opponent_signal_sentinel_counts`
- `opponent_signal_numeric_counts` where available
- `opponent_signal_provenance_counts`

Means and averages ignore sentinel values and average only actual numeric observations. If no numeric observations exist, the aggregate remains an `unavailable` sentinel instead of becoming `0.0`.

## Unsupported Counts

Unsupported opponent paths are represented as:

```json
{"opponent_signal_sentinel": "unsupported", "sentinel_reason": "..."}
```

These values are counted in `opponent_signal_sentinel_counts` and are not included in means.

## Curated Counts

Opponent provenance fields include:

- `curated`
- `inferred`
- `simulated`
- `unsupported`
- `sentinel_reason`

Curated opponent runs increment `opponent_signal_provenance_counts.curated`; this does not make curated opponents the default.

## Inferred Counts

Non-curated supported opponent profiles increment `opponent_signal_provenance_counts.inferred`. This is observability only and does not activate a new opponent influence path.

## Regression Safety

Regression gates continue to receive legacy-compatible numeric summaries through `normalize_sentinels_for_legacy_gates()`, which converts sentinel objects to `0.0` only for gate input compatibility. The stored reports keep sentinel detail so missing data remains visible.

No regression gate thresholds were changed.

## Touched Aggregation Paths

- `matchup_matrix.py`
- `train_agent.py`
- `evaluate_learning.py`
- `post_side_evaluator.py`
- `deck/post_side_evaluation.py`
- `SystemAIYugioh/report_schema.py`

## Validation

Run:

```powershell
python validate_stabilization_l.py
python validate_stabilization_k.py
python learning_signal_audit.py
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```
