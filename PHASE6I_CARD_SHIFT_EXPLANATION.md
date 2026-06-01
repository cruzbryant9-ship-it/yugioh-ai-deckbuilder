# Phase 6I: Card-Level Package Shift Explanation

Phase 6I explains accepted and rejected generic ratio changes at the card level. It does not replace authored builders, change scoring weights, or add duel simulation.

## What Was Added

- `deck/generic_card_shift_explainer.py`
  - Compares a baseline deck against a candidate deck.
  - Reports added/removed cards, copy increases/decreases, role deltas, package deltas, risk flags, and a readable explanation.
- `deck/generic_targeted_retest.py`
  - Attaches a `card_shift_explanation` to every targeted retest candidate.
  - Explains why accepted candidates passed or why rejected candidates failed.
- `generic_archetype_benchmark.py`
  - Adds card-shift summaries to JSON and markdown benchmark reports.
  - Reports helpful/harmful additions and removals plus package movement summaries.
- `deck/generic_ratio_memory.py`
  - Tracks helpful and harmful card movement counts from targeted retests.

## Explanation Fields

`explain_card_shifts()` returns:

- `cards_added`
- `cards_removed`
- `copy_increases`
- `copy_decreases`
- `role_delta`
- `package_delta`
- `explanation`
- `risk_flags`

Risk flags include starter loss, extender loss, interruption loss, brick pressure increases, payoff overfill risk, board breaker overfill risk, and package instability.

## How It Is Used

Targeted retesting now compares:

```text
baseline generic deck -> recommended ratio candidate deck
```

If a recommendation is rejected, the report can explain whether the candidate removed too many starters, added bricks, lost interruptions, or moved too many cards at once.

## Validation

Run:

```powershell
python validate_phase6i.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira --mode meta --runs 3
```

The latest benchmark markdown report includes:

- `Card Shift Summary`
- `Accepted Card Shifts`
- `Rejected Card Shifts`

## Limitations

The explanation is role-based and package-based. It does not prove exact gameplay causality; it identifies likely card movement reasons behind score changes.

## Recommended Next Step

Phase 6J should add package-shift replay reports that show before/after deck sections side by side for human review.
