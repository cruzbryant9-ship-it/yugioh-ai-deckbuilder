# Stabilization AA: Broader Candidate Validation

Broader validation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, current experimental behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_h_variant_broader_validation.py`
- `validate_stabilization_aa.py`
- `STABILIZATION_AA_BROADER_CANDIDATE_VALIDATION.md`

## Files Changed

- None; this phase adds broader validation/reporting files.

## Explicit Candidate

- Variant: `public_overlay_restore_overlap_reduce_preparations`
- Explicit-only dry-run path.
- No default behavior changed.

## Per-Seed Snapshot

| Seed | Runs | Generic Avg | H Avg | Delta | Positive | Negative | Neutral | Legality | Fallback | Interaction | Generic Fill |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12345 | 50 | 187.9346 | 191.1482 | 3.2136 | 50 | 0 | 0 | 1.0 | 0.0 | 4.0 | 0.0 |
| 23456 | 50 | 187.8638 | 191.1104 | 3.2466 | 50 | 0 | 0 | 1.0 | 0.0 | 4.0 | 0.0 |
| 34567 | 50 | 187.8306 | 191.2346 | 3.404 | 50 | 0 | 0 | 1.0 | 0.0 | 4.0 | 0.0 |

## Aggregate Snapshot

- Average delta across seeds: `3.2881`
- Worst seed delta: `3.2136`
- Best seed delta: `3.404`
- Total positive / negative / neutral: `150` / `0` / `0`
- Safety status: `{'clean': True, 'promotion_blockers': [], 'any_legality_issue': False, 'any_fallback': False, 'any_blocked_card_violation': False, 'any_interaction_drop': False, 'any_generic_fill_increase': False}`
- Recommendation: `eligible_for_candidate_review`
- Promotion applied: `False`

## Validation Results

- Passed: True
- Duration seconds: 543.3751
- PASS: broader runner works
- PASS: multiple seeds are used
- PASS: per-seed results are recorded
- PASS: aggregate results are recorded
- PASS: H variant remains explicit-only
- PASS: default Kashtira remains generic
- PASS: no builder defaults changed
- PASS: no promotion occurs
- PASS: Stabilization Z validator still passes
- PASS: Stabilization Y validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization AB should review the candidate evidence and, if still clean, test the explicit H candidate against additional modes or matchup-aware conditions while keeping it non-default.
