# Phase 5Q: Opponent Deck Profile Ingestion

Phase 5Q lets the AI ingest opponent decklists and convert them into specific opponent profiles. These profiles refine side-deck planning beyond broad matchup labels such as `combo`, `graveyard`, or `backrow`.

## Accepted Decklist Formats

The parser supports:

- plain text decklists
- one-card-per-line lists
- count-prefixed lines such as `3 Ash Blossom & Joyous Spring`
- suffix count lines such as `Ash Blossom & Joyous Spring x3`
- simple YDK-style sections
- section headers: `Main Deck`, `Extra Deck`, `Side Deck`, `#main`, `#extra`, `!side`

## Opponent Profile Fields

`deck/opponent_profiles.py` defines `OpponentProfile` with:

- name
- archetype
- known cards
- likely engines
- key starters
- key extenders
- key interruptions
- key board breakers
- graveyard dependency
- backrow density
- spell/trap density
- monster effect density
- summon volume
- banish dependency
- search dependency
- going-first plan
- going-second plan
- expected endboard
- choke points
- recommended counters
- nearest broad matchup

## Inference

`deck/opponent_analyzer.py` uses card names, card text, and simple heuristics to infer:

- archetype
- engine presence
- deck style
- likely hand traps
- likely board breakers
- choke points
- nearest broad matchup
- side priorities

If inference is uncertain, it falls back to `unknown_meta`.

## CLI Usage

```powershell
python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second
```

The analyzer prints the inferred opponent style, expected threats, choke points, recommended side-in/out cards, and post-side score estimate.

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/opponent_profiles/
```

## Matrix Integration

`matchup_matrix.py` supports:

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --opponent-profiles-folder path/to/folder
```

When provided, text decklists in the folder are analyzed and used as specific matchup targets.

## Memory Integration

Post-side memory can key by broad matchup name or by opponent profile name. This allows the system to remember side plans against specific deck families over time.

## Limitations

- Inference is heuristic, not a full metagame classifier.
- Unknown or misspelled card names are still included by name but may lack text-derived signals.
- Opponent behavior is not simulated.
- Specific card rulings are approximated by text/category heuristics.

## Next Phase

Phase 5R should add opponent-specific matchup libraries: curated profiles for common decks such as Snake-Eye, Tenpai, Labrynth, Branded, Kashtira, Runick, Floowandereeze, and Tearlaments.
