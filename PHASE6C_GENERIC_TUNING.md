# Phase 6C: Generic Deck Evaluation + Ratio Tuning

Phase 6C adds a tuning loop for generic archetype decks. It does not replace authored builders and does not change Blue-Eyes authored behavior.

## Generic Tuner

`deck/generic_tuner.py` implements:

```python
tune_generic_deck(archetype, card_pool, mode="meta", runs=20)
```

The tuner:

- generates multiple ratio profiles
- builds one generic deck per ratio profile
- scores each deck with `score_deck_breakdown()`
- records package counts and confidence
- selects the best legal deck
- updates generic ratio memory when the best result is legal

## Ratio Memory

`deck/generic_ratio_memory.py` stores memory at:

```text
SystemAIYugioh/data/deck_profiles/generic_ratio_memory.json
```

It tracks per archetype and mode:

- best package ratios
- average score by ratio profile
- best starter/extender/payoff/interruption balance
- bad ratio patterns
- confidence trends

Memory influence is intentionally small: the generic builder can use remembered ratios as a starting point, but legality and copy limits still dominate.

## Build Path

`build_deck(..., generic_tune_runs=0)` remains fast by default.

- `generic_tune_runs=0`: normal generic builder when needed
- `generic_tune_runs>0`: run the generic tuning loop when the generic fallback path is used

Authored Blue-Eyes package building remains first priority.

## CLI

`yugioh_ai_deckbuilder.py` now asks:

```text
Generic tune runs? [0]
```

Use `0` for normal generation. Use a small number like `5` or `10` for generic archetype tuning.

## Limitations

The tuner searches heuristic ratio profiles, not individual card replacements through a full optimizer. It does not perform self-play, neural learning, reinforcement learning, or exact duel simulation.

## Next Step

Phase 6D should add generic build report comparison across archetypes and optionally compare tuned generic builds against authored builds when authored systems exist.
