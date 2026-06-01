# Phase 6B: Generic Deck Construction Path

Phase 6B adds an optional generic deck builder for archetypes without authored package definitions. It does not replace the authored Blue-Eyes package builder.

## Builder Priority

`deck.builder.build_deck()` now uses this order:

1. Authored package builder when package definitions exist.
2. Generic builder when no authored package exists or the authored path cannot produce a valid deck.
3. Existing weighted random fallback as the last resort.

The most recent build report can be inspected with `deck.builder.get_last_build_report()`.

## Generic Builder

`deck/generic_deck_builder.py` consumes Phase 6A infrastructure:

- role inference
- generic package extraction
- combo skeleton inference
- compatibility hints

It builds:

- 40-card main deck
- up to 15-card Extra Deck
- side candidate hints
- package counts
- quota warnings
- generic confidence score

## Quotas

The generic builder uses flexible quotas:

- starters/searchers: 8-14
- extenders: 4-10
- payoffs: 2-6
- interruptions/non-engine: 6-12
- board breakers: 0-6
- bricks/garnets capped around 4-5

`meta` mode leans toward interruptions. `innovation` mode leans slightly more toward extenders and payoff exploration.

## Legality

The builder enforces:

- banlist/custom limits
- blocked card exclusion
- legal copy counts
- 40-card main deck target
- Extra Deck max 15

## Limitations

The generic deck builder is structural and heuristic. It can build legal exploratory decks for unsupported archetypes, but it does not yet prove exact combo legality or optimize ratios with archetype-specific matchup memory.

## Next Step

Phase 6C should add generic build evaluation loops that compare generic builds against authored builds when both exist, without changing authored builder priority.
