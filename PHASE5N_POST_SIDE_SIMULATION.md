# Phase 5N: Post-Side Simulation

Phase 5N turns side-deck recommendations into testable post-side deck variants. The AI now compares Game 1 deck quality against the recommended Games 2/3 configuration after applying side-in and side-out cards.

## Side Application

`deck/side_application.py` exposes:

```python
apply_side_plan(main_deck, side_deck, side_in, side_out)
```

It removes side-out cards from the main deck, adds side-in cards from the side deck, preserves main-deck size, respects copy limits, rejects blocked cards, and returns warnings when a plan cannot be applied cleanly.

## Side Planner Changes

`deck/side_deck_planner.py` now returns explicit plan fields:

- `side_in`
- `side_out`
- `priority_order`
- `matchup_reason`
- `going_reason`

The older `cards_to_side_out` field is preserved for compatibility.

## Post-Side Evaluation

Run:

```powershell
python post_side_evaluator.py --archetype "Blue-Eyes" --mode meta --matchup combo --going second --runs 1
```

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/post_side/
```

Each run records:

- Game 1 score
- post-side score
- post-side delta
- side plan validity
- side cards used
- cards sided out
- playable hand rate
- brick rate
- resilience score
- interruption vulnerability rates
- package quality

## Training, Evaluation, And Matrix Integration

`train_agent.py` now stores:

- `game1_score`
- `post_side_score`
- `post_side_delta`
- `post_side_valid`
- `side_cards_used`
- `cards_sided_out`

`evaluate_learning.py` compares baseline and learned generation on Game 1 score, post-side score, post-side delta, and side-plan validity.

`matchup_matrix.py` now records post-side score and delta per cell and includes post-side performance in engine ranking.

## Regression Gates

Learning is rejected when:

- post-side score drops too far
- post-side delta is strongly negative
- side plans are invalid too often
- blocked cards appear after siding
- post-side deck size is invalid

## Limitations

- This is still a recommendation evaluator, not a real match simulator.
- Side-out logic is heuristic and conservative.
- It does not yet model exact opponent decklists or post-side opponent behavior.
- Extra Deck siding is not modeled separately.

## Next Phase

Phase 5O should add side-plan optimization: test multiple side-in/out combinations, select the best legal post-side list, and compare going-first and going-second Games 2/3 plans separately.
