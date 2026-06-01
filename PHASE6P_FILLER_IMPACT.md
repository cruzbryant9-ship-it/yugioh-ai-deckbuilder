# Phase 6P: Filler Impact Measurement

Phase 6P separates filler that only completes an under-40 deck from filler that appears to improve or hurt performance.

## What Was Added

- `deck/generic_filler_impact.py`
  - Compares a pre-filler or nearest baseline result against the final contextual-filler result.
  - Classifies filler cards as:
    - `completion_only`
    - `performance_positive`
    - `performance_neutral`
    - `performance_negative`
    - `risky`
- `deck/generic_filler_memory.py`
  - Saves advisory filler evidence to `SystemAIYugioh/data/deck_profiles/generic_filler_memory.json`.
  - Tracks usage counts, average score/confidence deltas, completion-only counts, positive/negative counts, and package-pressure relief.
- `deck/generic_tuner.py`
  - Records per-variant filler impact reports.
- `generic_archetype_benchmark.py`
  - Summarizes filler impact classifications and updates filler memory with provenance.

## How Impact Is Measured

When contextual filler is used, the tuner compares:

1. The pre-contextual-filler candidate, often under 40 cards.
2. The final repaired legal deck after contextual filler is applied.

The comparison records:

- score delta
- confidence delta
- whether completion was required
- package pressure relieved or worsened
- filler role contribution
- whether the deck would have remained under 40 without filler

This is observational, not a rejection rule.

## Memory Safety

Filler memory uses the shared memory/provenance system:

- Validator-generated records are isolated or skipped in production.
- Production updates use atomic JSON writes.
- Memory is advisory-only and does not influence selection yet.

## Current Limitations

- Filler impact is not causal proof; it compares nearest available candidates.
- Multiple filler cards in the same repair step share the same observed outcome.
- Legal decks are not rejected solely because filler impact is negative.
- Filler memory is not yet used as tuning bias.

## Validation

Run:

```powershell
python validate_phase6p.py
python validate_phase6o.py
python validate_phase6n.py
python validate_stabilization_g.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick --mode meta --runs 3 --show-replay
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```
