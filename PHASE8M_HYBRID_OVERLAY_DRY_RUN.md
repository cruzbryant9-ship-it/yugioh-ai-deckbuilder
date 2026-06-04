# Phase 8M: Hybrid Overlay Dry-Run Adapter Branch

Explicit dry-run branch only. No default behavior, current experimental behavior, generic builder behavior, scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, or full combo graphs were changed.

## Files Created

- `kashtira_hybrid_overlay_regression_gate.py`
- `validate_phase8m.py`
- `PHASE8M_HYBRID_OVERLAY_DRY_RUN.md`

## Files Changed

- `deck/semi_specialized_builder_adapter.py`
- `deck/builder.py`
- `yugioh_ai_deckbuilder.py`

## Dry-Run Branch Behavior

- Normal Kashtira remains generic.
- Current explicit experimental Kashtira remains available without a variant.
- Hybrid overlay requires `--experimental-variant hybrid_generic_interaction_overlay`.

## Comparison

- Generic average score: 187.888
- Current experimental average score: 185.636
- Hybrid average score: 185.265
- Hybrid delta vs generic: -2.623
- Hybrid delta vs current experimental: -0.371
- Recommendation: `keep_dry_run_only`

## Validation Results

- Passed: True
- Duration seconds: 5705.2969
- PASS: normal Kashtira remains generic
- PASS: default experimental Kashtira remains unchanged
- PASS: hybrid variant only runs with explicit variant flag
- PASS: output marks dry_run_variant true
- PASS: Blue-Eyes authored behavior remains untouched
- PASS: unsupported variants fallback or fail safely
- PASS: legality remains clean
- PASS: hybrid report generates
- PASS: Phase 8L validator still passes
- PASS: Phase 8J validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8N

- Run a larger fixed-seed sample for the hybrid dry-run branch and inspect whether its score edge remains stable before touching the active experimental adapter.
