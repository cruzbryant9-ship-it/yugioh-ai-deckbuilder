# Phase 6Q: Filler Signal Eligibility Gates

Phase 6Q defines the gate framework that must pass before filler-memory evidence can ever become an advisory input. It does not activate filler-memory influence, change scoring, or alter authored Blue-Eyes behavior.

## Gate Predicates

The gate evaluator lives in `deck/filler_signal_gates.py`.

- `observation_floor`: requires enough total legal observations before a filler card can be considered.
- `archetype_breadth`: requires evidence from multiple archetypes so one deck family cannot create a global signal alone.
- `concentration_clearance`: blocks signals dominated by one archetype, such as Runick-only evidence.
- `attribution_majority`: requires most observations to be single-card attribution, not shared multi-card credit.
- `indeterminate_suppression`: blocks cards whose evidence is mostly indeterminate.
- `confidence_floor`: requires strong attribution confidence.
- `score_stability`: requires non-negative average score evidence without too many negative observations.
- `provenance_clean`: requires non-validator, legal observations with no illegal-observation contamination.
- `advisory_budget_available`: verifies advisory budget would exist if influence were later enabled.
- `kill_switch_enabled`: passes only when the global advisory kill switch is not active.
- `completion_bias_suppression`: blocks cards that mostly complete decks without showing performance evidence.

## Eligibility Report

`filler_signal_gate_report.py` evaluates current filler memory and reports:

- eligible signals
- near-eligible signals
- failed signals
- concentration warnings
- support failures
- archetype-breadth failures
- attribution failures

It can be run directly:

```powershell
python filler_signal_gate_report.py --save
```

Reports are written to:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/latest_filler_signal_gate_report.json
SystemAIYugioh/data/training_runs/generic_benchmarks/latest_filler_signal_gate_report.md
```

## Benchmark Integration

Generic benchmark reports now include a filler signal gate summary:

- cards closest to eligibility
- cards blocked by concentration
- cards blocked by attribution
- cards blocked by support
- eligible signal count

This is reporting only. The data does not influence filler selection.

## Current Expected State

Current filler memory is expected to produce zero eligible cards. Runick-only evidence, shared attribution, low attribution confidence, and indeterminate-heavy observations should remain blocked.

## Phase 6R Readiness

Phase 6R should only consider filler-memory influence after meaningful single-card attribution exists across multiple archetypes and the Phase 6Q gates show at least one clean eligible signal.
