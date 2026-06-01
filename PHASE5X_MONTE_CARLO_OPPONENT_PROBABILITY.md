# Phase 5X-lite: Monte Carlo Opponent Resource Probability

Phase 5X-lite adds a lightweight probability layer for opponent openings. It does not simulate full duels, turns, chain trees, or reinforcement learning. It samples opening hands from an opponent decklist and estimates whether the opponent is likely to see starters, extenders, interruptions, board breakers, backup access, graveyard access, and search access.

## What Monte Carlo Is Doing

`deck/opponent_probability_simulator.py` repeatedly samples five-card hands from the parsed opponent main deck. Each hand is classified against the opponent profile:

- starter access from known starters
- extender access from known extenders
- interruption access from known hand traps and interaction
- board breaker access from common going-second cards
- likely line access from starters or search cards
- backup line access from extenders or graveyard-enabled follow-up
- brick rate when no useful category appears
- graveyard and search access

The default run count is 1000. Validators use smaller runs so smoke tests stay quick.

## Graph Integration

Phase 5W resource validation remains the source of truth for whether an ordered opponent graph can legally resolve. Phase 5X-lite adds probability-weighted fields on top:

- `opponent_starter_open_rate`
- `opponent_extender_open_rate`
- `opponent_interruption_open_rate`
- `opponent_brick_rate`
- `probability_weighted_resource_valid_rate`
- `probability_weighted_stop_rate`
- `probability_weighted_pivot_rate`
- `probability_weighted_backup_rate`

Raw graph and resource metrics are preserved. The weighted metrics answer a different question: not only "can this line resolve?" but "how often is this line likely to be accessible from a real opener?"

## Why This Is Not Full Self-Play

This layer does not choose plays across a complete duel, model opponent sideboarding, track hidden information, or resolve all card text. It samples opening resource categories and weights existing graph/choke estimates. That keeps runtime small and avoids pretending the project has a full duel engine before it really does.

## How It Improves Matchup Analysis

Opponent analysis now reports both deterministic graph strength and opening likelihood. For example, a high `graph_stop_rate` matters more when `opponent_likely_line_access_rate` is also high. A scary backup route is less important if `opponent_backup_line_access_rate` is low.

This helps side planning distinguish:

- high-impact interruptions against common openers
- niche counters against rare lines
- matchup plans that overreact to possible but unlikely routes
- opponents whose backup line is probable enough to respect

## Limitations

- Card classification is heuristic and mostly name/profile based.
- It samples five-card hands only.
- It does not model draw phase, mulligans, sequencing, or player choice.
- It does not know every card's exact text unless earlier profile systems expose the card as a starter/extender/interruption.
- Curated profiles improve quality, but custom decklists may still need manual profile tuning.

## Next Step

After Phase 5X-lite, the recommended next step is Stabilization Pass A: reduce duplicated metric plumbing, freeze Phase 5 interfaces, clean report schemas, and make the validation suite faster and easier to run.
