# Phase 5I: Card-Text-Aware Costs and Conditions

Phase 5I adds a small, heuristic card text layer to the combo graph validator. The goal is not to parse every Yu-Gi-Oh card perfectly. The goal is to catch common gameplay requirements that matter for Blue-Eyes-style combo validation.

## Parser Patterns

`deck/card_text_parser.py` extracts simple structured hints from card text:

- reveal costs
- discard costs
- send-to-GY costs
- banish costs
- control conditions
- GY conditions
- deck search effects
- special summon effects
- once-per-turn flags and tags
- simple activation restrictions

The parser returns:

```python
{
    "costs": [],
    "conditions": [],
    "effects": [],
    "once_per_turn": False,
    "once_per_turn_tag": None,
    "activation_restrictions": [],
}
```

## Cost And Condition System

`deck/card_conditions.py` checks and applies costs against `ResourceState`.

Supported costs:

- reveal a card in hand
- discard a card from hand
- send a card from hand, field, or deck to GY
- banish a card from GY or another source

Supported conditions:

- control a matching card
- control a matching archetype or monster
- card exists in GY
- card exists on field
- card exists in hand
- target exists in deck
- target exists in GY

## Graph Integration

`LineNode` now supports:

- `costs`
- `conditions`
- `parsed_card_text_source`

Before a node resolves, the validator checks conditions, applies costs, and only then continues with movement, summon, search, and material validation.

New failure reasons include:

- `cost_reveal_unavailable`
- `cost_discard_unavailable`
- `cost_send_unavailable`
- `cost_banish_unavailable`
- `condition_control_unmet`
- `condition_gy_unmet`
- `condition_target_unavailable`
- `activation_restriction_failed`

## Blue-Eyes Modeling Added

- `Blue-Eyes Alternative White Dragon` now requires revealing `Blue-Eyes White Dragon`.
- `Dictator of D.` models sending `Blue-Eyes White Dragon` from deck to GY.
- `True Light + Jet Dragon` approximates needing control of `True Light`.
- `Abyss Dragon` follow-up approximates needing Blue-Eyes presence.

## Metrics Added

- `cost_condition_valid_rate`
- `cost_failure_rate_normalized`
- `condition_failure_rate_normalized`
- `reveal_cost_failure_rate`
- `discard_cost_failure_rate`
- `gy_condition_failure_rate`
- `control_condition_failure_rate`

Regression gates can reject learning when these metrics regress too much.

## Limitations

- The parser is pattern-based, not a full PSCT parser.
- It does not understand every replacement cost or optional branch.
- It does not yet distinguish activation cost from effect resolution with full chain timing.
- It approximates some Blue-Eyes conditions instead of modeling full game history.

## Adding New Card-Specific Costs

Prefer explicit graph fields when the card is strategically important:

```python
LineNode(
    "Reveal Blue-Eyes",
    "special_summon",
    costs=({"type": "reveal", "requirement": {"name": "Blue-Eyes White Dragon"}},),
)
```

Use `parsed_card_text_source` for lower-risk heuristic parsing when exact modeling is not needed yet.

## Next Phase

Phase 5J should add effect resolution branches and game-history flags, such as “was summoned this turn,” “was sent to GY this turn,” and “card/effect activated successfully.”
