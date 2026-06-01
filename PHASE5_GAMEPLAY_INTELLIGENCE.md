# Phase 5 Gameplay Intelligence

## What Was Added

Phase 5 adds the first real gameplay-intelligence layer on top of the existing Phase 4 heuristic optimizer. The old systems still exist: card sync, banlist/custom limits, deck generation, heuristic scoring, training, learned card stats, engine stats, evaluation, and engine comparison.

New systems:

- `deck/combo_lines.py`: structured combo line definitions.
- `deck/hand_simulator.py`: opening-hand simulation and real combo reports.
- `validate_phase5.py`: validation script for schema, imports, blocked cards, and command compatibility.
- Expanded score breakdown fields in `deck/builder.py`.
- Expanded training, evaluation, and engine comparison reports.

## How Combo Lines Work

Combo lines are represented by `ComboLine` objects. Each line has structured fields:

- `name`
- `archetype`
- `required_cards`
- `optional_cards`
- `starter_cards`
- `extender_cards`
- `search_targets`
- `normal_summon_required`
- `once_per_turn_tags`
- `locks`
- `endboard`
- `interruptions`
- `follow_up`
- `weak_to`
- `recovery_routes`
- `brick_risk`
- `score`

The first included lines are Blue-Eyes focused:

- Sage + White Stone -> Blue-Eyes Spirit Dragon
- Chaos Form + Chaos MAX -> Chaos MAX pressure
- True Light + Jet Dragon -> Jet protection loop
- Dictator of D. + Blue-Eyes access -> setup line
- Bingo Machine access -> Blue-Eyes consistency line

## How Hand Simulation Works

`deck/hand_simulator.py` samples opening hands and returns a structured result:

```json
{
  "hand": [],
  "playable": true,
  "available_lines": [],
  "best_line": null,
  "starter_count": 0,
  "extender_count": 0,
  "brick_count": 0,
  "interruption_count": 0,
  "follow_up_count": 0,
  "handtrap_count": 0,
  "board_breaker_count": 0,
  "normal_summon_conflict": false,
  "estimated_endboard": [],
  "recovery_routes": [],
  "weak_to": [],
  "score": 0.0
}
```

The simulator currently detects:

- playable starters
- extenders
- bricks
- normal summon conflicts
- known combo line availability
- interruption cards
- follow-up cards
- handtrap and board breaker counts

## How Scoring Changed

`score_deck_breakdown()` keeps all legacy fields:

- `consistency_score`
- `starter_score`
- `extender_score`
- `interruption_score`
- `brick_penalty`
- `endboard_score`
- `learned_card_bonus`
- `final_score`

It now also includes Phase 5 fields:

- `playable_hand_rate`
- `brick_rate`
- `combo_line_score`
- `interruption_resilience_score`
- `follow_up_score`

The final score is supplemented by small gameplay intelligence terms. The old scoring system still matters; Phase 5 does not replace it yet.

## How To Run Validation

From PowerShell:

```powershell
cd "C:\Users\theeg\OneDrive\Desktop\yugioh_ai_deckbuilder"
python validate_phase5.py
```

The validator checks:

- blocked cards do not appear
- hand simulator schema is valid
- Blue-Eyes combo lines are registered
- score breakdown contains Phase 5 fields
- training runs for 2 runs
- evaluation runs for 2 runs
- engine comparison runs for 1 run per engine
- JSON writes do not crash
- circular imports are avoided

## How To Add New Combo Lines

Open `deck/combo_lines.py` and add a new `ComboLine` to `COMBO_LINES` or an archetype-specific tuple.

Recommended pattern:

1. Give the line a human-readable `name`.
2. Set the `archetype`.
3. Put mandatory openers in `required_cards`.
4. Put flexible pieces in `optional_cards`.
5. Mark whether it consumes the normal summon.
6. Describe endboard, interruptions, follow-up, weaknesses, and recovery routes.
7. Keep `score` conservative until validated by training and evaluation.

## Current Limitations

This is still not a full Yu-Gi-Oh rules engine. The simulator does not yet resolve chains, costs, once-per-turn conflicts, summon locks, exact card activation legality, matchup interaction, or side decking.

The system now understands some structured hand and combo concepts, but many detections are still text-based. Combo lines are manually authored and should be expanded archetype-by-archetype.

## Next Roadmap

Highest-priority next work:

1. Add explicit package-based deck construction.
2. Add one-card and two-card combo requirements.
3. Model once-per-turn conflicts more strictly.
4. Add going-first and going-second hand goals.
5. Add opponent interruption simulation.
6. Add matchup profiles.
7. Feed engine comparison winners back into deck generation as structured packages.
8. Add regression gates so learned profiles cannot be saved when real combo metrics get worse.
9. Add unit tests around every new simulator function.
10. Build a markdown or HTML report summarizing Phase 5 metrics after each automation run.

