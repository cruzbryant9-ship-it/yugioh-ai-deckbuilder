# Phase 8E: Kashtira Quota Movement Sensitivity Replay

Replay/testing only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.

## Files Created

- `semi_specialization_sensitivity_report.py`
- `validate_phase8e.py`
- `PHASE8E_KASHTIRA_QUOTA_SENSITIVITY.md`

## Files Changed

- `deck/semi_specialized_quota_replay.py`

## Sensitivity Results

- Stability classification: `stable`
- Generic total gap: 36.0
- Not activated: True

## Gap By Movement Strength

- `0.0`: total gap 36.0, delta vs baseline 0.0, worsened roles none
- `0.5`: total gap 22.5, delta vs baseline 13.5, worsened roles none
- `0.75`: total gap 15.75, delta vs baseline 20.25, worsened roles none
- `1.0`: total gap 9.0, delta vs baseline 27.0, worsened roles none

## Worsened Roles

- None

## Risk Flags

- banlist changes can sharply affect starter density
- do not infer full combo graph until package ratios stabilize under pilot review
- filler dependency is slightly above Phase 8B readiness gate

## Validation Results

- Passed: True
- Duration seconds: 456.4587
- PASS: sensitivity replay runs
- PASS: all movement strengths are present
- PASS: 0% equals generic baseline
- PASS: 100% matches Phase 8D proposed replay behavior
- PASS: not_activated remains true
- PASS: no semi-specialized builder is activated
- PASS: Phase 8D validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8F

- Add a non-activated role-classification audit for Kashtira payoff, interruption, board-breaker, and Extra Deck payoff tags.
- Compare sensitivity using fixed card pools so quota movement can be separated from card database drift.
- Keep any future semi-specialized builder behind an explicit experimental flag and generic-vs-experimental regression gates.
