# Phase 6U: Repeated Filler Influence A/B Testing

Phase 6U adds a repeated A/B runner for the controlled filler-memory influence experiment from Phase 6T. It does not make filler influence default, expand the allowed filler list, change scoring weights, or alter authored Blue-Eyes behavior.

## Runner

Use:

```powershell
python filler_influence_ab_test.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5 --trials 5
```

Each trial runs the same archetypes and tuning count twice:

- control benchmark with filler-memory influence off
- experiment benchmark with filler-memory influence on

The experiment path still only allows activation-ready fillers:

- Ash Blossom & Joyous Spring
- Effect Veiler
- Ghost Belle & Haunted Mansion

Nibiru, the Primal Being and Infinite Impermanence remain blocked from filler-memory influence.

## No-Op Classification

A trial is classified as `no_effect` when filler-memory influence does not change ordering or selected filler choice, even if the experiment score is numerically higher. This prevents noisy benchmark variance from being mistaken for evidence that influence helped.

Classification rules:

- `no_effect`: no ordering/selection change, or selection-changing delta is within the neutral band
- `helped`: ordering or selection changed and experiment beats control beyond the neutral band
- `hurt`: ordering or selection changed and experiment trails control beyond the neutral band

## Reports

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/filler_influence_ab/
```

Latest files:

- `latest_filler_influence_ab_report.json`
- `latest_filler_influence_ab_report.md`

Reports include:

- control average improvement
- experiment average improvement
- experiment-minus-control delta
- repair success
- rejected deck counts
- filler choices
- ordering-change count
- selection-change count
- bias applied
- helped/hurt/no-effect classification

## Recommendation Criteria

Filler-memory influence should remain experimental unless repeated runs show actual ordering or selection changes with legal, non-regressed outcomes. A better experiment score alone is not enough if the influence path was a no-op.
