# Phase 6J: Package Shift Replay Reports

Phase 6J adds readable before/after replay reports for generic ratio retests. It does not replace authored builders, change scoring weights, or add new gameplay mechanics.

## What Was Added

- `deck/generic_package_replay.py`
  - Builds a package replay report from a baseline deck and candidate deck.
  - Includes before/after package counts, main/Extra Deck counts, card deltas, role deltas, risk flags, and a markdown section.
- `deck/generic_targeted_retest.py`
  - Attaches `package_replay_report` to every tested recommendation.
  - Accepted and rejected recommendations both carry replay data.
- `generic_archetype_benchmark.py`
  - Adds `Before/After Package Replay` sections to benchmark markdown.
  - Adds a compact card-delta table.
  - Adds `--show-replay` for console previews.

## Replay Contents

Each replay includes:

- Before/after main deck package counts
- Before/after Extra Deck count
- Cards added and removed
- Copy increases and decreases
- Package gains/losses
- Risk flags
- A short explanation
- A markdown table for package movement
- A compact card-delta table

## CLI Usage

```powershell
python generic_archetype_benchmark.py --archetypes Branded Kashtira --mode meta --runs 3 --show-replay
```

The markdown report is still written to:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/latest_generic_benchmark_report.md
```

## Limitations

Replay reports explain deck construction changes, not exact duel causality. They are intended for human review of why a generic ratio candidate was accepted or rejected.

## Recommended Next Step

Phase 6K should add a compact HTML or rich markdown deck-diff artifact for easier side-by-side review across many archetypes.
