# Phase 6G: Generic Trend Diagnosis

Phase 6G adds a diagnosis layer for generic archetype benchmarking. It does not replace authored Blue-Eyes logic, change scoring weights, or add duel simulation. The new system explains why generic tuning is declining, noisy, or repair-heavy.

## What Was Added

- `deck/generic_trend_diagnosis.py`
  - Diagnoses benchmark trends using latest package counts plus historical benchmark memory.
  - Returns suspected causes, severity, package pressure, confidence trend, repair dependency, and recommended adjustments.
- `deck/generic_benchmark_memory.py`
  - Stores the latest diagnosis per archetype and mode.
  - Keeps diagnosis metadata alongside trend and repair history.
- `deck/generic_tuner.py`
  - Reads the latest diagnosis and applies small capped ratio exploration nudges.
  - Does not override legality, banlist, custom limits, or repair checks.
- `generic_archetype_benchmark.py`
  - Adds a trend diagnosis section to the benchmark markdown report.
  - Includes whether diagnosis influenced the current tuning run.

## Diagnosis Categories

The diagnosis system can flag:

- `starter_density_low`
- `extender_shortage`
- `payoff_overfill`
- `brick_pressure_high`
- `interruption_shortage`
- `board_breaker_overfill`
- `repair_dependency_high`
- `confidence_declining`
- `quota_instability`
- `ratio_overfitting`
- `package_variance_high`

## Tuning Influence

Diagnosis influence is deliberately small and capped:

- Low starters: explore slightly more starters/searchers.
- Extender shortage: explore slightly more extenders.
- Payoff overfill: reduce payoff quota slightly.
- Brick pressure: reduce max bricks slightly.
- Interruption shortage: explore slightly more non-engine interruption.
- Repair dependency: prefer safer baseline-adjacent profiles.

The generic repair layer and legality checks still decide whether a deck is accepted.

## Validation

Run:

```powershell
python validate_phase6g.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira --mode meta --runs 3
```

The benchmark report at `SystemAIYugioh/data/training_runs/generic_benchmarks/latest_generic_benchmark_report.md` includes a `Trend Diagnosis` section.

## Limitations

The diagnosis is heuristic. It explains package pressure and trend symptoms, not exact duel causes. Some generic archetypes still need richer role inference before the diagnosis can be fully precise.

## Recommended Next Step

Phase 6H should use these diagnoses to produce safer archetype-specific ratio recommendations without changing authored deck builders.
