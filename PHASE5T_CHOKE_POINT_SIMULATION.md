# Phase 5T: Opponent-Specific Choke-Point Simulation

Phase 5T adds a lightweight opponent-line model so side planning can estimate which interruptions actually stop or weaken curated opponent starter lines.

## Opponent Line Model

Opponent lines live in `deck/opponent_choke_model.py`. Each line records:

- opponent archetype
- line name
- starter, extender, search, graveyard, and field-effect cards
- choke points
- cards or interruption types the line is weak to
- recovery cards
- expected endboard
- line score
- resilience score

The first modeled decks are Snake-Eye, Tenpai, Labrynth, Branded, Kashtira, Runick, Floowandereeze, and Tearlaments.

## Choke Simulation

`deck/choke_simulator.py` exposes:

```python
simulate_choke_points(opponent_profile, available_interruptions)
```

It compares available side/interruption cards against the opponent's modeled lines and estimates:

- whether a line is stopped, weakened, or still succeeds
- recovery likelihood
- best interruption choices
- poor interruption choices
- average stop rate
- average recovery rate
- choke coverage score

## Side Planning Integration

The side deck planner and side-plan optimizer now use choke simulation as an additional ranking signal. Cards that hit modeled starter-line choke points receive a small boost, while cards that do not interact with meaningful lines can receive a penalty.

This complements, but does not replace:

- curated profile counters
- post-side memory
- curated opponent memory
- banlist/custom limit checks
- side-plan legality validation

## New Metrics

Reports now include:

- `choke_stop_rate`
- `opponent_recovery_rate`
- `choke_coverage_score`
- `best_interruption_overlap`
- `poor_interruption_count`

These appear in opponent analysis, post-side evaluation, training/evaluation summaries, matrix reports, and curated opponent memory.

## Limitations

- This is still heuristic. It estimates disruption quality; it does not simulate a full opponent hand, chain, or duel state.
- Each curated deck currently has one broad line model. More lines per deck will improve accuracy.
- Recovery estimates are approximate and based on modeled recovery cards plus resilience score.
- Unknown inferred opponents gracefully fall back to zero choke metrics.

## Next Phase

Phase 5U should expand each curated opponent into multiple branchable lines and test exact interruption timing windows against those lines.
