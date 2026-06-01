# Phase 5H: Normalized Failure Attribution + Exact Summon Math

Phase 5H makes graph failures less noisy. Earlier phases counted every failed graph line, even when the same hand had another valid line. That made optional failed lines look like real deck weakness and could cause regression gates to reject healthy training batches.

## Normalized Failure Attribution

The hand simulator now separates raw graph failures from normalized failures.

- Raw failures are still kept for debugging.
- Optional failed lines are counted in `optional_line_failure_rate`.
- If a hand has at least one valid graph line, failed alternate lines do not count as major normalized failures.
- If no graph line is valid, the simulator attributes failure to the best attempted failed line.

New normalized metrics:

- `optional_line_failure_rate`
- `best_line_failure_rate`
- `no_valid_line_rate`
- `normalized_search_failure_rate`
- `normalized_cost_failure_rate`
- `normalized_material_failure_rate`
- `normalized_extra_deck_failure_rate`

## Regression Gate Changes

Regression gates now prefer normalized failure rates over raw search, cost, material, and Extra Deck failure rates.

The gate can reject learning when:

- `no_valid_line_rate` rises too much
- `best_line_failure_rate` rises too much
- `normalized_search_failure_rate` rises too much
- `normalized_cost_failure_rate` rises too much
- `normalized_material_failure_rate` rises too much
- `normalized_extra_deck_failure_rate` rises too much

Optional line failures alone should not reject a batch.

## Exact Summon Math

The line validator now has simple exact summon checks:

- Synchro: material levels must exactly match the target Synchro monster level when known.
- Ritual: tribute levels must meet or exceed the Ritual Monster's required level.
- Xyz: scaffold support checks matching levels and material count when the target rank is known.
- Link: scaffold support checks material count against link rating when known.

New summon math metrics:

- `synchro_exact_level_valid_rate`
- `synchro_level_failure_rate`
- `ritual_level_valid_rate`
- `ritual_level_failure_rate`
- `xyz_material_valid_rate`
- `link_material_valid_rate`

## Current Limitations

This is still not a full Yu-Gi-Oh rules engine.

- Synchro checks exact total level, but not every card text exception.
- Ritual checks total tribute level, but not replacement effects or exact spell-specific clauses.
- Xyz and Link validation are scaffolds, not full Extra Deck rule simulations.
- Optional graph failures are still visible in reports, but they are intentionally softer in scoring and gates.

## How To Validate

Run:

```powershell
python validate_phase5h.py
```

For the full Phase 5 chain:

```powershell
python validate_phase5.py
python validate_phase5b.py
python validate_phase5c.py
python validate_phase5d.py
python validate_phase5e.py
python validate_phase5f.py
python validate_phase5g.py
python validate_phase5h.py
```

## Recommended Next Phase

Phase 5I should add card-text-aware cost and condition modeling. The highest-value targets are effects that say "reveal", "discard", "send from deck", "banish from GY", and "if you control Blue-Eyes White Dragon".
