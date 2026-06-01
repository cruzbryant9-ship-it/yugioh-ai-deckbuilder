# Phase 5S: Curated Opponent Performance Memory

Phase 5S adds persistent memory for named curated opponent decks. Broad matchup memory still exists, but the AI can now remember which engines, side-in cards, and side-out choices performed well against decks like Snake-Eye, Tenpai, Labrynth, Branded, Kashtira, Runick, Floowandereeze, and Tearlaments.

## Memory File

Curated memory is saved at:

`SystemAIYugioh/data/deck_profiles/curated_opponent_memory.json`

The memory is keyed by:

- player archetype
- mode
- curated opponent name
- going plan

## Fields Stored

Each memory profile tracks:

- best engine variants
- average score by engine
- post-side delta by engine
- side-in card success counts
- side-in card average post-side delta
- side-out card success counts
- side-out card average post-side delta
- best full side plans
- worst side plans
- interruption vulnerability trends
- resilience score trends
- matchup coverage trends
- post-side validity history

## How Side Learning Works

When the side-plan optimizer receives a curated or hybrid opponent profile, it loads curated opponent memory for that exact opponent and going plan. Cards with positive historical post-side deltas receive a small boost. Cards associated with poor deltas receive a small penalty.

These weights are capped and legality still wins:

- banlist and custom limits are checked first
- blocked cards receive no memory boost
- generic post-side memory remains available as fallback
- inferred-only profiles use the older broad matchup memory

## How Engine Choices Become Opponent-Aware

Deck generation now checks curated opponent memory before falling back to broad matchup engine stats. If a curated opponent has a remembered best engine, that engine can be selected as the preferred variant. The boost remains small because engine choice still passes through package building, scoring, and regression gates.

## Updating Memory

Memory is updated by:

```powershell
python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second
```

and by curated matrix runs:

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents
```

Updates are gated. Memory is not updated if the side plan is invalid, blocked cards appear, post-side delta is strongly negative, resilience drops too much, or memory performs worse than the no-memory baseline.

## Resetting Memory

To reset curated opponent learning, delete:

`SystemAIYugioh/data/deck_profiles/curated_opponent_memory.json`

The next curated opponent analysis or matrix run will recreate it.

## Limitations

- Memory is statistical and heuristic, not proof of duel correctness.
- Small sample sizes can overvalue a side plan until more runs smooth it out.
- Engine memory only nudges selection; it does not guarantee a specific package build.
- Curated memory requires a curated or hybrid opponent profile. Unknown inferred decks still use generic matchup memory.

## Next Phase

Phase 5T should add opponent-specific choke-point simulation: test which interruptions most often stop each curated deck's likely starter lines, then feed that into side planning and hand-trap prioritization.
