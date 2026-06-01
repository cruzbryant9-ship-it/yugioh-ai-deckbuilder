# Phase 5W: Opponent Graph Resource Validation

Phase 5W adds opponent-side resource tracking to ordered opponent branch graphs.

## Opponent Resource State

`deck/opponent_resource_state.py` tracks:

- hand
- field
- graveyard
- banished
- deck
- Extra Deck
- normal summon usage
- once-per-turn tags
- locks
- turn events

It is string-based for now, with light support for card dictionaries.

## Node Resource Requirements

`OpponentActionNode` now supports requirements and movements such as:

- `requires_in_hand`
- `requires_in_deck`
- `requires_on_field`
- `requires_in_gy`
- `requires_in_extra`
- `consumes_from_hand`
- `searches_from_deck`
- `summons_from_hand`
- `summons_from_deck`
- `summons_from_extra`
- `sends_to_gy`
- `banishes_from_gy`
- `once_per_turn_tag`
- `normal_summon_required`

## Resource-Aware Graph Simulation

`deck/opponent_graph_simulator.py` now initializes opponent resources, validates each node, applies movements, enforces normal summon and once-per-turn usage, and separates:

- interruption-stopped lines
- resource-failed lines
- pivot-route success
- backup-route success

## New Metrics

- `opponent_resource_valid_rate`
- `opponent_resource_failure_rate`
- `opponent_pivot_success_rate`
- `opponent_backup_success_rate`
- `opponent_missing_card_failures`
- `opponent_missing_extra_failures`
- `opponent_once_per_turn_failures`
- `opponent_normal_summon_failures`

## Limitations

- Resource tracking is conservative and string-based.
- It does not yet infer probability of opening the required cards.
- It does not model full opponent material math or hidden information.
- Some compact curated graphs use approximate resource effects.

## Next Phase

Phase 5X should add opponent hand-probability sampling, so graph resource validity reflects how often an opponent actually opens each route.
