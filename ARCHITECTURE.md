# SystemAIYugioh Architecture

SystemAIYugioh is an autonomous Yu-Gi-Oh deckbuilding and evaluation project. Phase 5 moved the system from pure heuristic generation toward structured gameplay-aware analysis while keeping the original training and CLI workflow intact.

## System Map

- `yugioh_ai_deckbuilder.py` is the interactive entry point.
- `deck/` contains deck construction, scoring, combo simulation, package building, side planning, opponent analysis, and memory helpers.
- `SystemAIYugioh/` contains card database sync, banlist support, regression gates, report schema helpers, logging, and shared JSON safety utilities.
- `data/` contains custom limits and blocked-card cleanup logic.
- `SystemAIYugioh/data/` stores card data, learned memory, post-side memory, curated opponent profiles, and training reports.
- `validate_phase5*.py` and `validate_stabilization_a.py` are the validation suite.

## Data Flow

1. Card data loads through `SystemAIYugioh/card_database.py`.
2. Banlist/custom limit cleanup runs through `data/card_limits.py`.
3. Decks are generated through package-aware builders in `deck/builder.py` and `deck/package_builder.py`.
4. Decks are scored through `score_deck_breakdown()` plus combo, graph, resource, package, interruption, matchup, side, and opponent metrics.
5. Training/evaluation scripts save reports and learned memory only after regression gates pass.
6. Matchup and opponent analysis feed engine stats, side memory, and curated opponent memory.

## Major Modules

- Package construction: `deck/packages.py`, `deck/package_builder.py`, `deck/package_quality.py`
- Combo simulation: `deck/combo_lines.py`, `deck/hand_simulator.py`, `deck/line_graph.py`, `deck/line_validator.py`
- Resource/material validation: `deck/resource_state.py`, `deck/card_metadata.py`
- Costs/conditions/history: `deck/card_text_parser.py`, `deck/card_conditions.py`
- Interruption modeling: `deck/chain_model.py`, `deck/interruption_profiles.py`
- Matchups and siding: `deck/matchup_profiles.py`, `deck/side_deck_planner.py`, `deck/side_plan_optimizer.py`, `deck/side_application.py`
- Opponent simulation: `deck/opponent_analyzer.py`, `deck/opponent_choke_model.py`, `deck/opponent_branch_graph.py`, `deck/opponent_graph_simulator.py`, `deck/opponent_resource_state.py`, `deck/opponent_probability_simulator.py`

## Memory Systems

- Learned card stats: `SystemAIYugioh/data/deck_profiles/learned_card_stats.json`
- Learned engine stats: `SystemAIYugioh/data/deck_profiles/learned_engine_stats.json`
- Matchup engine stats: `SystemAIYugioh/data/deck_profiles/matchup_engine_stats.json`
- Post-side stats: `SystemAIYugioh/data/deck_profiles/post_side_stats.json`
- Curated opponent memory: `SystemAIYugioh/data/deck_profiles/curated_opponent_memory.json`

Memory writes should pass regression gates and use safe JSON helpers where practical.

## Scoring Pipeline

The scoring pipeline combines old heuristic fields with newer gameplay metrics. It preserves compatibility fields like `final_score`, `starter_score`, `extender_score`, and `brick_penalty`, while adding package quality, graph validity, resource validity, typed material validity, interruption resilience, side-deck quality, post-side deltas, opponent graph metrics, and probability-weighted opponent metrics.

## Matchup And Side Pipeline

Broad matchup profiles are converted into side priorities. Curated or inferred opponent profiles refine those priorities. The side planner proposes candidate side cards; the optimizer tests legal side-in/out combinations and chooses the best valid post-side deck.

## Opponent Simulation Pipeline

Opponent decklists are parsed, analyzed, optionally matched to curated profiles, then evaluated through choke models, timing windows, ordered branch graphs, resource validation, and Monte Carlo opening probability. This is still not full duel self-play.

## Validation Strategy

Smoke mode uses low run counts and matrix settings suitable for quick checks. Full mode keeps larger run counts available for deeper validation. Phase validators protect backward compatibility, while `validate_stabilization_a.py` verifies stabilization utilities and smoke workflow.

## Known Limitations

- The project is not a full duel simulator.
- Opponent probabilities are heuristic and opening-hand only.
- Card text parsing is pattern-based.
- Some metric plumbing is still repeated across report writers.
- Runtime is dominated by matrix and nested validator commands.
