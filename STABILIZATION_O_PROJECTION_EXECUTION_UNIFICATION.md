# Stabilization O: Projection vs Execution Unification

Audit-only architecture remediation. No scoring, deck construction, default semi-specialized behavior, Blue-Eyes authored behavior, memory influence, promotion status, neural methods, self-play, duel engine, or combo graph behavior was changed.

## Files Created

- `deck/interaction_core_registry.py`
- `projection_execution_parity_audit.py`
- `validate_stabilization_o.py`
- `STABILIZATION_O_PROJECTION_EXECUTION_UNIFICATION.md`
- `SystemAIYugioh/data/training_runs/architecture_audit/latest_projection_execution_parity_report.json`
- `SystemAIYugioh/data/training_runs/architecture_audit/latest_projection_execution_parity_report.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`
- `deck/semi_specialized_adapter_tuning.py`
- `kashtira_adapter_tuning_plan.py`
- `kashtira_hybrid_overlay_regression_gate.py`
- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Dependency Gate Findings

- `filler_dependency_gate`: `0.0 > 0.0` at `deck/semi_specialized_builder_adapter.py` line 566
  Classification: `active_candidate_vs_baseline_gate`; can trigger: `True`; currently triggered: `False`.
  Note: No further correction in Stabilization P; future work should improve candidate dependency measurement fidelity if needed.
- `repair_dependency_gate`: `0.0 > 0.0` at `deck/semi_specialized_builder_adapter.py` line 574
  Classification: `active_candidate_vs_baseline_gate`; can trigger: `True`; currently triggered: `False`.
  Note: No further correction in Stabilization P; future work should improve candidate dependency measurement fidelity if needed.

## Interaction Registry Findings

- Registry owner: `deck.interaction_core_registry`
- Kashtira interaction core: Ash Blossom & Joyous Spring, Ghost Belle & Haunted Mansion, D.D. Crow, Nibiru, the Primal Being
- Registry-backed users: 8
- Migrated modules: `deck/semi_specialized_adapter_tuning.py`, `deck/semi_specialized_builder_adapter.py`, `kashtira_adapter_tuning_plan.py`, `kashtira_hybrid_overlay_regression_gate.py`
- Remaining hardcoded source users: 7
- Promotion paths using hardcoded interaction lists: 0

## Projection vs Execution Mismatch

| Metric | Projected | Executed | Abs Delta | Percent Delta | Classification |
| --- | ---: | ---: | ---: | ---: | --- |
| score | 188.138 | 185.205 | -2.933 | -1.559 | severe_mismatch |
| package_quality | 83.237 | 79.78 | -3.457 | -4.1532 | warning |
| quota_balance | 20.65 | 27.0 | 6.35 | 30.7506 | severe_mismatch |
| preserved_interaction_count | 4.0 | 0.0 | -4.0 | -100.0 | severe_mismatch |
| filler_dependency | unavailable | 0.0 | unavailable | unavailable | metric_unavailable |
| repair_dependency | unavailable | 0.0 | unavailable | unavailable | metric_unavailable |

## Promotion Source Audit

- `proposal_only`: `projected`; flag: `projected_output_not_promotion_evidence`. Comes from Phase 8L simulated variant estimates and is explicitly blocked from promotion use.
- `promote_blocked`: `executed`. Blocks promotion from real fixed-seed execution metrics.
- `keep_dry_run_only`: `executed`. Comes from real hybrid overlay execution versus generic baseline.
- `eligible_for_more_testing`: `executed`. Can only be returned from fixed-seed execution when score and safety metrics are clean.

## Executed Promotion Safety Gates

- Generic-fill gate: `{'current_experimental_vs_generic': {'status': 'measured', 'flag': 'generic_fill_pressure_increase', 'promotion_blocked': True, 'delta': {'status': 'measured', 'delta': 15.0, 'generic_value': 0.0, 'candidate_value': 15.0}, 'limit': 0.0, 'comparison': '15.0 > 0.0'}, 'hybrid_overlay_vs_generic': {'status': 'measured', 'flag': 'generic_fill_pressure_increase', 'promotion_blocked': True, 'delta': {'status': 'measured', 'delta': 16.0, 'generic_value': 0.0, 'candidate_value': 16.0}, 'limit': 0.0, 'comparison': '16.0 > 0.0'}}`
- Interaction-loss gate: `{'current_experimental_vs_generic': {'status': 'measured', 'flag': 'interaction_loss', 'promotion_blocked': True, 'lost_interaction_cards': ['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being'], 'interaction_loss_count': 4.0, 'delta': {'status': 'measured', 'delta': -4.0, 'generic_value': 4.0, 'candidate_value': 0.0}, 'limit': 0.0, 'comparison': '4.0 > 0.0'}, 'hybrid_overlay_vs_generic': {'status': 'measured', 'flag': 'interaction_loss', 'promotion_blocked': True, 'lost_interaction_cards': ['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being'], 'interaction_loss_count': 4.0, 'delta': {'status': 'measured', 'delta': -4.0, 'generic_value': 4.0, 'candidate_value': 0.0}, 'limit': 0.0, 'comparison': '4.0 > 0.0'}}`
- Promotion blocking reasons: `{'current_experimental_vs_generic': ['generic_fill_pressure_increase', 'interaction_loss'], 'hybrid_overlay_vs_generic': ['generic_fill_pressure_increase', 'interaction_loss']}`
- Lost interaction cards: `{'current_experimental_vs_generic': ['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being'], 'hybrid_overlay_vs_generic': ['Ash Blossom & Joyous Spring', 'D.D. Crow', 'Ghost Belle & Haunted Mansion', 'Nibiru, the Primal Being']}`

## Summary

- Severe mismatches: score, quota_balance, preserved_interaction_count
- Unavailable parity metrics: filler_dependency, repair_dependency
- Dead gates: None
- Active dependency gates: filler_dependency_gate, repair_dependency_gate
- Projected-only promotion paths: None

## Recommendation For Stabilization P

- Keep Phase 8L proposal-only, require executed-deck evidence for every promotion-like recommendation, and improve dependency measurement fidelity in the executed candidate reports.
