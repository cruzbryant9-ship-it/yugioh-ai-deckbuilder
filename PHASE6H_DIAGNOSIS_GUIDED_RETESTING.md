# Phase 6H: Diagnosis-Guided Ratio Recommendation + Targeted Retesting

Phase 6H turns Phase 6G diagnosis output into conservative ratio recommendations, retests those recommendations directly, and only stores them when they improve safely.

## What Was Added

- `deck/generic_ratio_recommender.py`
  - Converts diagnosis causes into targeted ratio profiles.
  - Examples:
    - `starter_density_low`: add starter/searcher slots.
    - `extender_shortage`: add extender slots.
    - `payoff_overfill`: reduce payoff count.
    - `brick_pressure_high`: reduce max bricks and payoff pressure.
    - `interruption_shortage`: add non-engine interruption slots.
    - `ratio_overfitting`: retest smaller baseline-adjacent changes.
- `deck/generic_targeted_retest.py`
  - Builds, repairs, scores, and safety-checks each recommended ratio.
  - Rejects illegal decks, blocked-card violations, hard legality warnings, low confidence, or non-improving recommendations.
- `generic_archetype_benchmark.py`
  - Runs targeted retests for medium/high diagnosis severity, declining trends, or noisy trends.
  - Adds targeted retest details to JSON and markdown reports.
- `deck/generic_ratio_memory.py`
  - Stores accepted and rejected targeted recommendations.
  - Tracks recommendation success rate and diagnosis-cause-to-adjustment outcomes.
- `deck/generic_benchmark_memory.py`
  - Stores the latest targeted retest result per archetype and mode.

## Safety Rules

Targeted recommendations are only accepted when:

- Every retest run produces a legal 40-card main deck.
- No blocked cards appear.
- No hard legality warnings are present.
- Generic confidence remains above the safety floor.
- Average score improves over the stored baseline by a safe margin.

Rejected recommendations are still recorded so the system learns which diagnosis adjustments are not worth repeating.

## How To Run

```powershell
python validate_phase6h.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira --mode meta --runs 3
```

The latest benchmark markdown report includes a `Targeted Retests` section.

## Limitations

Targeted retesting is still heuristic search over ratio profiles, not self-play or reinforcement learning. It can improve package balance, but it does not prove a deck is competitively optimal.

## Recommended Next Step

Phase 6I should add archetype-specific generic package quality explanations so accepted ratio changes can be tied to concrete card-role shifts.
