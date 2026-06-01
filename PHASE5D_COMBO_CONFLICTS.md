# Phase 5D Combo Conflicts

## What Phase 5D Adds

Phase 5D improves gameplay realism by expanding Blue-Eyes combo lines and modeling common hand conflicts:

- normal summon conflicts
- once-per-turn overlap
- dead duplicate cards
- unsupported high-level pieces
- payoff without enabler
- enabler without payoff
- incompatible lines

## Combo Line Schema

Combo lines now include:

- `required_cards`
- `starter_cards`
- `extender_cards`
- `searched_cards`
- `search_targets`
- `normal_summon_required`
- `once_per_turn_tags`
- `endboard`
- `interruptions`
- `follow_up`
- `weak_to`
- `recovery_routes`
- `brick_risk`
- `line_score`

Blue-Eyes lines currently include Sage/Stone, Dictator setup, Bingo access, Wishes access, True Light + Jet Dragon, Chaos MAX, Ultimate Fusion, Spirit Dragon, Abyss Dragon follow-up, and Alternative White Dragon pressure.

## Conflict Modeling

`deck/hand_simulator.py` now detects:

- multiple available lines that need the normal summon
- duplicate once-per-turn tags across available lines
- repeated hard once-per-turn or payoff cards
- too many high-level monsters relative to enablers
- ritual pieces without enough support
- payoff cards without enablers
- enablers without payoff

The simulator returns:

- `normal_summon_conflict`
- `once_per_turn_conflicts`
- `dead_duplicate_count`
- `unsupported_piece_count`
- `payoff_without_enabler`
- `enabler_without_payoff`
- `conflicting_lines`

## Best-Line Selection

Best-line selection now uses effective line score plus:

- endboard count
- interruption count
- follow-up count
- recovery route count

Then it subtracts penalties for:

- brick risk
- normal summon conflicts
- once-per-turn conflicts
- dead duplicates
- unsupported pieces
- payoff/enabler mismatch

## Scoring Changes

`score_deck_breakdown()` now includes:

- `normal_summon_conflict_rate`
- `once_per_turn_conflict_rate`
- `dead_duplicate_rate`
- `payoff_without_enabler_rate`
- `enabler_without_payoff_rate`
- `best_line_average_score`

All previous Phase 5, 5B, and 5C fields remain compatible.

## Limitations

This is still not a full rules engine. Conflict detection is conservative and heuristic. It does not resolve costs, chains, exact activation windows, material legality, or opponent interaction.

## Adding Future Combo Lines

Add new `ComboLine` objects in `deck/combo_lines.py`. Use precise `once_per_turn_tags` and `normal_summon_required` values so conflict modeling can reason about overlap. Prefer conservative `line_score` values until validation data proves the line is reliable.

