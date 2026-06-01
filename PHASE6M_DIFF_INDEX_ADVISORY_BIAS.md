# Phase 6M: Diff-Index Advisory Tuning Bias + Memory Scrub

## Purpose

Phase 6M safely enables diff-index awareness after Stabilization G isolated validator memory and added provenance.

This is not a scoring change. Diff-index memory does not veto decks and does not override legality, banlist/custom limits, repair checks, or score-based acceptance.

## Memory Scrub

`deck/generic_diff_index.py` now provides:

```python
scrub_diff_index_memory()
```

It removes or quarantines known old validation probe data such as:

- `Index Probe`
- `Card Probe`
- `Warning Probe`
- `Helpful Add`
- `Harmful Add`
- `Helpful Remove`
- `Harmful Remove`
- records marked `validator_generated=True`

The scrub report is written to:

```text
SystemAIYugioh/data/deck_profiles/generic_diff_index_scrub_report.json
```

## Advisory Signals

`get_diff_index_advisory_signal(archetype, candidate_card_movements)` reads the scrubbed diff index and produces advisory hints from supported card movements.

It ignores:

- validator-generated records
- low-support movements
- contested movements
- legality-driven rejection data
- known probe names

It reports:

- helpful/harmful hints
- suppressed low-support signals
- contested signals
- capped advisory signal

## Tuner Integration

`deck/generic_tuner.py` now computes card movements for each generic tuning candidate and attaches diff-index advisory metadata.

The tuner still selects by:

1. raw score
2. advisory tie-break nudge
3. confidence

This means a lower-scoring deck cannot beat a higher-scoring deck because of diff-index memory alone.

## Influence Budget

Diff-index bias uses `deck/advisory_influence_budget.py`.

Diagnosis bias and diff-index bias share one global advisory cap. The global kill switch disables diff-index influence.

## Benchmark Reporting

`generic_archetype_benchmark.py` now reports:

- `diff_index_bias_used`
- `advisory_budget_used`
- `advisory_signals_applied`
- `suppressed_low_support_signals`
- `contested_signals`
- `scrub_report_summary`

## Validation

Run:

```bash
python validate_phase6m.py
```

It verifies memory scrub behavior, low-support filtering, contested-signal suppression, budget caps, kill switch behavior, score-first candidate selection, legality rejection filtering, benchmark compatibility, Phase 6L compatibility, Stabilization G compatibility, and matchup matrix smoke.

## Limitations

The diff index is advisory only. It can help order equally scoring candidates, but it does not yet create new ratio recommendations by itself. That keeps the project safe while collecting cleaner post-scrub memory.
