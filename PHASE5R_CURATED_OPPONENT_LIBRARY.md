# Phase 5R: Curated Opponent Profile Library

Phase 5R adds editable matchup knowledge for common competitive opponent decks. The inferred decklist analyzer from Phase 5Q still works, but it can now merge its decklist signals with curated profiles stored in JSON.

## Files Added

- `SystemAIYugioh/data/opponent_profiles/curated_profiles.json`
- `deck/curated_opponent_library.py`
- `validate_phase5r.py`

## Curated Profile Format

Each curated profile includes:

- `archetype` and `aliases`
- `deck_style` and `matchup_category`
- `core_cards`, `starters`, `extenders`, `interruptions`, and `board_breakers`
- dependency estimates such as graveyard, banish, search, backrow, and summon volume
- `expected_endboard`, `choke_points`, and matchup notes
- `best_counters`, `weak_counters`, `side_in_recommendations`, and `side_out_priorities`

Profiles are intentionally JSON so they can be edited without touching code.

## Profiles Included

- Snake-Eye
- Tenpai
- Labrynth
- Branded
- Kashtira
- Runick
- Floowandereeze
- Tearlaments

## How Profiles Improve Side Planning

When an opponent decklist is analyzed, the analyzer first builds a heuristic inferred profile. It then checks the curated library by aliases and card overlap. If a curated match is found, the final opponent profile is marked as `hybrid` and uses curated knowledge to improve:

- choke point identification
- counter priorities
- side-in suggestions
- side-out priorities
- expected interruptions
- matchup category

The side deck planner still respects banlist and custom limits. Curated recommendations influence ranking, but they do not force illegal cards.

## Running Opponent Analysis

```powershell
python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second
```

The output now includes profile source, matched curated profile, best counters, weak counters, curated notes, and optimized post-side recommendations.

## Running Curated Matrix Testing

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents
```

This swaps broad matchup categories for the curated opponent library and saves the same JSON and Markdown matrix reports under `SystemAIYugioh/data/training_runs/matchup_matrix/`.

## Limitations

- The curated data is matchup guidance, not a full metagame truth source.
- Profiles may lag behind real card releases or banlist shifts until edited.
- Side plans remain recommendations validated by the optimizer, not duel-perfect plans.
- Decklist matching is card-overlap based and can confuse hybrid piles if they share many staples.

## Next Phase

Phase 5S should add opponent profile performance memory: track which curated counters and side plans actually improved post-side results against each named opponent deck, then feed that back into future side-plan optimization.
