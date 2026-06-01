# Stabilization K: Opponent Intelligence Integration Audit

Audit-only review. This pass does not change gameplay scoring, deck construction, authored Blue-Eyes behavior, memory influence, reports outside this audit output, or regression gates.

## Signal Status Table

| Signal | Status | Producer | Consumers | Persistence | Report Locations | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| choke_stop_rate | active | deck/choke_simulator.py: simulate_choke_points() average_stop_rate; exported by deck/side_deck_planner.py and deck/side_plan_optimizer.py | curated opponent memory, regression gates, matchup/post-side/training summaries | training/evaluation run JSON, matchup matrix reports, post-side reports, curated_opponent_memory.json histories | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Directly stored by curated opponent memory; side optimization uses the choke report context rather than this scalar alone. |
| opponent_recovery_rate | active | deck/choke_simulator.py: simulate_choke_points() average_recovery_rate; exported by side-deck reporting layers | curated opponent memory, regression gates, matchup/post-side/training summaries | training/evaluation run JSON, matchup matrix reports, post-side reports, curated_opponent_memory.json histories | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Curated memory keeps a history, but no general learned-card or engine-memory path consumes it. |
| graph_stop_rate | active-telemetry-gated | deck/opponent_graph_simulator.py: simulate_opponent_graph() aggregates route stop scores | regression gates, matchup/post-side/training summaries; graph-derived best interruption nodes feed side planning | training/evaluation run JSON, matchup matrix reports, post-side reports | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | The numeric rate is gated and reported; side optimization is affected by graph interruption recommendations, not by the scalar directly. |
| graph_pivot_rate | active-telemetry-gated | deck/opponent_graph_simulator.py: simulate_opponent_graph() aggregates route pivot scores | regression gates, matchup/post-side/training summaries | training/evaluation run JSON, matchup matrix reports, post-side reports | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | No deck construction, gameplay score, or memory influence was found. |
| probability_weighted_stop_rate | report-only-bypassed | deck/opponent_graph_simulator.py: probability_weighted_metrics() multiplies graph_stop_rate by likely-line access | opponent analysis, matchup matrix, post-side reporting; metric registry names it | matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation | matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Produced, stored, and reported in several paths, but no active consumer was found. |
| opponent_resource_valid_rate | active-telemetry-gated | deck/opponent_graph_simulator.py: simulate_opponent_graph() validates route resource requirements | regression gates, matchup/post-side/training summaries | training/evaluation run JSON, matchup matrix reports, post-side reports | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Gated as a safety signal, but does not alter construction or memory influence. |
| opponent_resource_failure_rate | active | deck/opponent_graph_simulator.py: simulate_opponent_graph() validates route resource failures | deck/side_deck_planner.py choke_candidate_adjustment(), regression gates, matchup/post-side/training summaries | training/evaluation run JSON, matchup matrix reports, post-side reports | train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | The only required scalar found to directly affect side candidate adjustment, via resource-aware interruption tagging. |
| opponent_starter_open_rate | report-only-bypassed | deck/opponent_probability_simulator.py: simulate_opponent_openings(); copied through opponent_graph_simulator.probability_weighted_metrics() | opponent analysis, matchup matrix, post-side reporting; metric registry names it | matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation | matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Produced by Monte Carlo opening estimates and reported, but no active decision consumer was found. |
| opponent_brick_rate | report-only-bypassed | deck/opponent_probability_simulator.py: simulate_opponent_openings(); copied through opponent_graph_simulator.probability_weighted_metrics() | opponent analysis, matchup matrix, post-side reporting; metric registry names it | matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation | matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py | Missing probability data can become indistinguishable from a true zero brick rate in current reporting paths. |

## Influence Map

| Signal | Scoring | Tuning | Side Optimization | Matchup Matrix | Learning Memory | Regression Gates |
| --- | --- | --- | --- | --- | --- | --- |
| choke_stop_rate | no | no | indirect | yes | yes-curated | yes |
| opponent_recovery_rate | no | no | telemetry | yes | yes-curated | yes |
| graph_stop_rate | no | no | indirect | yes | no | yes |
| graph_pivot_rate | no | no | telemetry | yes | no | yes |
| probability_weighted_stop_rate | no | no | no | report-only | no | no |
| opponent_resource_valid_rate | no | no | telemetry | yes | no | yes |
| opponent_resource_failure_rate | no | no | yes | yes | no | yes |
| opponent_starter_open_rate | no | no | no | report-only | no | no |
| opponent_brick_rate | no | no | no | report-only | no | no |

## Classification Summary

- Active: choke_stop_rate, opponent_recovery_rate, opponent_resource_failure_rate.
- Active telemetry/gated: graph_stop_rate, graph_pivot_rate, opponent_resource_valid_rate.
- Report only: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.
- Bypassed in train/evaluate aggregation: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.
- Curated-only memory persistence: choke_stop_rate, opponent_recovery_rate.
- Dead: none among the required signals.

## Discovery Counts

