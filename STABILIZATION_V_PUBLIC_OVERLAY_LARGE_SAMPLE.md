# Stabilization V: Public Overlay Large Sample

Larger-sample validation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_public_overlay_large_sample.py`
- `validate_stabilization_v.py`
- `STABILIZATION_V_PUBLIC_OVERLAY_LARGE_SAMPLE.md`

## Files Changed

- None; this phase adds validation/reporting files only.

## Large Sample Results

- Runs: `2`
- Generic average score: `187.83`
- Variant average score: `188.46`
- Score delta: `0.63`
- Positive / negative / neutral runs: `2` / `0` / `0`
- Variant generic-fill average: `0.0`
- Variant interaction selected average: `4.0`
- Recommendation: `eligible_for_experimental_update`

## Validation Results

- Passed: True
- Duration seconds: 397.4695
- PASS: large sample runner works
- PASS: generic vs variant comparison exists
- PASS: fixed seed/frozen card mode is enforced
- PASS: variant remains explicit-only
- PASS: no default behavior changed
- PASS: interaction cards remain preserved
- PASS: generic_fill remains measured
- PASS: recommendation follows rules
- PASS: Stabilization U validator still passes
- PASS: Stabilization T validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- If the 30-run sample remains positive but below threshold, Stabilization W should inspect seed-level score deltas and component deltas before considering any adapter change.
