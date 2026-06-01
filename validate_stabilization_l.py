from __future__ import annotations

from pathlib import Path

from matchup_matrix import matrix_summary, summarize_cell
from post_side_evaluator import summarize_results as summarize_post_side_results
from SystemAIYugioh.opponent_signal_sentinel import (
    coalesce_opponent_signal,
    is_opponent_signal_sentinel,
    mean_observed,
    normalize_sentinels_for_legacy_gates,
    opponent_signal_provenance,
    opponent_signal_sentinel,
    sentinel_reason,
)
from SystemAIYugioh.validation_harness import assert_markdown_report_exists, assert_success, in_core_suite, run_checks, run_python, smoke_matchup_matrix


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OPPONENT_SIGNAL_SENTINEL_REPORT.md"


def main() -> None:
    checks = [
        ("sentinels survive aggregation", validate_sentinels_survive_aggregation),
        ("means skip sentinels", validate_means_skip_sentinels),
        ("unsupported opponents are not reported as zero", validate_unsupported_not_zero),
        ("gate normalization preserves legacy numeric behavior", validate_gate_normalization),
        ("sentinel report exists", validate_report_exists),
        ("Stabilization K validator still passes", validate_stabilization_k),
        ("learning audit still passes", validate_learning_audit),
        ("matchup matrix smoke still passes", validate_matchup_matrix_smoke),
    ]
    result = run_checks(
        "validate_stabilization_l",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_l.json",
    )
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization L validation complete.")


def validate_sentinels_survive_aggregation() -> None:
    base = {
        "ok": True,
        "game1_score": 1,
        "post_side_score": 1,
        "post_side_delta": 0,
        "post_side_valid": True,
        "side_cards_used": [],
    }
    rows = [
        {**base, "run": 1, "choke_stop_rate": 0.25, "opponent_signal_provenance": {"inferred": True, "simulated": True}},
        {**base, "run": 2, "choke_stop_rate": opponent_signal_sentinel("not_run"), "opponent_signal_provenance": {"unsupported": True}},
    ]
    post_summary = summarize_post_side_results(rows)
    if post_summary["average_choke_stop_rate"] != 0.25:
        raise AssertionError(post_summary["average_choke_stop_rate"])
    counts = post_summary.get("opponent_signal_sentinel_counts", {})
    if counts.get("choke_stop_rate", {}).get("not_run") != 1:
        raise AssertionError(counts)

    cell = summarize_cell("pure", "validator", "both", [{"ok": True, "run": 1, "final_score": 1, "package_quality": 1, "playable_hand_rate": 1, "brick_rate": 0, "resilience_score": 1, "side_deck_score": 1, "game1_score": 1, "post_side_score": 1, "post_side_delta": 0, "post_side_valid": True, "matchup_coverage_score": 1, "going_first_side_score": 1, "going_second_side_score": 1, "choke_stop_rate": opponent_signal_sentinel("schema_missing"), "main_deck": [], "extra_deck": [], "recommended_side_deck": []}])
    if sentinel_reason(cell.get("choke_stop_rate")) != "unavailable":
        raise AssertionError(cell.get("choke_stop_rate"))


def validate_means_skip_sentinels() -> None:
    value = mean_observed(
        [
            {"graph_stop_rate": 0.0},
            {"graph_stop_rate": opponent_signal_sentinel("unavailable")},
            {"graph_stop_rate": 0.6},
        ],
        "graph_stop_rate",
        4,
    )
    if value != 0.3:
        raise AssertionError(value)


def validate_unsupported_not_zero() -> None:
    provenance = opponent_signal_provenance(None, unsupported=True, sentinel_reason="validator unsupported")
    value = coalesce_opponent_signal("opponent_brick_rate", {}, {}, provenance)
    if not is_opponent_signal_sentinel(value) or sentinel_reason(value) != "unsupported":
        raise AssertionError(value)
    if value == 0:
        raise AssertionError("unsupported opponent collapsed to zero")


def validate_gate_normalization() -> None:
    summary = {"average_choke_stop_rate": opponent_signal_sentinel("unavailable")}
    normalized = normalize_sentinels_for_legacy_gates(summary)
    if normalized.get("average_choke_stop_rate") != 0.0:
        raise AssertionError(normalized)


def validate_report_exists() -> None:
    assert_markdown_report_exists(REPORT_PATH, ("not_run", "unavailable", "unsupported", "schema_missing", "opponent_signal_sentinel_counts"))


def validate_stabilization_k() -> None:
    if in_core_suite():
        return
    assert_success(run_python("validate_stabilization_k.py"))


def validate_learning_audit() -> None:
    assert_success(run_python("learning_signal_audit.py"))


def validate_matchup_matrix_smoke() -> None:
    if in_core_suite():
        return
    assert_success(smoke_matchup_matrix(timeout=1800), ("Failed cells: 0",))


if __name__ == "__main__":
    main()
