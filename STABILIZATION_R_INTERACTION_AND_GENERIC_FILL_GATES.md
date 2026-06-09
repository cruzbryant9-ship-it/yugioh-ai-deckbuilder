# Stabilization R: Interaction Loss + Generic Fill Promotion Gates

Safety-gate/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `validate_stabilization_r.py`
- `STABILIZATION_R_INTERACTION_AND_GENERIC_FILL_GATES.md`

## Files Changed

- `deck/executed_dependency_telemetry.py`
- `kashtira_hybrid_overlay_regression_gate.py`
- `kashtira_experimental_regression_gate.py`
- `semi_specialized_experimental_comparison.py`
- `projection_execution_parity_audit.py`

## Generic-Fill Gate Behavior

- Blocks promotion when candidate `generic_fill_count` is greater than generic baseline beyond the configured safety limit.
- Default safety limit: `0.0` additional generic-fill cards.
- Current experimental gate: `{'status': 'measured', 'flag': 'generic_fill_pressure_increase', 'promotion_blocked': True, 'delta': {'status': 'measured', 'delta': 15.0, 'generic_value': 0.0, 'candidate_value': 15.0}, 'limit': 0.0, 'comparison': '15.0 > 0.0'}`
- Hybrid gate: `{'status': 'measured', 'flag': 'generic_fill_pressure_increase', 'promotion_blocked': True, 'delta': {'status': 'measured', 'delta': 16.0, 'generic_value': 0.0, 'candidate_value': 16.0}, 'limit': 0.0, 'comparison': '16.0 > 0.0'}`

## Interaction-Loss Gate Behavior

- Uses `deck.interaction_core_registry` for the Kashtira interaction core.
- Blocks promotion when candidate selected interaction count is below generic baseline beyond the configured safety limit.
- Default safety limit: `0.0` lost interaction cards.
- Current experimental lost cards: `['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being']`
- Hybrid lost cards: `['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being']`

## Current Gate Results

- Experimental recommendation: `promote_blocked`
- Experimental blocking reasons: `['generic_fill_pressure_increase', 'interaction_loss']`
- Hybrid recommendation: `promote_blocked`
- Hybrid blocking reasons: `['generic_fill_pressure_increase', 'interaction_loss']`

## Validation Results

- Passed: True
- Duration seconds: 215.3923
- PASS: generic-fill increase blocks promotion in synthetic data
- PASS: interaction loss blocks promotion in synthetic data
- PASS: lost interaction cards are reported
- PASS: gates use interaction_core_registry
- PASS: gates run on executed data, not projection
- PASS: Phase 8M report includes new gate fields
- PASS: Phase 8J report includes new gate fields
- PASS: Stabilization Q validator still passes
- PASS: Stabilization P validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization S should investigate why the experimental and hybrid paths lose all registry interaction cards and rely on 15-16 generic-fill picks, but still keep any adapter changes behind explicit non-default execution gates.
