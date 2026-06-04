# Phase 7A: Benchmark & Cache Trust

Infrastructure-only phase. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression threshold, filler-memory, or opponent-influence changes were made.

## Fingerprint Coverage

- Source fingerprint version: 1
- Source hash: `8695afd64d0e5e9f4e0fdbd40ba68f4d3d913e7c74b47e937281aa459308b8df`
- Covered files: 55
- `deck/advisory_influence_budget.py`
- `deck/archetype_role_inference.py`
- `deck/builder.py`
- `deck/card_conditions.py`
- `deck/card_metadata.py`
- `deck/card_text_parser.py`
- `deck/chain_model.py`
- `deck/package_builder.py`
- `deck/hand_simulator.py`
- `deck/combo_lines.py`
- `deck/curated_opponent_memory.py`
- `deck/deck_analysis.py`
- `deck/deck_utils.py`
- `deck/generic_combo_skeleton.py`
- `deck/generic_deck_builder.py`
- `deck/generic_deck_repair.py`
- `deck/generic_filler_selector.py`
- `deck/generic_package_extractor.py`
- `deck/generic_package_replay.py`
- `deck/generic_repair_diagnostics.py`
- `deck/generic_tuner.py`
- `deck/interruption_profiles.py`
- `deck/line_graph.py`
- `deck/line_validator.py`
- `deck/package_quality.py`
- `deck/packages.py`
- `deck/post_side_memory.py`
- `deck/resource_state.py`
- `deck/side_application.py`
- `deck/side_deck_scoring.py`
- `deck/side_deck_planner.py`
- `deck/side_plan_optimizer.py`
- `deck/post_side_evaluation.py`
- `deck/choke_simulator.py`
- `deck/opponent_graph_simulator.py`
- `deck/opponent_probability_simulator.py`
- `deck/opponent_analyzer.py`
- `deck/opponent_choke_model.py`
- `deck/opponent_branch_graph.py`
- `deck/opponent_profiles.py`
- `deck/opponent_resource_state.py`
- `deck/matchup_profiles.py`
- `deck/matchup_engine_stats.py`
- `deck/engine_variants.py`
- `deck/timing_windows.py`
- `SystemAIYugioh/banlist.py`
- `SystemAIYugioh/cache_fingerprint.py`
- `SystemAIYugioh/matrix_cache.py`
- `SystemAIYugioh/metric_registry.py`
- `SystemAIYugioh/opponent_metric_builder.py`
- `SystemAIYugioh/opponent_signal_sentinel.py`
- `SystemAIYugioh/regression_gates.py`
- `SystemAIYugioh/report_schema.py`
- `SystemAIYugioh/score_snapshot.py`
- `matchup_matrix.py`

## Cache Invalidation Coverage

- Matrix cache fingerprints now include deterministic content hashes for score-affecting source files.
- Matrix cache keys also include the active source fingerprint and benchmark seed when provided.
- Source-only changes invalidate stale matrix cache entries without requiring manual `CACHE_VERSION` bumps.
- Validation: {'ok': True, 'base_file': 'SystemAIYugioh/banlist.py', 'base_key': 'ca6f4035628d10a4a96ae10b7d349ca0842a6b992084a5b74e12676ea68ddf1d', 'edited_key': '27b70d9cb560be0db869e8d41c29cf5d7bb9d511006c600eab760f2516747a06'}

## Parity Results

- Matched cells: 3
- Best warm engine: pure
- Detailed report: `CACHE_PARITY_REPORT.md`

## Determinism Results

- Score drift: 0.0
- Engine drift: False
- Deck drift: False

## Cache Provenance

- Matrix reports include `cache_fingerprint` and `source_fingerprint`.
- Matrix cells include `cache_hit`, `cache_generation_time`, `cache_created_timestamp`, `cache_fingerprint`, and `source_fingerprint`.

## Remaining Risks

- Determinism is guaranteed only when a seed is provided for benchmark trust checks.
- Existing non-seeded CLI runs may still intentionally explore random weighted deck/package choices.
- Persistent cache trust depends on all future score-affecting modules being added to `SCORE_AFFECTING_SOURCE_FILES`.
