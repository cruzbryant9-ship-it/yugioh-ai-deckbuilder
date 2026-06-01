# Stabilization M: Opponent Metric Consolidation

This pass centralizes opponent metric assembly and summary formatting without changing gameplay, scoring, deck construction, memory influence, regression gate thresholds, or opponent intelligence behavior.

## Authoritative Builder

New shared path:

```text
SystemAIYugioh/opponent_metric_builder.py
```

Responsibilities:

- Collect opponent metrics from primary and fallback reports.
- Preserve sentinel values for missing, unavailable, unsupported, or not-run signals.
- Attach provenance fields for curated, inferred, simulated, unsupported, and sentinel reasons.
- Build report-ready averages that skip sentinels.
- Aggregate numeric, sentinel, and provenance counts.
- Normalize sentinels only for legacy regression gate compatibility.

## Metrics Migrated

The shared builder covers:

- `choke_stop_rate`
- `opponent_recovery_rate`
- `choke_coverage_score`
- `best_interruption_overlap`
- `poor_interruption_count`
- `timing_precision_score`
- `pivot_risk_score`
- `best_timing_window_count`
- `late_interruption_risk`
- `early_interruption_risk`
- `backup_line_success_rate`
- `graph_stop_rate`
- `graph_pivot_rate`
- `graph_endboard_reduction_score`
- `graph_best_interruption_count`
- `graph_poor_interruption_count`
- `graph_timing_precision_score`
- `opponent_resource_valid_rate`
- `opponent_resource_failure_rate`
- `opponent_pivot_success_rate`
- `opponent_backup_success_rate`
- `opponent_missing_card_failures`
- `opponent_missing_extra_failures`
- `opponent_once_per_turn_failures`
- `opponent_normal_summon_failures`
- `opponent_starter_open_rate`
- `opponent_extender_open_rate`
- `opponent_interruption_open_rate`
- `opponent_brick_rate`
- `probability_weighted_resource_valid_rate`
- `probability_weighted_stop_rate`
- `probability_weighted_pivot_rate`
- `probability_weighted_backup_rate`

## Consumers Migrated

- `matchup_matrix.py`
- `train_agent.py`
- `evaluate_learning.py`
- `post_side_evaluator.py`
- `analyze_opponent_deck.py`
- `deck/post_side_evaluation.py`
- `SystemAIYugioh/report_schema.py`

## Duplicate Code Removed

Removed duplicated per-script logic for:

- Primary/fallback opponent metric extraction.
- Sentinel-aware opponent means.
- Sentinel count aggregation.
- Provenance count aggregation.
- Legacy gate normalization call sites.

`matchup_matrix.py` also no longer owns local nested/flat opponent count aggregation helpers.

## Remaining Legacy Paths

Legacy regression gates still receive numeric-compatible summaries through:

```text
normalize_opponent_metrics_for_gates()
```

This preserves current gate outcomes and thresholds while report payloads retain sentinel detail.

Existing CLI print statements still default missing display fields to `0` for user-facing compatibility, but report aggregation and persisted metric fields use the shared builder.

## Sentinel Coverage Summary

Sentinel-aware coverage now includes:

- Pivot metrics: `pivot_risk_score`, `graph_pivot_rate`, `opponent_pivot_success_rate`, `probability_weighted_pivot_rate`.
- Backup metrics: `backup_line_success_rate`, `opponent_backup_success_rate`, `probability_weighted_backup_rate`.
- Interruption-risk metrics: `best_interruption_overlap`, `poor_interruption_count`, `timing_precision_score`, `best_timing_window_count`, `late_interruption_risk`, `early_interruption_risk`.
- Graph score metrics: `graph_stop_rate`, `graph_pivot_rate`, `graph_endboard_reduction_score`, `graph_best_interruption_count`, `graph_poor_interruption_count`, `graph_timing_precision_score`.

## Validation

Run:

```powershell
python validate_stabilization_m.py
python validate_stabilization_l.py
python validate_stabilization_k.py
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```
