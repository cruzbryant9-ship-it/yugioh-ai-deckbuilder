# Phase 5E Line Requirement Graphs

## What Phase 5E Adds

Phase 5E adds graph-based combo validation. Earlier phases detected named lines from hand contents. Graph validation checks whether a hand can progress through ordered requirements from opener to payoff.

## Graph Node Schema

Graph nodes live in `deck/line_graph.py` as `LineNode` objects:

- `name`
- `action_type`
- `requires_cards`
- `requires_zones`
- `produces_cards`
- `moves_cards`
- `consumes_cards`
- `once_per_turn_tag`
- `normal_summon_required`
- `locks_applied`
- `interruption_points`
- `payoff_score`

Supported action types include opener, search, summon, send_to_gy, special_summon, ritual_summon, fusion_summon, synchro_summon, set_trap, endboard, and follow_up.

## How Validation Works

`deck/line_validator.py` walks a graph node by node. It tracks available cards, produced cards, consumed cards, normal summon usage, once-per-turn tags, zones, locks, interruption points, payoff score, resource score, and risk score.

Validation returns:

- `valid`
- `line_name`
- `completed_nodes`
- `failed_node`
- `failure_reason`
- `endboard`
- `follow_up`
- `interruption_points`
- `payoff_score`
- `resource_score`
- `risk_score`
- `final_line_score`

## Graph Lines Added

Blue-Eyes graph lines cover:

- Sage + White Stone -> Spirit Dragon
- Dictator setup -> Blue-Eyes access
- Bingo Machine -> search line
- Wishes for Eyes -> access line
- True Light + Jet loop
- Chaos Form -> Chaos MAX
- Ultimate Fusion -> fusion pressure
- Abyss Dragon follow-up
- Alternative White Dragon pressure

## How Graph Scoring Differs

The old heuristic system asks: "Does this hand contain cards that look like a line?"

The graph system asks: "Can this hand satisfy each step, produce needed cards, avoid illegal repeated normal summons or once-per-turn tags, and reach payoff?"

Graph metrics added to scoring:

- `graph_valid_line_rate`
- `graph_average_line_score`
- `graph_average_payoff_score`
- `graph_average_resource_score`
- `graph_average_risk_score`
- `graph_failed_line_rate`
- `most_common_graph_failure_reason`

## Current Limitations

This is still not a full rules engine. Zones are simplified, material validation is approximate, deck-search availability is optimistic, and card text is not parsed into exact effects. It is a structured validator, not a duel simulator.

## Next Phase Recommendation

Phase 5F should add resource zones and material accounting: hand, field, graveyard, banish, deck, Extra Deck, normal summon availability, and exact material requirements for Ritual/Fusion/Synchro/Link lines.

