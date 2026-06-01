# Phase 6S: Eligible Filler Signal Holdout Review

Phase 6S reviews filler-memory signals that passed Phase 6Q gates after Phase 6R attribution collection. It does not activate filler-memory influence, change scoring, change authored Blue-Eyes behavior, or relax legality rules.

## Goal

Eligibility gates prove that a filler signal has enough clean historical support. Holdout review checks whether that signal still looks useful in fresh controlled comparisons outside the attribution accumulation path.

## Runner

Run:

```powershell
python filler_signal_holdout_review.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 3
```

The runner:

1. Loads eligible filler signals from `filler_signal_gate_report.py`.
2. Builds fresh generic baseline decks.
3. Tests each eligible filler with the same one-card controlled comparison used by Phase 6R.
4. Records positive, neutral, and negative holdout outcomes.
5. Saves holdout reports without updating filler memory.

## Holdout Outcome Rules

Each test is classified by score delta:

- `positive`: score delta >= `0.5`
- `neutral`: score delta between `-0.5` and `0.5`
- `negative`: score delta <= `-0.5`

A filler passes holdout when:

- enough tests remain clean single-card comparisons
- average holdout delta is non-negative
- negative result rate stays conservative
- positive plus neutral results are at least as common as negative results

## Gate Report Integration

`filler_signal_gate_report.py` now adds:

- `holdout_required`
- `holdout_passed`
- `holdout_average_delta`
- `holdout_support_count`
- `holdout_contradiction_count`
- `activation_ready`

A filler is activation-ready only when:

```text
eligibility_gates_passed AND holdout_passed
```

Activation-ready status is still reporting only. It does not enable influence.

## Reports

Holdout reports are saved to:

```text
SystemAIYugioh/data/training_runs/filler_holdout/latest_filler_holdout_report.json
SystemAIYugioh/data/training_runs/filler_holdout/latest_filler_holdout_report.md
```

The gate report is also refreshed:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/latest_filler_signal_gate_report.md
```

## Limitations

This is still heuristic deck scoring, not duel self-play. Holdout results are useful as a safety check, but Phase 6T should keep any first influence activation small, capped, reversible, and monitored.
