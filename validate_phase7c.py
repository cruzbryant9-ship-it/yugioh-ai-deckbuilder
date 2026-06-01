from __future__ import annotations

from pathlib import Path

from SystemAIYugioh.opponent_metric_builder import (
    build_opponent_metric_bundle,
    display_opponent_metric,
    normalize_opponent_metrics_for_gates,
    opponent_gate_normalization_metadata,
    summarize_opponent_metrics,
)
from SystemAIYugioh.opponent_signal_sentinel import normalize_for_gate, opponent_signal_sentinel
from SystemAIYugioh.report_schema import normalize_report
from SystemAIYugioh.validation_harness import (
    assert_json_report_exists,
    assert_markdown_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


PHASE_REPORT = Path("PHASE7C_SCHEMA_SENTINEL_UNIFICATION.md")


def main() -> None:
    checks = [
        ("one canonical normalization path exists", validate_canonical_normalization),
        ("report schema includes opponent metric schema version", validate_report_schema_version),
        ("sentinel counts appear in reports", validate_sentinel_counts),
        ("gate transparency fields exist", validate_gate_transparency),
        ("sentinel CLI display does not print fake zero", validate_cli_display),
        ("legacy gate numeric behavior is unchanged", validate_gate_numeric_compatibility),
        ("Phase 7B validator still passes", validate_phase7b),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
        ("documentation exists", validate_documentation),
    ]
    result = run_checks(
        "validate_phase7c",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase7c.json",
    )
    if not result.passed:
        raise SystemExit(1)
    print("Phase 7C validation complete.")


def validate_canonical_normalization() -> dict[str, object]:
    sentinel_file = Path("SystemAIYugioh") / "opponent_signal_sentinel.py"
    text = sentinel_file.read_text(encoding="utf-8")
    if "def normalize_for_gate" not in text or "def gate_normalization_metadata" not in text:
        raise AssertionError("canonical normalization functions missing")
    builder_text = (Path("SystemAIYugioh") / "opponent_metric_builder.py").read_text(encoding="utf-8")
    if "normalize_for_gate" not in builder_text or "gate_normalization_metadata" not in builder_text:
        raise AssertionError("builder does not delegate to canonical normalization")
    return {"canonical": "SystemAIYugioh/opponent_signal_sentinel.py::normalize_for_gate"}


def validate_report_schema_version() -> dict[str, object]:
    report = normalize_report("validator", {"summary": {}})
    summary = report.get("summary", {})
    if summary.get("opponent_metric_schema_version") != 1 or summary.get("sentinel_policy_version") != 1:
        raise AssertionError(summary)
    bundle = build_opponent_metric_bundle({}, {}, matchup="validator")
    if bundle.get("opponent_metric_schema_version") != 1:
        raise AssertionError(bundle)
    return {"opponent_metric_schema_version": 1, "sentinel_policy_version": 1}


def validate_sentinel_counts() -> dict[str, object]:
    summary = summarize_opponent_metrics(
        [{"graph_stop_rate": opponent_signal_sentinel("schema_missing")}],
        keys=("graph_stop_rate",),
    )
    if summary.get("sentinel_counts", {}).get("graph_stop_rate", {}).get("schema_missing") != 1:
        raise AssertionError(summary)
    for key in ("numeric_observation_counts", "unsupported_counts", "simulated_counts", "curated_counts", "inferred_counts"):
        if key not in summary:
            raise AssertionError(f"missing {key}")
    return {"sentinel_counts": summary["sentinel_counts"]}


def validate_gate_transparency() -> dict[str, object]:
    summary = {"average_graph_stop_rate": opponent_signal_sentinel("unavailable")}
    metadata = opponent_gate_normalization_metadata(summary)
    for key in ("gate_input_was_sentinel", "gate_sentinel_reasons", "gate_numeric_fallback_used"):
        if key not in metadata:
            raise AssertionError(metadata)
    if not metadata["gate_input_was_sentinel"] or not metadata["gate_numeric_fallback_used"]:
        raise AssertionError(metadata)
    return metadata


def validate_cli_display() -> dict[str, object]:
    cases = {
        "not_run": "not run",
        "unsupported": "unsupported",
        "unavailable": "unavailable",
        "schema_missing": "schema missing",
    }
    rendered = {reason: display_opponent_metric(opponent_signal_sentinel(reason)) for reason in cases}
    if rendered != cases:
        raise AssertionError(rendered)
    if "0.0" in rendered.values() or "0" in rendered.values():
        raise AssertionError(rendered)
    return rendered


def validate_gate_numeric_compatibility() -> dict[str, object]:
    payload = {"average_graph_stop_rate": opponent_signal_sentinel("schema_missing")}
    if normalize_for_gate(payload)["average_graph_stop_rate"] != 0.0:
        raise AssertionError(payload)
    if normalize_opponent_metrics_for_gates(payload)["average_graph_stop_rate"] != 0.0:
        raise AssertionError(payload)
    return {"sentinel_gate_value": 0.0}


def validate_phase7b() -> dict[str, object]:
    result = run_python("validate_phase7b.py", timeout=4200)
    assert_success(result)
    return {"duration_seconds": round(result.duration_seconds, 4)}


def validate_core_suite() -> dict[str, object]:
    result = run_python("validate_core_suite.py", timeout=3600)
    assert_success(result)
    return {"duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, object]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"duration_seconds": round(result.duration_seconds, 4)}


def validate_documentation() -> dict[str, object]:
    assert_markdown_report_exists(PHASE_REPORT, ("Schema Changes", "Normalization Path", "Gate Transparency Behavior", "Reports And CLI Examples", "Remaining Risks"))
    payload = assert_json_report_exists(Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase7b.json", ("validator", "passed", "checks"))
    return {"phase_report": PHASE_REPORT.as_posix(), "phase7b_json_passed": payload.get("passed")}


if __name__ == "__main__":
    main()
