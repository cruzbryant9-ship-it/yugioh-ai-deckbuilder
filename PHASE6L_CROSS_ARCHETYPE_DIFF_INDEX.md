# Phase 6L: Cross-Archetype Diff Indexing

Phase 6L adds an advisory memory index for recurring helpful and harmful card/package movements across generic archetype benchmark reports. It does not change scoring, legality, authored Blue-Eyes behavior, or deck acceptance rules.

## What Was Added

- `deck/generic_diff_index.py`
  - Builds a cross-archetype diff index from benchmark results.
  - Persists long-term movement memory to:
    - `SystemAIYugioh/data/deck_profiles/generic_diff_index.json`
- `generic_archetype_benchmark.py`
  - Updates the diff index after each benchmark.
  - Adds a `Cross-Archetype Diff Index` section to the latest benchmark markdown.
  - Adds advisory warnings when a current run repeats historically harmful movements.

## Indexed Signals

The index tracks:

- Helpful card additions
- Harmful card additions
- Helpful card removals
- Harmful card removals
- Helpful package gains/losses
- Harmful package gains/losses
- Recurring risk flags
- Recurring repair actions
- Affected archetypes

Each movement stores count, affected archetypes, last seen timestamp, and average score delta when available.

## Advisory Warnings

Warnings are advisory only. They do not reject a deck unless existing legality, score, or regression checks fail.

Examples:

- Candidate adds a historically harmful card movement.
- Candidate removes a historically helpful card movement.
- Candidate repeats a historically harmful package movement.

## Run

```powershell
python validate_phase6l.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick --mode meta --runs 3 --show-replay
```

## Limitations

The index is correlation-based. It tells you movements that repeatedly appeared in helpful or harmful retests, but it does not prove exact duel causality.

## Recommended Next Step

Phase 6M should make the generic tuner read this index as a capped advisory prior, without changing legality or score gates.
