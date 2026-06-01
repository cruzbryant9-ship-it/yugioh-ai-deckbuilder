# Phase 5F Resource State

## What Phase 5F Adds

Phase 5F adds explicit resource tracking for combo graph validation. Instead of only checking that a card name appears somewhere, graph validation now tracks simplified zones:

- hand
- field
- graveyard
- banished
- deck
- Extra Deck

## ResourceState

`deck/resource_state.py` defines `ResourceState`, a string-based zone tracker with helpers for:

- checking card availability
- moving cards between zones
- searching the deck
- sending cards to the graveyard
- summoning from hand, deck, or Extra Deck
- enforcing one normal summon
- enforcing once-per-turn tags
- applying locks

## Graph Validation With Resources

`deck/line_validator.py` now initializes a `ResourceState` from the sampled hand, full deck, and Extra Deck. Each graph node can check or perform resource actions:

- `search_card`
- `summon_card`
- `extra_deck_card`
- `required_materials`
- `consumes_materials`
- `cost_cards`
- `sends_to_gy`
- `requires_in_deck`
- `requires_in_extra`
- `produces_to_field`
- `produces_to_gy`

Failure reasons are more specific:

- `missing_required_card`
- `missing_material`
- `missing_search_target`
- `missing_extra_deck_card`
- `normal_summon_used`
- `once_per_turn_conflict`
- `cost_unavailable`
- `lock_conflict`
- `payoff_unreachable`

## New Metrics

`real_combo_report()` now includes:

- `resource_valid_line_rate`
- `missing_material_rate`
- `missing_search_target_rate`
- `missing_extra_deck_rate`
- `cost_failure_rate`
- `normal_summon_failure_rate`
- `once_per_turn_failure_rate`

`score_deck_breakdown()` adds:

- `resource_valid_line_rate`
- `material_failure_rate`
- `search_failure_rate`
- `extra_deck_failure_rate`
- `cost_failure_rate`

## Known Simplifications

This is still string-based and intentionally conservative. It does not yet model exact levels, tuners, attributes, chain timing, replacement materials, summon locks in full detail, or real card text parsing.

## Adding New Movement Nodes

Add fields to a `LineNode` in `deck/line_graph.py`. Prefer explicit fields such as `search_card`, `required_materials`, `extra_deck_card`, and `cost_cards` over vague `produces_cards` when the line needs resource validation.

## Next Phase

Phase 5G should add material typing and summon requirements: tuner/non-tuner, levels, Ritual levels, Fusion named materials, Link ratings, and archetype/material substitutions.

