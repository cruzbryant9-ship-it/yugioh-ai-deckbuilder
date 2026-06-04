# Phase 8J: Kashtira Experimental Regression Gate

Deterministic regression testing only. The experimental builder was not promoted, semi-specialized building was not made default, and scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, full combo graphs, generic builder behavior, and legality enforcement were not changed.

## Files Created

- `kashtira_experimental_regression_gate.py`
- `validate_phase8j.py`
- `PHASE8J_KASHTIRA_EXPERIMENTAL_REGRESSION_GATE.md`

## Files Changed

- None

## Regression Gate Behavior

- Mode: `meta`
- Runs: 10
- Seed: 12345
- Frozen cards: True
- Live refresh used: False

## Fixed-Seed Results

- Generic average score: 187.888
- Experimental average score: 186.095
- Score delta: -1.793
- Generic quota balance: 24.0
- Experimental quota balance: 21.0
- Experimental fallback rate: 0.0
- Recommendation: `promote_blocked`
- Promotion blocked: True

## Validation Results

- Passed: True
- Duration seconds: 4692.3051
- PASS: regression gate runner works
- PASS: fixed seed mode is enforced
- PASS: frozen-card mode is enforced
- PASS: generic and experimental are compared
- PASS: score regression blocks promotion
- PASS: legality failure blocks promotion
- PASS: blocked-card failure blocks promotion
- PASS: fallback path is measured
- PASS: Blue-Eyes authored behavior remains untouched
- PASS: experimental path remains off by default
- PASS: Phase 8I validator still passes
- PASS: Phase 8H validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8K

- Improve the explicit experimental Kashtira adapter under the fixed-seed gate, focusing on score parity before any promotion discussion.
- Keep promotion blocked until the gate reports equal-or-better score, clean legality, zero fallback, and equal-or-better quota balance.
