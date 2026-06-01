# Phase 5P: Post-Side Learning Memory

Phase 5P adds persistent memory for optimized side plans. The AI no longer has to rediscover every useful side-in and side-out pattern from scratch each run.

## Memory File

Post-side memory is stored at:

```text
SystemAIYugioh/data/deck_profiles/post_side_stats.json
```

Memory is keyed by:

- archetype
- mode
- matchup
- going plan

## Stored Fields

For each matchup context, memory tracks:

- side-in card counts
- side-out card counts
- average post-side delta by side-in card
- average post-side delta by side-out card
- best side-in patterns
- best side-out patterns
- best full side plans
- valid candidate rate history
- post-side score history
- post-side delta history
- rejected side cards
- cards frequently present in bad side plans

## Optimizer Influence

`deck/side_plan_optimizer.py` reads memory and applies a small capped adjustment to side-in and side-out candidate scores.

Positive historical post-side deltas can slightly boost cards and side-out choices. Negative results and bad-plan appearances can slightly reduce them.

The influence is capped and never overrides:

- banlist rules
- custom limits
- blocked-card rejection
- duplicate validation
- post-side deck legality

## Memory Updates

`post_side_evaluator.py` updates memory after successful post-side evaluations.

`train_agent.py` updates memory only when regression gates accept the training batch.

`evaluate_learning.py` compares memory-enabled post-side plans against no-memory post-side plans and reports the delta difference.

`matchup_matrix.py` records remembered side cards and memory-aided post-side deltas per cell.

## Rejection Rules

Regression gates reject memory-sensitive updates if:

- optimized post-side delta is too negative
- valid candidate rate is too low
- side optimization fails too often
- blocked cards appear
- memory worsens evaluation compared with no-memory baseline

## Limitations

- Memory is still heuristic and score-based, not match-win-rate based.
- It learns card and pattern tendencies, not exact opponent decklists.
- Extra Deck side plans are not separately modeled.
- Smoke tests use low run counts, so memory should be treated as directional until larger runs are scheduled.

## Next Phase

Phase 5Q should add opponent deck profile ingestion so post-side memory can learn against real deck families rather than broad matchup categories only.
