# Phase 6F: Generic Benchmark History + Trend Memory

Phase 6F adds persistent benchmark history for generic archetype tuning and repair.

## History File

Generic benchmark history is stored at:

```text
SystemAIYugioh/data/deck_profiles/generic_benchmark_history.json
```

The history is keyed by archetype and mode.

## Tracked Fields

Each archetype profile tracks:

- total benchmark runs
- average normal score
- average tuned score
- average improvement
- best improvement
- worst improvement
- tuning hurt count
- repair success rate history
- average repair actions
- rejected deck count
- memory update count
- best ratio patterns
- bad ratio patterns
- trend direction

Trend direction can be:

- improving
- stable
- declining
- noisy

## Acceptance Rules

Runs contribute to positive trend patterns only when:

- tuned deck is legal
- blocked-card checks pass
- improvement is not meaningfully negative
- confidence does not collapse

Bad runs are still stored in history, but they do not overwrite best-known ratio patterns.

## Benchmark Reports

`generic_archetype_benchmark.py` now appends history after every benchmark and extends `latest_generic_benchmark_report.md` with:

- historical trend table
- long-term leaders
- noisy/follow-up archetypes
- repair reliability by archetype

## Limitations

Trend labels are lightweight statistical summaries, not predictive models. They are meant to flag consistency and risk, not replace deeper future evaluation.
