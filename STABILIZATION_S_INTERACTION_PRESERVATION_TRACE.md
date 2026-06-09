# Stabilization S: Interaction Preservation Failure Trace

Trace/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `deck/interaction_preservation_trace.py`
- `kashtira_interaction_preservation_trace.py`
- `validate_stabilization_s.py`
- `STABILIZATION_S_INTERACTION_PRESERVATION_TRACE.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`
- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Trace Results

- `Ash Blossom & Joyous Spring`
  - Available/legal: `True` / `True`
  - Generic/experimental/hybrid counts: `2` / `0` / `0`
  - Classification: `not_in_profile_roles, preservation_stage_noop`
  - Rejection stage: `interaction_preservation_stage`
  - Rejection reason: `Ash Blossom & Joyous Spring: absent from generic baseline main deck`
- `Ghost Belle & Haunted Mansion`
  - Available/legal: `True` / `True`
  - Generic/experimental/hybrid counts: `2` / `0` / `0`
  - Classification: `not_in_profile_roles, preservation_stage_noop`
  - Rejection stage: `interaction_preservation_stage`
  - Rejection reason: `Ghost Belle & Haunted Mansion: absent from generic baseline main deck`
- `D.D. Crow`
  - Available/legal: `True` / `True`
  - Generic/experimental/hybrid counts: `2` / `0` / `0`
  - Classification: `not_in_profile_roles, preservation_stage_noop`
  - Rejection stage: `interaction_preservation_stage`
  - Rejection reason: `D.D. Crow: absent from generic baseline main deck`
- `Nibiru, the Primal Being`
  - Available/legal: `True` / `True`
  - Generic/experimental/hybrid counts: `2` / `0` / `0`
  - Classification: `not_in_profile_roles, preservation_stage_noop`
  - Rejection stage: `interaction_preservation_stage`
  - Rejection reason: `Nibiru, the Primal Being: absent from generic baseline main deck`

## Failure Classification

- Interaction cards are available in the card pool and legal.
- The normal generic build contains the registry interaction cards.
- The current experimental path does not select them in profile quota roles.
- The hybrid path attempts preservation, but its internal generic baseline contains zero copies, so preservation is a no-op.
- The cards are skipped, not unavailable, illegal, displaced after selection, or truncated after final selection.

## Validation Results

- Passed: True
- Duration seconds: 438.5878
- PASS: trace module runs
- PASS: adapter emits trace metadata
- PASS: trace runner generates JSON/Markdown
- PASS: each registry interaction card has a trace
- PASS: failure classification is present
- PASS: no selection behavior changed
- PASS: Stabilization R validator still passes
- PASS: Stabilization Q validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization T should design a report-only candidate fix that compares using the public generic baseline interaction set, then test it behind an explicit non-default dry-run path before any adapter behavior changes.
