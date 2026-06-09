# Stabilization Q: Executed Candidate Dependency Telemetry

Telemetry/remediation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `deck/executed_dependency_telemetry.py`
- `validate_stabilization_q.py`
- `STABILIZATION_Q_EXECUTED_DEPENDENCY_TELEMETRY.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`
- `kashtira_hybrid_overlay_regression_gate.py`
- `kashtira_experimental_regression_gate.py`
- `semi_specialized_experimental_comparison.py`
- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Telemetry Fields Added

- `safe_filler_used_count`
- `repair_used`
- `repair_success`
- `repair_action_count`
- `repair_dependency_score`
- `filler_dependency_score`
- `generic_fill_count`
- `interaction_preservation_attempted`
- `interaction_candidates_selected`
- `interaction_candidates_rejected`
- `interaction_rejection_reasons`

## Generic vs Experimental Dependency Comparison

- Experimental dependency gate status: `measured`
- Experimental dependency gate passed: `True`
- Experimental dependency delta: `{'safe_filler_used_count': {'status': 'measured', 'delta': 0.0, 'generic_value': 0.0, 'candidate_value': 0.0}, 'repair_action_count': {'status': 'measured', 'delta': 0.0, 'generic_value': 0.0, 'candidate_value': 0.0}, 'repair_dependency_score': {'status': 'measured', 'delta': 0.0, 'generic_value': 0.0, 'candidate_value': 0.0}, 'filler_dependency_score': {'status': 'measured', 'delta': 0.0, 'generic_value': 0.0, 'candidate_value': 0.0}, 'generic_fill_count': {'status': 'measured', 'delta': 15.0, 'generic_value': 0.0, 'candidate_value': 15.0}, 'interaction_candidates_selected': {'status': 'measured', 'delta': -4.0, 'generic_value': 4.0, 'candidate_value': 0.0}}`
- Hybrid dependency gate status: `measured`
- Hybrid dependency gate passed: `True`

## Unavailable Handling

- Missing dependency fields are summarized as explicit sentinel states such as `not_measured`, not as numeric zero.
- Measured zero remains numeric `0.0` only when the executed build report actually provided the field.

## Validation Results

- Passed: True
- Duration seconds: 228.0483
- PASS: executed reports include dependency telemetry
- PASS: generic vs experimental dependency deltas exist
- PASS: unavailable values remain explicit sentinel
- PASS: filler dependency gate can trigger from executed-shaped data
- PASS: repair dependency gate can trigger from executed-shaped data
- PASS: Phase 8M validator still passes or latest artifact is verified
- PASS: Phase 8J validator still passes
- PASS: Stabilization P validator still passes
- PASS: Stabilization O validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization R should decide whether generic-fill pressure belongs in a separate promotion gate, since executed telemetry now shows generic fill and interaction-preservation failures clearly even when repair/filler dependency gates pass.
