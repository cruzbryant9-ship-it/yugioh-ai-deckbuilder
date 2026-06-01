# Stabilization Pass G: Memory Isolation + Advisory Influence Safety

## What Changed

Stabilization G adds a memory safety layer before any future diff-index tuning bias is allowed.

The new shared memory context lives in:

```text
SystemAIYugioh/memory_context.py
```

Production memory still defaults to:

```text
SystemAIYugioh/data/deck_profiles/
```

Validators can now redirect memory writes with `YUGIOH_AI_MEMORY_ROOT` and `YUGIOH_AI_TEST_MODE`, or by using the temporary isolated-memory context helper.

## Isolated Memory Files

The following production learning files now resolve through the shared memory context:

- `generic_diff_index.json`
- `generic_benchmark_history.json`
- `generic_ratio_memory.json`
- `post_side_stats.json`
- `matchup_engine_stats.json`
- `curated_opponent_memory.json`

Validator probes should write only to temporary memory roots. If a validator-generated update accidentally targets production memory, the writer skips it.

## Provenance

Memory updates now carry lightweight provenance:

- `source`
- `validator_generated`
- `smoke`
- `legal`
- `confidence_score`
- `improvement`
- `timestamp`

Writers keep a bounded `provenance_log` and a `last_update_provenance` field.

## Rejection Classification

Rejected targeted recommendations are now classified by cause:

- `score_negative`
- `legality_failed`
- `blocked_card`
- `confidence_failed`
- `repair_failed`
- `quota_warning`
- `incomplete_deck`
- `copy_limit_failed`

Only score-negative, legal, confidence-safe failures are eligible for harmful movement learning. Legality failures and incomplete decks are stored as rejected attempts, but they do not become harmful card/package memory.

## Repair Hardening

`deck/generic_deck_repair.py` now reports:

- `repair_action_count`
- `repair_action_cap`
- `repair_action_cap_reached`
- `repair_converged`
- `repair_failure_cause`

Repair is checked for idempotence so `repair(repair(deck))` should not keep mutating the same deck.

## Advisory Budget Foundation

`deck/advisory_influence_budget.py` creates a shared budget for future advisory nudges. Diagnosis bias and future diff-index bias can share one global cap, and a kill switch can disable advisory influence. Diff-index memory is not applied to tuning yet.

## Validation

Run:

```bash
python validate_stabilization_g.py
```

The validator checks isolated memory writes, production memory preservation, provenance, rejection cause classification, repair idempotence, advisory caps, Phase 6L compatibility, Stabilization F compatibility, and matchup matrix smoke.

## Current Limitations

This pass does not make the diff index influence tuning. It only prepares the safety controls for a future Phase 6M pass.
