# Learning Signal Audit

- Report version: stabilization-i-v1
- Created: 2026-06-01T01:44:41.714415+00:00
- JSON report: `SystemAIYugioh\data\training_runs\learning_signal_audit\latest_learning_signal_audit.json`
- Signals audited: 14
- Active influences: learned_card_stats, learning_tuning, learned_engine_stats, matchup_engine_stats, post_side_memory, curated_opponent_memory, generic_ratio_memory, generic_benchmark_history, generic_diff_index, diagnosis bias, diff-index bias
- No-op influences: filler-memory bias
- Reporting-only systems: generic_filler_memory, filler_signal_gates
- Stale memories: learned_card_stats, learning_tuning, learned_engine_stats
- Noisy memories: generic_diff_index, diff-index bias
- Unsafe-to-influence memories: generic_filler_memory, filler-memory bias

## Signal Table

| Signal | Classification | Influence | Recommendation |
|---|---|---|---|
| learned_card_stats | active, useful, stale | score_bonus_and_weighted_fallback | keep active |
| learning_tuning | active, stale | weighted_random_fallback | collect more data |
| learned_engine_stats | active, stale | weighted_random_fallback | collect more data |
| matchup_engine_stats | active, useful | matchup_engine_selection | keep active |
| post_side_memory | active, useful | side_plan_optimization | keep active |
| curated_opponent_memory | active, useful | opponent_specific_side_and_engine_selection | keep active |
| generic_ratio_memory | active, useful | generic_builder_ratio_profile | keep active |
| generic_benchmark_history | active, useful | diagnosis_source | keep active |
| generic_diff_index | active, experimental, noisy | small_capped_advisory | keep experimental |
| generic_filler_memory | reporting-only, unsafe-to-influence | reporting_and_gate_input | collect more data |
| filler_signal_gates | reporting-only, useful | gate/report | keep active |
| diagnosis bias | active, useful | small_capped_ratio_nudge | keep active |
| diff-index bias | active, experimental, noisy | small_capped_advisory | keep experimental |
| filler-memory bias | no-op, experimental, unsafe-to-influence | disabled_by_default | keep experimental |

## Evidence

### learned_card_stats
- Used by deck.builder learned_card_weight() and score_deck_breakdown learned_card_bonus.
- Memory file exists at SystemAIYugioh\data\deck_profiles\learned_card_stats.json (17498 bytes).
- Last modified: 2026-05-24T21:32:55.584251+00:00 (7.17 days old).
- Profile/record count estimate: 8.

### learning_tuning
- Used by deck.builder tuning_card_weight() in the weighted fallback path.
- Memory file exists at SystemAIYugioh\data\deck_profiles\learning_tuning.json (3111 bytes).
- Last modified: 2026-05-24T21:32:53.581722+00:00 (7.17 days old).
- Profile/record count estimate: 20.

### learned_engine_stats
- Used by deck.builder engine_card_weight() in the weighted fallback path.
- Memory file exists at SystemAIYugioh\data\deck_profiles\learned_engine_stats.json (3290 bytes).
- Last modified: 2026-05-24T21:32:53.582719+00:00 (7.17 days old).
- Profile/record count estimate: 9.

### matchup_engine_stats
- Used by deck.builder when matchup/going context is provided.
- Latest matrix updated stats: True.
- Memory file exists at SystemAIYugioh\data\deck_profiles\matchup_engine_stats.json (35706 bytes).
- Last modified: 2026-06-01T01:44:09.079418+00:00 (0.0 days old).
- Profile/record count estimate: 24.

### post_side_memory
- Used by side_plan_optimizer side-in and side-out adjustment helpers.
- Memory file exists at SystemAIYugioh\data\deck_profiles\post_side_stats.json (106972 bytes).
- Last modified: 2026-06-01T01:44:41.239779+00:00 (0.0 days old).
- Profile/record count estimate: 319.

### curated_opponent_memory
- Used by side_plan_optimizer and matchup_engine_stats for curated opponents.
- Latest matrix updated curated opponent memory: True.
- Memory file exists at SystemAIYugioh\data\deck_profiles\curated_opponent_memory.json (768846 bytes).
- Last modified: 2026-06-01T01:44:11.460285+00:00 (0.0 days old).
- Profile/record count estimate: 721.

### generic_ratio_memory
- Used by generic_deck_builder when use_ratio_memory=True.
- Memory file exists at SystemAIYugioh\data\deck_profiles\generic_ratio_memory.json (12512254 bytes).
- Last modified: 2026-05-30T07:29:55.301854+00:00 (1.76 days old).
- Profile/record count estimate: 87.

### generic_benchmark_history
- Used by generic_tuner through load_tuning_diagnosis() to drive diagnosis bias.
- Memory file exists at SystemAIYugioh\data\deck_profiles\generic_benchmark_history.json (902831 bytes).
- Last modified: 2026-05-30T07:29:55.349514+00:00 (1.76 days old).
- Profile/record count estimate: 49.

### generic_diff_index
- Used by generic_tuner get_diff_index_advisory_signal(); advisory-only and capped.
- Latest generic benchmark diff-index bias used count: 3.
- Memory file exists at SystemAIYugioh\data\deck_profiles\generic_diff_index.json (45981 bytes).
- Last modified: 2026-05-30T07:29:55.398803+00:00 (1.76 days old).
- Profile/record count estimate: 11.

### generic_filler_memory
- Feeds filler_signal_gates and reports; influence is off by default.
- Phase 6U still saw zero ordering/selection changes when the experiment flag was enabled.
- Memory file exists at SystemAIYugioh\data\deck_profiles\generic_filler_memory.json (107409 bytes).
- Last modified: 2026-05-30T07:29:55.356094+00:00 (1.76 days old).
- Profile/record count estimate: 153.

### filler_signal_gates
- Defines activation readiness; does not itself alter deck construction.
- Activation-ready fillers: Ash Blossom & Joyous Spring, Effect Veiler, Ghost Belle & Haunted Mansion.

### diagnosis bias
- generic_tuner applies small ratio nudges from generic_benchmark_history diagnoses.
- Latest benchmark diagnosis bias used count: 4.

### diff-index bias
- Uses scrubbed generic_diff_index signals as capped advisory nudges.
- Latest benchmark diff-index bias used count: 3.

### filler-memory bias
- Experiment flag exists but default is False.
- Latest Phase 6U A/B ordering changes: 0; selection changes: 0.
