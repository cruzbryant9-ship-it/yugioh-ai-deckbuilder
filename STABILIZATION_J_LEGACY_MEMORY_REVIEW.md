# Stabilization J: Legacy Memory Refresh + Retirement Review

Stabilization J adds review tooling for old and stale memory files. It does not add gameplay systems, change scoring weights, alter authored Blue-Eyes behavior, activate filler-memory influence, or bypass banlist/custom limits.

## Review Tool

Run:

```powershell
python legacy_memory_review.py
```

The tool inspects:

- `learned_card_stats.json`
- `learning_tuning.json`
- `learned_engine_stats.json`
- `post_side_stats.json`
- `generic_ratio_memory.json`
- `generic_benchmark_history.json`
- `generic_diff_index.json`
- `generic_filler_memory.json`
- `matchup_engine_stats.json`
- `curated_opponent_memory.json`

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/legacy_memory_review/
```

Latest files:

- `latest_legacy_memory_review.json`
- `latest_legacy_memory_review.md`

## What It Checks

For each memory file, the review records:

- file existence
- record count estimate
- last modified time
- schema version if present
- provenance coverage
- stale status
- missing Phase 6-era fields
- blocked-card contamination
- validator probe contamination
- compatibility with current metrics
- recommendation

The blocked/invalid scan looks for:

- Pot of Greed
- Protector with Eyes of Blue
- Strength in Unity
- Index Probe
- Card Probe
- Warning Probe
- Helpful Add
- Harmful Add
- Helpful Remove
- Harmful Remove
- Probe Card

## Recommendations

The review emits one recommendation per memory:

- `keep_active`: memory is current enough and used by active paths
- `refresh`: memory is stale or legacy-shaped but still useful
- `quarantine`: contamination or validator-generated dominance was detected
- `retire`: incompatible or no longer useful
- `collect_more_data`: signal exists but is not strong enough for active influence

## Quarantine Helper

The quarantine mechanism is in:

```text
SystemAIYugioh/memory_quarantine.py
```

It supports:

- copy old memory to `SystemAIYugioh/data/memory_quarantine/`
- preserve timestamps with `shutil.copy2`
- write a manifest
- never delete the original automatically
- optionally create an inactive sidecar marker if explicitly requested

Example:

```python
from SystemAIYugioh.memory_quarantine import quarantine_memory_file

quarantine_memory_file(
    "SystemAIYugioh/data/deck_profiles/learned_card_stats.json",
    "Manual review before refresh",
)
```

## Refresh Commands

The review includes suggested commands instead of automatically overwriting memory. Typical refreshes include:

```powershell
python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 20
python compare_engines.py --archetype "Blue-Eyes" --mode meta --runs-per-engine 3
python post_side_evaluator.py --archetype "Blue-Eyes" --mode meta --matchup combo --going second --runs 5
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 3 --use-curated-opponents
```

## Validation

Run:

```powershell
python validate_stabilization_j.py
```

The validator checks that the review runs, quarantine copies safely, manifests are written, blocked-card scans work, recommendations are generated, production memory is not deleted, Stabilization I still passes, and matchup matrix smoke still passes.
