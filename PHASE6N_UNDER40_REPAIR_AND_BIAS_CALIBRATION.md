# Phase 6N: Generic Under-40 Repair Completion + Advisory Bias Calibration

## Purpose

Phase 6N improves generic deck completion for archetypes that exhaust their archetype pool before reaching 40 cards. It is focused on repair, diagnostics, and reporting. It does not change scoring weights, authored Blue-Eyes behavior, or advisory influence strength.

## Under-40 Diagnostics

`deck/generic_repair_diagnostics.py` adds:

```python
diagnose_under_40_repair(...)
```

It reports:

- `under_40_reason`
- `missing_count`
- `available_fillers`
- `blocked_candidates`
- `copy_limit_blocked`
- `recommended_repair_strategy`

Reasons include exhausted legal copy counts, too many blocked cards, missing safe fillers, Extra Deck-only pools, spell/trap-heavy core exhaustion, and package quota conflicts.

## Safe Filler Fallback

`deck/generic_deck_repair.py` now uses a fallback ladder:

1. Fill missing starters/searchers.
2. Fill extenders.
3. Fill legal archetype core cards.
4. Fill legal interruptions/non-engine.
5. Fill legal board breakers.
6. Fill legal safe generic filler.
7. If still under 40, reject with diagnostics.

Safe filler is restricted to known generic cards such as hand traps, board breakers, consistency cards, and defensive spells/traps. It still respects banlist/custom limits, copy limits, and blocked cards.

## Spell/Trap-Heavy Archetypes

Repair now treats spell/trap-heavy cores more gracefully. It allows spell/trap archetype cards to count as valid core/search/recovery density and no longer assumes missing monsters are required for the deck to be complete.

## Advisory Bias Calibration

Advisory influence was not increased.

Reports now include:

- `advisory_budget_available`
- `advisory_budget_used`
- `diagnosis_bias_used`
- `diff_index_bias_used`
- `signals_suppressed`
- `signals_ignored_due_to_low_support`
- `signals_ignored_due_to_contested_history`
- `bias_changed_exploration_order`

## Benchmark Reporting

`generic_archetype_benchmark.py` now reports:

- under-40 diagnostics
- repair strategy counts
- decks completed by safe filler
- decks still rejected
- advisory bias calibration summary

## Validation

Run:

```bash
python validate_phase6n.py
```

It checks under-40 completion, blocked-card and copy-limit safety, Runick-style spell/trap-heavy repair, no overfill, diagnostics, advisory caps, kill switch behavior, Phase 6M compatibility, Stabilization G compatibility, and matchup matrix smoke.

## Limitations

Safe filler is intentionally conservative and hand-curated. The next step can improve filler ranking by archetype context, but this pass keeps the behavior simple and legality-first.
