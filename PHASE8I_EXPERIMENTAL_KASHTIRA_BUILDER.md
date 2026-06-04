# Phase 8I: Experimental Kashtira Builder Flag

Explicit opt-in only. Semi-specialized building was not made default, Blue-Eyes authored behavior was not changed, other archetypes remain unsupported, and scoring, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, duel engine features, and full combo graphs were not changed.

## Files Created

- `deck/semi_specialized_builder_adapter.py`
- `semi_specialized_experimental_comparison.py`
- `validate_phase8i.py`
- `PHASE8I_EXPERIMENTAL_KASHTIRA_BUILDER.md`

## Files Changed

- `deck/builder.py`
- `yugioh_ai_deckbuilder.py`
- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Experimental Flag Behavior

- Default Kashtira CLI/build path remains generic.
- Experimental path requires `--experimental-semi-specialized --specialization-profile Kashtira`.
- Unsupported archetypes or failed gates fall back to generic.
- Active profile still has Riseheart as active payoff: True

## Generic vs Experimental Comparison

- Generic average score: 187.68
- Experimental average score: 185.162
- Generic builders used: generic
- Experimental builders used: semi_specialized_experimental
- Experimental fallback rate: 0.0
- Regression recommendation: `do_not_promote_score_regression`

## Validation Results

- Passed: True
- Duration seconds: 2353.268
- PASS: default Kashtira path remains generic
- PASS: explicit flag can call experimental adapter
- PASS: Blue-Eyes authored path remains unchanged
- PASS: unsupported archetype cannot use experimental path
- PASS: failed gates fallback to generic
- PASS: blocked cards are rejected
- PASS: output marks experimental/not_default
- PASS: comparison report generates
- PASS: Phase 8H validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8J

- Add experimental regression gates comparing generic and explicit Kashtira experimental outputs across fixed seeds and frozen card pools.
- Keep the experimental flag opt-in until repeated reports show no score, legality, fallback, or package-balance regressions.
