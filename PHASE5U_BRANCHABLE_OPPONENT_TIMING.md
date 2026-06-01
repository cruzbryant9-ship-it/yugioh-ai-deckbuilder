# Phase 5U: Branchable Opponent Line Timing

Phase 5U expands opponent choke simulation from broad line matching into branchable, timing-aware interruption analysis.

## Branchable Opponent Lines

`deck/opponent_choke_model.py` now derives multiple branches from each curated opponent line:

- starter line
- extender line
- recovery line
- backup line
- high-roll line
- post-interruption line

Each branch includes required cards, optional cards, branch points, timing windows, recovery routes, uninterrupted/interrupted endboards, stop severity, recovery likelihood, and recommended interruptions.

## Timing Windows

`deck/timing_windows.py` defines reusable timing windows:

- on activation
- on summon
- on resolution
- in GY
- before search resolves
- after search resolves
- before special summon
- after material committed
- before endboard established

Each window records valid responses, missed-window risk, best response cards, and poor response cards.

## Timing-Aware Simulation

`simulate_choke_points()` now evaluates each available interruption against each branch timing window. Reports include:

- best timing windows
- bad timing windows
- line branch results
- timing precision score
- pivot risk score
- backup line success rate
- late/early interruption risk

Old Phase 5T fields are preserved for compatibility.

## Side Planning Impact

The side planner and optimizer still use curated counters and memory, but now add timing-aware reasons such as `timing_aware_choke`. This lets the AI prefer cards that hit high-impact windows rather than cards that only interact after the opponent has already pivoted.

## Limitations

- Branches are heuristic expansions, not full opponent hand simulation.
- Timing windows are approximate and card-family based.
- Broad matchup names without curated opponent profiles still fall back to zero timing/choke metrics.
- More exact accuracy will require opponent-specific graph lines for each curated deck.

## Next Phase

Phase 5V should add opponent-specific branch graphs, where each curated opponent line has ordered actions and exact timing windows per action.
