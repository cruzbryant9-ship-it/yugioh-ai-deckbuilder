# Phase 8D: Kashtira Quota Replay Harness

Replay/testing only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.

## Files Created

- `deck/semi_specialized_quota_replay.py`
- `semi_specialization_quota_replay_report.py`
- `validate_phase8d.py`
- `PHASE8D_KASHTIRA_QUOTA_REPLAY.md`

## Files Changed

- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Quota Replay Behavior

- Builds normal generic Kashtira decks.
- Compares observed role/package counts against Phase 8C quota targets.
- Projects report-only quota adjustments toward the target balance.
- Does not alter final deck scores or deck construction.
- Not activated: True

## Before/After Quota Balance

- Generic total gap: 36.0
- Proposed total gap: 9.0
- Gap delta: 27.0
- `starters_searchers`: generic gap 9.0 -> projected gap 2.25
- `extenders`: generic gap 9.0 -> projected gap 2.25
- `payoffs`: generic gap -4.0 -> projected gap -1.0
- `interruptions`: generic gap -6.0 -> projected gap -1.5
- `board_breakers`: generic gap -3.0 -> projected gap -0.75
- `extra_deck_payoffs`: generic gap -5.0 -> projected gap -1.25

## Improved Roles

- `starters_searchers`
- `extenders`
- `payoffs`
- `interruptions`
- `board_breakers`
- `extra_deck_payoffs`

## Worsened Roles

- None

## Risk Flags

- banlist changes can sharply affect starter density
- do not infer full combo graph until package ratios stabilize under pilot review
- filler dependency is slightly above Phase 8B readiness gate

## Validation Results

- Passed: True
- Duration seconds: 323.2082
- PASS: replay module runs
- PASS: report runner generates JSON/Markdown
- PASS: replay output marks not_activated true
- PASS: generic builder still works
- PASS: Blue-Eyes authored behavior remains untouched
- PASS: Phase 8C validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8E

- Add a non-activating quota replay comparison against alternate target strengths, such as 50%, 75%, and 100% target movement.
- Inspect whether payoff/interruption under-target gaps come from role classification before adding any builder flag.
- Keep any future semi-specialized builder behind an explicit experimental flag plus generic-vs-experimental regression gates.
