# Phase 5J: Effect Resolution Branches + Game-History Flags

Phase 5J adds lightweight turn history and branch selection to the combo graph validator.

## Game History

`ResourceState` now tracks:

- `summoned_this_turn`
- `special_summoned_this_turn`
- `sent_to_gy_this_turn`
- `activated_cards_this_turn`
- `resolved_effects_this_turn`
- `searched_this_turn`
- `used_effect_tags`
- `turn_events`

The validator records events as cards move, summon, search, activate, resolve effects, and complete graph nodes.

## History Conditions

`deck/card_conditions.py` can now check:

- `was_summoned_this_turn`
- `was_special_summoned_this_turn`
- `was_sent_to_gy_this_turn`
- `effect_resolved_this_turn`
- `card_activated_this_turn`
- `previous_node_completed`
- `previous_card_moved`

New failure reasons:

- `history_condition_unmet`
- `summon_history_missing`
- `gy_history_missing`
- `activation_history_missing`
- `resolution_history_missing`

## Effect Branches

`LineNode` now supports `branches`.

Each branch can define:

```python
{
    "name": "search starter",
    "conditions": [],
    "costs": [],
    "effects": [],
    "score": 5,
}
```

The validator:

1. Filters branches by conditions, costs, and effect target availability.
2. Chooses the highest-scoring valid branch.
3. Applies branch costs and effects.
4. Records the chosen branch and branch events.
5. Fails with a branch-related reason if no branch is valid.

## Blue-Eyes Branches Added

- `Bingo Machine` can choose starter, payoff, or follow-up search targets.
- `Wishes for Eyes` can choose starter or Blue-Eyes access.
- `Abyss Dragon` can choose ritual or fusion follow-up.
- `True Light` can choose summon or support approximation.
- `Dictator of D.` records the Blue-Eyes send-to-GY setup and uses that history.

## Metrics Added

- `branch_valid_rate`
- `no_valid_branch_rate`
- `average_branch_score`
- `history_condition_failure_rate`
- `summon_history_failure_rate`
- `gy_history_failure_rate`
- `activation_history_failure_rate`
- `resolution_history_failure_rate`

Regression gates can reject learning if branch validity falls or history failures spike.

## Limitations

This is still a compact model, not a full chain simulator.

- Branch effects are simple resource and event operations.
- The branch scorer is static for now.
- History is per simulated hand and does not model opponent interaction windows.
- It does not yet model mandatory vs optional triggers, missed timing, or chain links.

## Next Phase

Phase 5K should add trigger windows and chain interaction modeling: activation windows, response windows, negation/resolution outcomes, and interruption-aware line resilience.
