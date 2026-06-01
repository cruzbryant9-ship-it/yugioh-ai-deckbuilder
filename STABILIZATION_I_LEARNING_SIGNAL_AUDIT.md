# Stabilization I: Learning Signal Audit

Stabilization I adds an audit-only view of the current learning and advisory systems. It does not activate filler-memory influence, change scoring weights, add gameplay logic, or alter authored Blue-Eyes behavior.

## Audit Command

```powershell
python learning_signal_audit.py
```

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/learning_signal_audit/
```

Latest files:

- `latest_learning_signal_audit.json`
- `latest_learning_signal_audit.md`

## Signals Audited

The audit covers:

- `learned_card_stats`
- `learning_tuning`
- `learned_engine_stats`
- `matchup_engine_stats`
- `post_side_memory`
- `curated_opponent_memory`
- `generic_ratio_memory`
- `generic_benchmark_history`
- `generic_diff_index`
- `generic_filler_memory`
- `filler_signal_gates`
- diagnosis bias
- diff-index bias
- filler-memory bias

## Classification Buckets

The report classifies each signal into one or more buckets:

- `active`: currently influences generation, scoring, tuning, matchup selection, or side planning
- `useful`: enough current evidence or integration value to keep enabled
- `no-op`: code path exists but recent evidence shows no behavior change
- `noisy`: evidence exists but should remain capped or experimental
- `reporting-only`: produces analysis/gates/reports but does not directly influence deck choices
- `stale`: memory exists but has not been refreshed recently
- `unsafe-to-influence`: should not directly drive choices yet
- `experimental`: intentionally limited or flag-gated

## Current Safety Expectations

`generic_filler_memory` remains reporting-only and unsafe to influence directly.

`filler-memory bias` remains disabled by default. Phase 6U showed:

- ordering changes: `0`
- selection changes: `0`

That means filler-memory influence is safe enough to keep as an explicit experiment, but it is still no-op evidence, not proof of usefulness.

## Recommendation Meanings

Each signal receives one recommendation:

- `keep active`: leave enabled in current paths
- `keep experimental`: keep flag-gated or advisory-only
- `disable`: remove from active influence if future audit finds harm
- `collect more data`: continue reporting or benchmark collection before increasing influence
- `retire`: candidate for future cleanup if it remains unused/stale

## Validation

```powershell
python validate_stabilization_i.py
```

The validator checks that every required signal is present, summary buckets are populated, filler-memory bias is still no-op/experimental, generic filler memory remains reporting-only/unsafe-to-influence, reports save correctly, and the audit CLI runs.
