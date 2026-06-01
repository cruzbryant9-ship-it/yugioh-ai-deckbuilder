# Phase 5C Regression Gates

## What Phase 5C Adds

Phase 5C adds a protection layer around learned memory. Training runs still save their reports, but weak or suspicious batches no longer overwrite:

- `learned_card_stats.json`
- `learning_tuning.json`
- `learned_engine_stats.json`

## Package Quality Scoring

`deck/package_quality.py` exposes:

```python
score_package_quality(deck, package_metrics, score_breakdown)
```

It returns:

- `package_balance_score`
- `starter_quota_score`
- `brick_quota_score`
- `non_engine_score`
- `engine_coherence_score`
- `extra_deck_score`
- `quota_violation_penalty`
- `final_package_quality_score`

The score uses package counts, quota violations, playable hand rate, brick rate, combo line score, endboard score, resilience, and follow-up.

## Regression Gates

`SystemAIYugioh/regression_gates.py` exposes:

```python
evaluate_training_batch(summary, previous_profile)
```

The gate rejects learning updates when:

- average score drops too far below the previous learned average
- playable hand rate drops too much
- brick rate increases too much
- blocked-card violations exist
- package quota violations are too frequent
- package quality is too low

Reports are still saved even when learning is rejected.

## Thresholds

Thresholds live in `RegressionGateConfig`:

- `max_average_score_drop`
- `max_playable_rate_drop`
- `max_brick_rate_increase`
- `max_package_violation_rate`
- `min_package_quality_score`

They are conservative by default. Tighten them when the simulator becomes more reliable; loosen them when exploring experimental engines.

## Accept Or Reject Behavior

Accepted training:

- saves the run report
- updates card learning
- updates auto-tuning
- updates engine learning

Rejected training:

- saves the run report
- records rejection reasons in the report
- does not update learned card, tuning, or engine memory

## Why This Protects Long-Term Learning

Earlier phases could learn from noisy batches even when they had worse hands, worse brick rates, or broken package ratios. Phase 5C makes learning stateful and defensive: new data must be at least reasonably healthy before it can become future bias.

## Validation

Run:

```powershell
python validate_phase5.py
python validate_phase5b.py
python validate_phase5c.py
```

Then run the normal smoke commands:

```powershell
python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 2
python evaluate_learning.py --archetype "Blue-Eyes" --mode meta --runs 2
python compare_engines.py --archetype "Blue-Eyes" --mode meta --runs-per-engine 1
```

