# Phase 6E: Generic Legality Repair + Ratio Fallback Recovery

Phase 6E adds a repair layer for generic decks. It does not replace authored builders and does not change Blue-Eyes authored behavior.

## Repair Module

`deck/generic_deck_repair.py` implements:

```python
repair_generic_deck(main_deck, extra_deck, archetype, card_pool, package_data, quota_profile, mode="meta")
```

The repair pass checks:

- main deck below or above 40 cards
- Extra Deck above 15 cards
- blocked cards
- copy-limit violations
- missing starter/searcher minimums
- missing extender minimums
- payoff overfill
- brick/garnet overfill

## Repair Priority

When filling missing main-deck slots, repair prefers:

1. legal starters/searchers
2. legal extenders
3. legal interruptions/non-engine cards
4. legal recovery cards
5. legal board breakers
6. low-risk archetype cards

It avoids blocked cards, over-copy-limit cards, and high brick/garnet cards when possible.

## Tuner Recovery

`deck/generic_tuner.py` now uses repaired builder outputs. If a ratio still produces an illegal or incomplete deck, the tuner tries a safer fallback ratio. Failed ratios are recorded as bad ratio patterns when memory updates are enabled.

## Benchmark Metrics

`generic_archetype_benchmark.py` now reports:

- repair success rate
- average repair actions
- decks saved by repair
- decks still rejected
- common repair warnings

Ratio memory still only updates when the tuned/repaired deck is legal, blocked-card checks pass, and the score improvement is safe.

## Limitations

Repair is conservative. It can recover many 38-39 card generic builds, but it does not invent missing archetype support or perform full card-by-card optimization.
