# Phase 7A: Benchmark & Cache Trust

Infrastructure-only phase. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression threshold, filler-memory, or opponent-influence changes were made.

## Fingerprint Coverage

- Source fingerprint version: 1
- Source hash: `b6f48a47fe68cea240fa6f21b5590e24eadb647db0e255a3064f09efee6e2748`
- Covered files: 11
- `deck/builder.py`
- `deck/package_builder.py`
- `deck/hand_simulator.py`
- `deck/line_validator.py`
- `deck/side_deck_planner.py`
- `deck/side_plan_optimizer.py`
- `deck/post_side_evaluation.py`
- `deck/choke_simulator.py`
- `deck/opponent_graph_simulator.py`
- `deck/opponent_probability_simulator.py`
- `matchup_matrix.py`

## Cache Invalidation Coverage

- Matrix cache fingerprints now include deterministic content hashes for score-affecting source files.
- Matrix cache keys also include the active source fingerprint and benchmark seed when provided.
- Source-only changes invalidate stale matrix cache entries without requiring manual `CACHE_VERSION` bumps.
- Validation: {'ok': True, 'base_file': 'deck/builder.py', 'base_key': 'e519c0623f9f446acbe3d31eedcdc35a76f72e8d4c06890716244237f1d21b96', 'edited_key': '27b70d9cb560be0db869e8d41c29cf5d7bb9d511006c600eab760f2516747a06'}

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
