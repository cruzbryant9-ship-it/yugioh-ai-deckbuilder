# Phase 8K: Kashtira Experimental Regression Analysis

Analysis/reporting only. No gameplay behavior, builder behavior, scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, full combo graphs, or generic builder behavior were changed.

## Files Created

- `kashtira_experimental_regression_analysis.py`
- `validate_phase8k.py`
- `PHASE8K_KASHTIRA_REGRESSION_ANALYSIS.md`

## Files Changed

- None

## Largest Negative Components

- `final_score`: -2.252
- None

## Largest Positive Components

- `package_quality_score`: 2.117
- `brick_penalty`: 1.6
- `consistency_score`: 1.2
- `endboard_score`: 0.4
- None

## Card-Level Differences

- Added `Book of Eclipse`: +30 (board_breakers)
- Added `Divine Arsenal AA-ZEUS - Sky Thunder`: +10 (extra_deck_payoffs)
- Added `Kashtira Preparations`: +10 (interruptions)
- Added `Kashtira Shangri-Ira`: +10 (extra_deck_payoffs)
- Added `Number 11: Big Eye`: +10 (extra_deck_payoffs)
- Removed `Ash Blossom & Joyous Spring`: -10 (other)
- Removed `D.D. Crow`: -10 (other)
- Removed `Ghost Belle & Haunted Mansion`: -10 (other)
- Removed `Nibiru, the Primal Being`: -10 (other)

## Package-Level Differences

- `board_breakers`: +3.0
- `extenders`: -9.0
- `extra_deck_payoffs`: +3.0
- `generic_fill`: +15.0
- `starters`: +12.0
- `starters_searchers`: -21.0

## Root-Cause Summary

- quota/package quality improves, but scoring components regress
- experimental path increases brick penalty
- experimental path relies on generic fill after quota picks, suggesting adapter selection needs tuning
- experimental path repeatedly removes generic-selected cards associated with higher score

## Recommendation

- `adjust_adapter_selection`

## Validation Results

- Passed: True
- Duration seconds: 8250.2477
- PASS: analyzer runs
- PASS: fixed-seed/frozen-card mode is used
- PASS: generic and experimental are compared
- PASS: component deltas are reported
- PASS: card-level differences are reported
- PASS: package-level differences are reported
- PASS: recommendation is report-only
- PASS: experimental path remains off by default
- PASS: Phase 8J validator still passes
- PASS: Phase 8I validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8L

- Create a proposed-only adapter tuning plan based on the regression analysis, then test it under the fixed-seed Phase 8J gate before applying any code behavior change.
