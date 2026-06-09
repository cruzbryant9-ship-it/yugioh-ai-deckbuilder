# Stabilization U: Public Overlay Generic-Fill Pressure Reduction

Dry-run/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_public_overlay_tuning_gate.py`
- `validate_stabilization_u.py`
- `STABILIZATION_U_PUBLIC_OVERLAY_GENERIC_FILL_REDUCTION.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`

## Variants Tested

- `public_overlay_reduce_generic_fill`
- `public_overlay_archetype_fill_priority`
- `public_overlay_interaction_plus_archetype_core`

## Results

- Generic average score: `187.83`
- Best variant: `public_overlay_reduce_generic_fill`
- Best variant average score: `188.46`
- Best variant delta vs generic: `0.63`
- Best variant generic-fill average: `0.0`
- Best variant interaction selected average: `4.0`
- Best variant recommendation: `eligible_for_larger_sample`

## Variant Summary

- `public_overlay_reduce_generic_fill`: score `188.46`, delta `0.63`, generic fill `0.0`, interaction `4.0`, recommendation `eligible_for_larger_sample`
- `public_overlay_archetype_fill_priority`: score `188.205`, delta `0.375`, generic fill `0.0`, interaction `4.0`, recommendation `needs_retest`
- `public_overlay_interaction_plus_archetype_core`: score `187.15`, delta `-0.68`, generic fill `0.0`, interaction `4.0`, recommendation `keep_dry_run_only`

## Validation Results

- Passed: True
- Duration seconds: 418.4369
- PASS: all tuning variants are explicit-only
- PASS: default Kashtira remains generic
- PASS: current experimental remains unchanged
- PASS: public baseline overlay remains unchanged
- PASS: tuning variants preserve legal interaction cards
- PASS: tuning variants report generic-fill counts
- PASS: no builder defaults changed
- PASS: Stabilization T validator still passes
- PASS: Stabilization R validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization V should run a larger fixed-seed sample for `public_overlay_reduce_generic_fill` and inspect whether the score edge survives beyond the small dry-run gate.
