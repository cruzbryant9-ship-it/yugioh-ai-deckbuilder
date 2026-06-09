# Stabilization W: Public Overlay Delta Analysis

Analysis/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_public_overlay_delta_analysis.py`
- `validate_stabilization_w.py`
- `STABILIZATION_W_PUBLIC_OVERLAY_DELTA_ANALYSIS.md`

## Files Changed

- None; this phase adds analysis/reporting files only.

## Win/Loss Summary

- Score delta: `0.102`
- Positive / negative / neutral runs: `20` / `9` / `1`
- Recommendation: `eligible_for_targeted_adjustment`

## Average Component Deltas

- `consistency_score`: `0.0`
- `starter_score`: `0.0`
- `extender_score`: `0.0`
- `interruption_score`: `0.0`
- `brick_penalty`: `0.0`
- `endboard_score`: `0.7`
- `package_quality_score`: `2.9967`
- `generic_confidence_score`: `-0.7445`
- `final_score`: `0.102`

## Losing-Run Causes

- `package_quality_only_gain`: `9`

## Recurring Card Movements

- `added_in_winning_runs`: `[('Book of Eclipse', 40), ('Kashtira Preparations', 20)]`
- `removed_in_winning_runs`: `[('Kashtira Akstra', 20), ('Kashtira Overlap', 20), ('Tearlaments Kashtira', 20)]`
- `added_in_losing_runs`: `[('Book of Eclipse', 18), ('Kashtira Preparations', 9)]`
- `removed_in_losing_runs`: `[('Kashtira Akstra', 9), ('Kashtira Overlap', 9), ('Tearlaments Kashtira', 9)]`

## Validation Results

- Passed: True
- Duration seconds: 806.4764
- PASS: analysis runner works
- PASS: 30 run-level rows are produced
- PASS: component deltas are present
- PASS: winning/losing summaries are present
- PASS: loss clusters are present
- PASS: card-delta summary is present
- PASS: no behavior changes occur
- PASS: Stabilization V validator still passes
- PASS: Stabilization U validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization X should test a proposed-only targeted adjustment against the dominant losing-run cause before considering any active adapter change.
