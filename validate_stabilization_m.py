from __future__ import annotations

from pathlib import Path

from SystemAIYugioh.opponent_metric_builder import (
    build_opponent_metric_bundle,
    sentinel_coverage_keys,
    summarize_opponent_metrics,
)
from SystemAIYugioh.opponent_signal_sentinel import opponent_signal_sentinel, sentinel_reason
from SystemAIYugioh.validation_harness import assert_markdown_report_exists, assert_success, in_core_suite, run_checks, run_python, smoke_matchup_matrix


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OPPONENT_METRIC_CONSOLIDATION.md"
CONSUMERS = (
    "matchup_matrix.py",
    "train_agent.py",
    "evaluate_learning.py",
    "post_side_evaluator.py",
    "analyze_opponent_deck.py",
)
LEGACY_EXTRACTION_TERMS = (
    "coalesce_opponent_signal",
    "mean_observed",
    "opponent_signal_provenance(",
    "sentinel_counts(",
    "provenance_counts(",
    "numeric_counts(",
    "normalize_sentinels_for_legacy_gates",
)


def main() -> None:
    checks = [
        ("all consumers use the shared builder", validate_consumers_use_builder),
        ("duplicate extraction helpers are absent from consumers", validate_duplicate_helpers_removed),
        ("sentinel coverage is complete", validate_sentinel_coverage),
        ("builder preserves sentinel aggregation", validate_builder_sentinel_aggregation),
        ("existing reports still generate", validate_report_generation),
        ("Stabilization L validator still passes", validate_stabilization_l),
        ("Stabilization K validator still passes", validate_stabilization_k),
        ("matchup matrix smoke still passes", validate_matchup_matrix_smoke),
        ("documentation exists", validate_documentation),
    ]
    result = run_checks(
        "validate_stabilization_m",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_m.json",
    )
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization M validation complete.")


def validate_consumers_use_builder() -> None:
    for filename in CONSUMERS:
        text = (ROOT / filename).read_text(encoding="utf-8")
        if "SystemAIYugioh.opponent_metric_builder" not in text:
            raise AssertionError(f"{filename} does not import opponent_metric_builder")


def validate_duplicate_helpers_removed() -> None:
    for filename in CONSUMERS:
        text = (ROOT / filename).read_text(encoding="utf-8")
        violations = [term for term in LEGACY_EXTRACTION_TERMS if term in text]
        if violations:
            raise AssertionError(f"{filename}: {violations}")


def validate_sentinel_coverage() -> None:
    required = {
        "pivot_risk_score",
        "graph_pivot_rate",
        "opponent_pivot_success_rate",
        "probability_weighted_pivot_rate",
        "backup_line_success_rate",
        "opponent_backup_success_rate",
        "probability_weighted_backup_rate",
        "best_interruption_overlap",
        "poor_interruption_count",
        "timing_precision_score",
        "best_timing_window_count",
        "late_interruption_risk",
        "early_interruption_risk",
        "graph_stop_rate",
        "graph_endboard_reduction_score",
        "graph_best_interruption_count",
        "graph_poor_interruption_count",
        "graph_timing_precision_score",
    }
    covered = set(sentinel_coverage_keys())
    missing = sorted(required - covered)
    if missing:
        raise AssertionError(missing)


def validate_builder_sentinel_aggregation() -> None:
    bundle = build_opponent_metric_bundle({}, {}, matchup="validator")
    if sentinel_reason(bundle.get("graph_pivot_rate")) != "schema_missing":
        raise AssertionError(bundle.get("graph_pivot_rate"))
    summary = summarize_opponent_metrics(
        [
            {"graph_pivot_rate": 0.0, "opponent_signal_provenance": {"inferred": True, "simulated": True}},
            {"graph_pivot_rate": opponent_signal_sentinel("unavailable")},
            {"graph_pivot_rate": 0.8},
        ],
        keys=("graph_pivot_rate",),
    )
    if summary.get("average_graph_pivot_rate") != 0.4:
        raise AssertionError(summary)
    if summary.get("opponent_signal_sentinel_counts", {}).get("graph_pivot_rate", {}).get("unavailable") != 1:
        raise AssertionError(summary)


def validate_report_generation() -> None:
    result = run_python(
        "post_side_evaluator.py",
        "--archetype",
        "Blue-Eyes",
        "--mode",
        "meta",
        "--matchup",
        "combo",
        "--going",
        "both",
        "--runs",
        "1",
        timeout=900,
    )
    assert_success(result)


def validate_stabilization_l() -> None:
    if in_core_suite():
        return
    assert_success(run_python("validate_stabilization_l.py", timeout=2400))


def validate_stabilization_k() -> None:
    if in_core_suite():
        return
    assert_success(run_python("validate_stabilization_k.py"))


def validate_matchup_matrix_smoke() -> None:
    if in_core_suite():
        return
    assert_success(smoke_matchup_matrix(timeout=1800), ("Failed cells: 0",))


def validate_documentation() -> None:
    assert_markdown_report_exists(REPORT_PATH, ("opponent_metric_builder.py", "Metrics Migrated", "Duplicate Code Removed", "Sentinel Coverage Summary"))


if __name__ == "__main__":
    main()
