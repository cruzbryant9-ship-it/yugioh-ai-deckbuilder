# Stabilization T: Public Baseline Interaction Preservation Dry-Run

Dry-run candidate-fix testing only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_public_baseline_overlay_gate.py`
- `validate_stabilization_t.py`
- `STABILIZATION_T_PUBLIC_BASELINE_OVERLAY.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`
- `kashtira_public_baseline_overlay_gate.py`

## Public-Baseline Overlay Behavior

- Adds explicit variant `public_baseline_interaction_overlay`.
- The variant only runs when `--experimental-semi-specialized --specialization-profile Kashtira --experimental-variant public_baseline_interaction_overlay` is requested.
- The public generic baseline deck is used only to identify legal interaction cards for dry-run preservation.
- Current experimental and hybrid overlay behavior remain unchanged.

## Comparison Summary

- Generic average score: `187.83`
- Public overlay average score: `188.23`
- Public overlay delta vs generic: `0.4`
- Public overlay quota balance: `23.0`
- Public overlay generic-fill average: `12.0`
- Public overlay interaction selected average: `4.0`
- Recommendation: `keep_dry_run_only`

## Safety Gates

- Generic-fill gate: `{'status': 'measured', 'flag': 'generic_fill_pressure_increase', 'promotion_blocked': True, 'delta': {'status': 'measured', 'delta': 12.0, 'generic_value': 0.0, 'candidate_value': 12.0}, 'limit': 0.0, 'comparison': '12.0 > 0.0'}`
- Interaction-loss gate: `{'status': 'measured', 'flag': None, 'promotion_blocked': False, 'lost_interaction_cards': [], 'interaction_loss_count': 0.0, 'delta': {'status': 'measured', 'delta': 0.0, 'generic_value': 4.0, 'candidate_value': 4.0}, 'limit': 0.0, 'comparison': '0.0 > 0.0'}`
- Promotion-blocking reasons: `['generic_fill_pressure_increase']`
- Lost interaction cards: `[]`

## Validation Results

- Passed: True
- Duration seconds: 253.2036
- PASS: public-baseline variant is opt-in only
- PASS: default Kashtira remains generic
- PASS: current experimental path remains unchanged
- PASS: hybrid overlay path remains unchanged
- PASS: public baseline variant marks dry_run_variant true
- PASS: public baseline legal interaction cards are preserved
- PASS: no builder defaults changed
- PASS: public baseline overlay report generates
- PASS: Stabilization S validator still passes
- PASS: Stabilization R validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization U should investigate reducing public-overlay generic-fill pressure without changing defaults, using executed dry-run evidence only.
