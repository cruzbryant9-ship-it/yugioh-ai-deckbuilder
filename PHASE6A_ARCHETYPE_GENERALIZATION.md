# Phase 6A: Archetype Generalization Foundations

Phase 6A adds generalized archetype-learning infrastructure beside the authored Blue-Eyes systems. It does not replace combo graphs, package builder logic, side planning, regression gates, or stabilization/cache systems.

## Added Systems

### Role Inference

`deck/archetype_role_inference.py` classifies cards into structural roles:

- starter
- extender
- searcher
- payoff
- garnet/brick
- interruption
- board breaker
- recovery
- engine requirement

The inference uses card text, metadata, summon language, deck-search language, graveyard text, parsed costs/conditions, once-per-turn text, and Extra Deck/payoff signals.

### Generic Package Extraction

`deck/generic_package_extractor.py` builds inferred package definitions for arbitrary archetypes:

- core
- starters
- searchers
- extenders
- bricks
- engine
- traps
- non-engine candidates
- side-package candidates

These are advisory package outputs for future generalized deckbuilding. They do not override existing authored Blue-Eyes package construction.

### Archetype Relationship Graph

`deck/archetype_relationship_graph.py` scores compatibility between archetypes using:

- attribute overlap
- level overlap
- typing overlap
- graveyard synergy
- discard synergy
- search overlap
- summon compatibility
- Extra Deck compatibility
- engine collision risk

### Generic Combo Skeletons

`deck/generic_combo_skeleton.py` infers structural combo shapes:

`starter -> search -> extender -> payoff`

This is not a duel engine and does not validate exact card legality. It is a lightweight map of likely role progression.

## Current Limitations

The system is heuristic. It can identify broad structural roles, but it does not yet prove exact combo execution for arbitrary archetypes. It also does not infer precise archetype-specific restrictions unless those restrictions appear in recognizable text patterns.

## Next Step

Phase 6B should connect generic package outputs to an optional generalized builder mode while keeping authored archetype builders preferred when available.
