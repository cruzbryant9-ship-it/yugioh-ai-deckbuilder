# Stabilization Z: H Variant Dry-Run Adapter

Explicit dry-run adapter branch only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_h_variant_dry_run_gate.py`
- `validate_stabilization_z.py`
- `STABILIZATION_Z_H_VARIANT_DRY_RUN_ADAPTER.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`

## H Variant Dry-Run Behavior

- Explicit variant: `public_overlay_restore_overlap_reduce_preparations`
- Starts from `public_overlay_reduce_generic_fill` behavior.
- Replaces one `Kashtira Preparations` with one `Kashtira Overlap` when legal.
- Remains non-default and dry-run.

## Gate Snapshot

- Runs: `2`
- Generic average score: `187.83`
- Public overlay average score: `188.46`
- H variant average score: `191.635`
- Delta vs generic: `3.805`
- Delta vs public overlay: `3.175`
- Recommendation: `eligible_for_experimental_candidate`

## Validation Results

- Passed: True
- Duration seconds: 308.8811
- PASS: default Kashtira remains generic
- PASS: current experimental remains unchanged
- PASS: public overlay remains unchanged
- PASS: H variant only runs with explicit variant flag
- PASS: H output marks dry_run_variant true
- PASS: interaction cards remain preserved
- PASS: generic_fill remains 0
- PASS: no builder defaults changed
- PASS: Stabilization Y validator still passes
- PASS: Stabilization U validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization AA should run an even broader explicit-candidate comparison before any discussion of making this path more than dry-run.
