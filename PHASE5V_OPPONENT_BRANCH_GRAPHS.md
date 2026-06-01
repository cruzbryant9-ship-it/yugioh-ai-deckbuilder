# Phase 5V: Opponent-Specific Branch Graphs

Phase 5V models curated opponent play as ordered action graphs. The Phase 5U branch/timing simulator remains as fallback, but curated opponents can now expose exact action nodes and response windows.

## Graph Schema

`deck/opponent_branch_graph.py` defines:

- `OpponentActionNode`
- `OpponentBranchGraph`

Nodes include the action card, action type, required/produced cards, movement hints, chain and response window flags, timing window, vulnerability list, protection, recovery route, resolved/interrupted routing, endboard additions, risk score, and payoff score.

## Ordered Simulation

`deck/opponent_graph_simulator.py` walks graph nodes in order and checks available interruptions against each response window. It records:

- best interruption node
- poor interruption node
- pivot route after interruption
- outcome if interrupted
- outcome if not interrupted
- graph stop rate
- graph pivot rate
- graph endboard reduction score
- graph timing precision score

## Curated Graphs

Compact graphs were added for:

- Snake-Eye
- Tenpai
- Labrynth
- Branded
- Kashtira
- Runick
- Floowandereeze
- Tearlaments

Snake-Eye has the most detailed graph, including Ash, Poplar, Original Sinful Spoils, Flamberge, Promethean Princess, and backup routes.

## Fallback Behavior

`simulate_choke_points()` uses an opponent branch graph when available. If no graph exists, it falls back to the Phase 5U branchable line timing model. Unknown broad matchups still return zero graph metrics.

## Adding New Graphs

Add a new `OpponentBranchGraph` to `OPPONENT_GRAPHS` with:

- starter nodes
- ordered `if_resolved_go_to` routes
- `if_interrupted_go_to` backup routes
- choke nodes
- terminal endboard nodes
- compact but meaningful vulnerability lists

## Limitations

- Graphs are still heuristic and compact.
- They estimate action order and response timing, not full hidden-information duel state.
- They do not yet consume exact resources or model opponent hand composition.
- More detailed graph nodes will improve timing and pivot accuracy.

## Next Phase

Phase 5W should add opponent graph resource validation: track opponent hand, field, GY, banish, deck, and Extra Deck as their graph resolves.
