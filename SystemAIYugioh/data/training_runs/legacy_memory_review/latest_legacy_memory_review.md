# Legacy Memory Review

- Created: 2026-05-30T07:55:03.459311+00:00
- JSON report: `SystemAIYugioh\data\training_runs\legacy_memory_review\latest_legacy_memory_review.json`
- Memories reviewed: 10
- Stale memories: learned_card_stats, learning_tuning, learned_engine_stats, post_side_memory
- Contaminated memories: none
- Refresh candidates: learned_card_stats, learning_tuning, learned_engine_stats, post_side_memory
- Quarantine candidates: none
- Retirement candidates: none

## Review Table

| Memory | Records | Age Days | Compatibility | Blocked Hits | Probe Hits | Recommendation |
|---|---:|---:|---|---:|---:|---|
| learned_card_stats | 8 | 5.43 | legacy_missing_current_metrics | 0 | 0 | refresh |
| learning_tuning | 20 | 5.43 | legacy_missing_current_metrics | 0 | 0 | refresh |
| learned_engine_stats | 9 | 5.43 | legacy_missing_current_metrics | 0 | 0 | refresh |
| post_side_memory | 271 | 3.16 | legacy_missing_current_metrics | 0 | 0 | refresh |
| generic_ratio_memory | 87 | 0.02 | phase6_compatible | 0 | 0 | keep_active |
| generic_benchmark_history | 49 | 0.02 | phase6_partial | 0 | 0 | keep_active |
| generic_diff_index | 11 | 0.02 | phase6_compatible | 0 | 0 | keep_active |
| generic_filler_memory | 153 | 0.02 | phase6_compatible | 0 | 0 | collect_more_data |
| matchup_engine_stats | 24 | 0.0 | phase6_partial | 0 | 0 | keep_active |
| curated_opponent_memory | 348 | 0.0 | phase6_compatible | 0 | 0 | keep_active |

## Refresh Commands

### learned_card_stats
- `python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 20`
- `python evaluate_learning.py --archetype "Blue-Eyes" --mode meta --runs 10`

### learning_tuning
- `python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 20`

### learned_engine_stats
- `python compare_engines.py --archetype "Blue-Eyes" --mode meta --runs-per-engine 3`

### post_side_memory
- `python post_side_evaluator.py --archetype "Blue-Eyes" --mode meta --matchup combo --going second --runs 5`

### generic_ratio_memory
- `python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5`

### generic_benchmark_history
- `python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5`

### generic_diff_index
- `python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5 --show-replay`

### generic_filler_memory
- `python single_filler_attribution_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 3`
- `python filler_signal_gate_report.py`

### matchup_engine_stats
- `python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 3 --use-curated-opponents`

### curated_opponent_memory
- `python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 3 --use-curated-opponents`
- `python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second`

## Quarantine Behavior

- The review does not quarantine or delete production memory automatically.
- Use `SystemAIYugioh.memory_quarantine.quarantine_memory_file()` to copy a selected memory into quarantine.
- The helper writes a manifest and preserves timestamps with `shutil.copy2`.
