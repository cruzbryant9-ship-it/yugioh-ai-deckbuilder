# Phase 6D: Generic Build Benchmarking

Phase 6D adds a benchmark runner for generic deck construction and tuning across multiple archetypes.

## Runner

```bash
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 10
```

For each archetype, the runner:

- builds a normal generic deck without ratio memory
- runs the generic tuner
- compares normal score vs tuned score
- records confidence, package counts, quota warnings, legality, blocked-card violations, and skeleton coverage
- updates ratio memory only when the tuned deck safely improves
- records bad ratio patterns when tuning hurts or confidence collapses

## Reports

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/
```

The latest readable report is:

```text
SystemAIYugioh/data/training_runs/generic_benchmarks/latest_generic_benchmark_report.md
```

## Safety Rules

Ratio memory is updated only if:

- tuned deck is legal
- no blocked cards appear
- tuning improves score
- confidence does not collapse

Bad ratio patterns are recorded instead of replacing good memory.

## Summary Metrics

The benchmark summary reports:

- best improved archetype
- worst improved archetype
- average improvement
- archetypes where tuning hurt performance
- reliable ratio patterns
- common package weaknesses
- common quota warnings

## Limitations

The benchmark evaluates generic heuristic builds only. It does not perform self-play, reinforcement learning, or exact duel simulation.
