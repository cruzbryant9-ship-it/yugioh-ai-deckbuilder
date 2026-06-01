# Phase 5O: Side-Plan Optimization

Phase 5O improves post-side simulation by searching for a legal side-in/side-out plan instead of applying the first recommendation directly.

## Candidate Generation

`deck/side_plan_optimizer.py` exposes:

```python
optimize_side_plan(main_deck, side_deck, matchup, going, card_pool, max_candidates=50)
```

The optimizer tests side-in counts of 3, 6, 9, 12, and 15 when enough legal cards are available. It creates candidate plans from high-priority side cards and high-priority side-out cards, then validates each candidate with `apply_side_plan()`.

## Side-In Scoring

Side-in cards are prioritized from the side deck by:

- high-value cards from the matchup profile
- anti-combo cards into combo or monster-effect-heavy matchups
- backrow removal into backrow-heavy matchups
- graveyard hate into graveyard-heavy matchups
- going-first trap/negation value
- going-second removal and breaker value

## Side-Out Scoring

The optimizer prefers siding out:

- low matchup-value cards
- excess high-level or low-action cards
- redundant board breakers going first
- weak traps going second
- cards with little role contribution
- cards marked low-value by the matchup profile

It avoids siding out:

- Blue-Eyes core cards
- starters
- searchers
- known combo pieces

## Plan Selection

Each valid candidate preserves main-deck size, respects copy limits, rejects blocked cards, and keeps side-in/side-out counts matched. The highest-scoring legal post-side deck is selected.

The result includes:

- `candidate_count`
- `valid_candidate_count`
- `rejected_candidate_count`
- `valid_candidate_rate`
- `best_side_in`
- `best_side_out`
- `best_score`
- `post_side_delta`
- `optimization_used`
- rejection reasons

## Integration

`post_side_evaluator.py`, `train_agent.py`, `evaluate_learning.py`, and `matchup_matrix.py` now use optimized side plans. Regression gates check post-side delta, side-plan validity, valid candidate rate, and optimization success rate.

## Limitations

- Candidate search is intentionally capped for runtime.
- Scoring is still heuristic and does not simulate full matches.
- The optimizer does not yet search Extra Deck side plans.
- It selects from recommended side-deck cards, not every possible card in the database.

## Next Phase

Phase 5P should add post-side matchup learning: learn which side-in/out patterns repeatedly improve scores by matchup and feed that back into future side-plan generation.
