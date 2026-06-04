# Phase 8B: Archetype Specialization Candidate Detection

Detection/reporting only. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression thresholds, neural networks, reinforcement learning, self-play, or duel-engine features were changed.

## Files Created

- `deck/archetype_specialization_detector.py`
- `archetype_specialization_report.py`
- `validate_phase8b.py`
- `PHASE8B_ARCHETYPE_SPECIALIZATION_CANDIDATES.md`

## Files Changed

- `SystemAIYugioh/fingerprint_coverage_audit.py`

## Readiness Gates

- minimum benchmark runs
- average tuned improvement
- repair success rate
- rejected deck rate
- quota warning rate
- generic confidence score
- role inference confidence
- package stability
- ratio memory stability
- benchmark trend not declining
- blocked-card clean
- low repair dependency
- filler dependency not excessive

## Candidate Results

- Ready: None
- Watchlist: Branded, Kashtira, Runick
- Not ready: Tearlaments

## Evidence Summary

- `Branded`: watchlist score 95.17; runs=200, improvement=0.0999, repair=1.0, failed=average_tuned_improvement, ratio_memory_stability
- `Kashtira`: watchlist score 99.66; runs=200, improvement=0.5367, repair=1.0, failed=filler_dependency_not_excessive
- `Runick`: watchlist score 78.27; runs=29, improvement=1.7224, repair=0.8621, failed=repair_success_rate, rejected_deck_rate, quota_warning_rate, low_repair_dependency
- `Tearlaments`: not_ready score 97.31; runs=16, improvement=0.3006, repair=1.0, failed=minimum_benchmark_runs, ratio_memory_stability, filler_dependency_not_excessive

## Validation Results

- Passed: True
- Duration seconds: 125.7742
- PASS: detector runs
- PASS: report runner works
- PASS: readiness score is produced
- PASS: watchlist or ready supported by evidence
- PASS: insufficient evidence produces not_ready
- PASS: blocked-card contamination fails candidate status
- PASS: high repair dependency prevents ready status
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Phase 8C

- Manually review watchlist/ready archetypes and choose one semi-specialization pilot.
- Draft archetype-specific package constraints and role maps only; still avoid authored combo graphs until evidence is reviewed.
- Add a pre-promotion regression report comparing generic vs semi-specialized behavior before any activation.