| Signal | Source Occurrences | Representative Files |
| --- | ---: | --- |
| choke_stop_rate | 60 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5T_CHOKE_POINT_SIMULATION.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py |
| opponent_recovery_rate | 46 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5T_CHOKE_POINT_SIMULATION.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py |
| graph_stop_rate | 66 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5X_MONTE_CARLO_OPPONENT_PROBABILITY.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py |
| graph_pivot_rate | 58 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py, analyze_opponent_deck.py |
| probability_weighted_stop_rate | 43 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5X_MONTE_CARLO_OPPONENT_PROBABILITY.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/report_schema.py |
| opponent_resource_valid_rate | 48 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5W_OPPONENT_RESOURCE_VALIDATION.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py |
| opponent_resource_failure_rate | 42 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5W_OPPONENT_RESOURCE_VALIDATION.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, SystemAIYugioh/regression_gates.py |
| opponent_starter_open_rate | 39 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5X_MONTE_CARLO_OPPONENT_PROBABILITY.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, analyze_opponent_deck.py |
| opponent_brick_rate | 40 | OPPONENT_METRIC_CONSOLIDATION.md, OPPONENT_SIGNAL_AUDIT.md, OPPONENT_SIGNAL_SENTINEL_REPORT.md, PHASE5X_MONTE_CARLO_OPPONENT_PROBABILITY.md, SystemAIYugioh/metric_registry.py, SystemAIYugioh/opponent_metric_builder.py, SystemAIYugioh/opponent_signal_sentinel.py, analyze_opponent_deck.py |

## Dead Signal List

- No required signal is completely dead: every required signal is produced and appears in at least one report or validation path.
- Produced, stored, reported, but not consumed by active decision logic: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.
- Gated telemetry without direct scoring/deck/memory influence: graph_pivot_rate and opponent_resource_valid_rate.

## Curated-Only Signal List

- choke_stop_rate: stored in curated_opponent_memory.json histories and side-card choke effectiveness.
- opponent_recovery_rate: stored in curated_opponent_memory.json histories.
- No graph, probability, starter, brick, or resource signal is persisted into curated opponent memory today.

## Produced/Stored/Reported But Never Consumed

- probability_weighted_stop_rate: produced in deck/opponent_graph_simulator.py, exported by side planners, reported by matchup/post-side/opponent analysis paths, and registered in SystemAIYugioh/metric_registry.py; no scoring, tuning, side optimization, memory, or regression-gate consumer was found.
- opponent_starter_open_rate: produced in deck/opponent_probability_simulator.py and reported in opponent analysis, matchup matrix, and post-side summaries; no active decision consumer was found.
- opponent_brick_rate: produced in deck/opponent_probability_simulator.py and reported in opponent analysis, matchup matrix, and post-side summaries; no active decision consumer was found.

## Silent Fallback List

- deck/choke_simulator.py:269-290 empty graph report returns 0.0 for graph/resource/probability signals.
- deck/opponent_probability_simulator.py:72-78 empty probability report returns 0.0 for starter and brick rates.
- deck/opponent_graph_simulator.py:304-310 missing probability estimates use estimates.get(..., 0.0), then probability_weighted_stop_rate becomes graph_stop_rate * 0.0.
- deck/side_deck_planner.py:197 resource failure lookup uses choke_report.get('opponent_resource_failure_rate', 0).
- train_agent.py:117-135 side metric collection falls back to side_report.get(..., 0) for choke/graph/resource metrics.
- evaluate_learning.py:110-128 side metric collection falls back to side_report.get(..., 0) for choke/graph/resource metrics.
- analyze_opponent_deck.py:92-122 report assembly falls back from optimized report to side report, then 0, for all required opponent signals.
- matchup_matrix.py:199-225 matrix cell assembly falls back from post-side report to side report, then 0, for all required opponent signals.
- matchup_matrix.py:373-393 matrix summary averages use float(cell.get(..., 0) or 0), masking missing cells as zeros.
- post_side_evaluator.py:83-107 post-side averages use result.get(..., 0) for all required opponent signals.
- SystemAIYugioh/report_schema.py:46-47 schema helper defaults missing opponent_resource_valid_rate and probability_weighted_stop_rate to 0.
- SystemAIYugioh/regression_gates.py:601-605 _number() converts missing or malformed values to 0.0 before gate comparisons and snapshots.

## Recommended Actions

1. Decide whether probability_weighted_stop_rate, opponent_starter_open_rate, and opponent_brick_rate should remain report-only telemetry or become regression gates.
2. Add a future explicit missing-data sentinel for opponent probability and graph reports so missing data is distinguishable from a true 0.0 measurement.
3. Consider extending train_agent.py and evaluate_learning.py side-metric aggregation to include probability_weighted_stop_rate, opponent_starter_open_rate, and opponent_brick_rate if these are intended to be monitored over training runs.
4. Document that curated opponent memory currently stores only choke_stop_rate and opponent_recovery_rate among the required signals, or deliberately extend curated memory in a later non-audit pass.
5. If opponent_resource_failure_rate remains a side optimization input, add future tests that assert missing resource modeling does not silently trigger a zero-resource-failure interpretation.

## Validation

Run:

```powershell
python validate_stabilization_k.py
```

The validator scans source files, verifies all required opponent signals are discoverable, verifies every influence path is classified, and regenerates this audit report.
