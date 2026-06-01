# Phase 6K: Rich Deck-Diff Review Artifacts

Phase 6K creates per-archetype deck-diff artifacts for human review. It does not replace authored builders, change scoring weights, or add new gameplay systems.

## What Was Added

- `deck/generic_deck_diff_report.py`
  - Builds rich deck-diff reports from baseline, tuned, and targeted retest data.
  - Produces markdown and simple dependency-free HTML.
- `generic_archetype_benchmark.py`
  - Saves per-archetype deck-diff artifacts under:
    - `SystemAIYugioh/data/training_runs/generic_benchmarks/deck_diffs/`
  - Adds artifact links to the main benchmark markdown report.

## Artifact Paths

For each archetype, the benchmark writes:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/deck_diffs/latest_<archetype>_deck_diff.md
SystemAIYugioh/data/training_runs/generic_benchmarks/deck_diffs/latest_<archetype>_deck_diff.html
```

Examples:

```text
latest_branded_deck_diff.md
latest_kashtira_deck_diff.md
```

## Report Sections

Each rich diff includes:

- Score Summary
- Baseline Deck
- Tuned Deck
- Package Count Comparison
- Cards Added
- Cards Removed
- Copy Changes
- Repair Actions
- Accepted Recommendations
- Rejected Recommendations
- Risk Flags
- Human Review Notes

## CLI Usage

```powershell
python generic_archetype_benchmark.py --archetypes Branded Kashtira --mode meta --runs 3 --show-replay
```

The `--show-replay` flag still prints compact replay snippets to the console, while the rich artifacts are always saved when benchmark reports are saved.

## Limitations

The artifacts are static markdown/HTML. They are meant for fast review, not interactive filtering or full duel-causality analysis.

## Recommended Next Step

Phase 6L should add cross-archetype diff indexing so the system can summarize recurring harmful card movements across many generic archetypes.
