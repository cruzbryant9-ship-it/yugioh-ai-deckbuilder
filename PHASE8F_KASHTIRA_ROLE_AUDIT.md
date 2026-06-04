# Phase 8F: Kashtira Role Classification Audit

Audit/report-only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.

## Files Created

- `deck/semi_specialized_role_audit.py`
- `semi_specialization_role_audit_report.py`
- `validate_phase8f.py`
- `PHASE8F_KASHTIRA_ROLE_AUDIT.md`

## Files Changed

- `deck/semi_specialized_quota_replay.py`
- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Audit Summary

- Role agreement score: 0.8214
- Readiness classification: `role_unstable`
- Not activated: True

## Confirmed Roles

- `starters_searchers`: Kashtira Fenrir, Kashtira Unicorn, Kashtiratheosis, Pressured Planet Wraitsoth
- `extenders`: Kashtira Big Bang, Kashtira Birth, Kashtira Riseheart, Scareclaw Kashtira, Tearlaments Kashtira
- `payoffs`: Kashtira Arise-Heart, Kashtira Shangri-Ira
- `interruptions`: Kashtira Arise-Heart, Kashtira Big Bang, Kashtira Fenrir, Kashtira Preparations
- `board_breakers`: Book of Eclipse, Dark Ruler No More, Evenly Matched, Lightning Storm
- `extra_deck_payoffs`: Divine Arsenal AA-ZEUS - Sky Thunder, Kashtira Arise-Heart, Kashtira Shangri-Ira, Number 11: Big Eye

## Conflicts

- `Kashtira Big Bang` as `bricks_garnets` [minor]: profile role lacks supporting generic/text/package signal
- `Kashtira Big Bang` as `bricks_garnets` [minor]: brick/garnet tag conflicts with high benchmark usage
- `Kashtira Ogre` as `bricks_garnets` [minor]: profile role lacks supporting generic/text/package signal
- `Kashtira Ogre` as `bricks_garnets` [minor]: brick/garnet tag conflicts with high benchmark usage
- `Kashtira Overlap` as `bricks_garnets` [minor]: profile role lacks supporting generic/text/package signal
- `Kashtira Overlap` as `bricks_garnets` [minor]: brick/garnet tag conflicts with high benchmark usage
- `Kashtira Preparations` as `bricks_garnets` [minor]: profile role lacks supporting generic/text/package signal
- `Kashtira Preparations` as `bricks_garnets` [minor]: brick/garnet tag conflicts with high benchmark usage
- `Kashtira Riseheart` as `payoffs` [major]: profile role lacks supporting generic/text/package signal
- `Kashtira Riseheart` as `payoffs` [major]: profile payoff but generic inference sees extender

## Low-Confidence Assignments

- `Book of Eclipse` as `board_breakers`: generic role confidence below audit threshold

## Risk Flags

- banlist changes can sharply affect starter density
- do not infer full combo graph until package ratios stabilize under pilot review
- filler dependency is slightly above Phase 8B readiness gate
- major role conflicts block experimental builder flag
- quota pressure still present: total gap 36.0
- role audit found 1 low-confidence assignments
- role audit found 10 role conflicts

## Validation Results

- Passed: True
- Duration seconds: 595.9955
- PASS: role audit runs
- PASS: report runner generates JSON/Markdown
- PASS: not_activated remains true
- PASS: conflicts are detected in synthetic cases
- PASS: Kashtira profile receives a classification
- PASS: Phase 8E validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8G

- Add a non-activated experimental flag design that can compare generic Kashtira builds against audited quota and role assumptions without changing defaults.
- Require role-audit readiness, quota-sensitivity stability, and generic-vs-experimental regression reports before any default activation.
