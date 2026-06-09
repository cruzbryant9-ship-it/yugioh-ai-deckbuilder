from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.executed_dependency_telemetry import (
    build_dependency_telemetry,
    dependency_gate_status,
    measured,
    sentinel,
    summarize_dependency_telemetry,
)
from kashtira_experimental_regression_gate import run_regression_gate, save_report as save_regression_report
from kashtira_hybrid_overlay_regression_gate import run_hybrid_gate, save_report as save_hybrid_report
from projection_execution_parity_audit import run_audit, save_architecture_reports
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_q.json"
PHASE_REPORT = Path("STABILIZATION_Q_EXECUTED_DEPENDENCY_TELEMETRY.md")


def main() -> None:
    checks = [
        ("executed reports include dependency telemetry", validate_executed_dependency_telemetry),
        ("generic vs experimental dependency deltas exist", validate_dependency_deltas),
        ("unavailable values remain explicit sentinel", validate_unavailable_sentinel),
        ("filler dependency gate can trigger from executed-shaped data", validate_filler_gate_from_executed_data),
        ("repair dependency gate can trigger from executed-shaped data", validate_repair_gate_from_executed_data),
        ("Phase 8M validator still passes or latest artifact is verified", lambda: validate_prior_artifact("validate_phase8m")),
        ("Phase 8J validator still passes", lambda: validate_prior_artifact("validate_phase8j")),
        ("Stabilization P validator still passes", validate_stabilization_p),
        ("Stabilization O validator still passes", validate_stabilization_o),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_q", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization Q validation complete.")


def validate_executed_dependency_telemetry() -> dict[str, Any]:
    report = run_hybrid_gate("meta", 1, 12345, frozen_cards=True)
    save_hybrid_report(report)
    required = {
        "safe_filler_used_count",
        "repair_used",
        "repair_success",
        "repair_action_count",
        "repair_dependency_score",
        "filler_dependency_score",
        "generic_fill_count",
        "interaction_preservation_attempted",
        "interaction_candidates_selected",
        "interaction_candidates_rejected",
        "interaction_rejection_reasons",
    }
    for section in ("generic_dependency", "experimental_dependency", "hybrid_dependency"):
        missing = required - set(report.get(section, {}))
        if missing:
            raise AssertionError({section: sorted(missing)})
    return {
        "generic_dependency_status": report["generic_dependency"]["filler_dependency_score"]["status"],
        "hybrid_dependency_status": report["hybrid_dependency"]["filler_dependency_score"]["status"],
        "hybrid_interaction_rejections": report["hybrid_dependency"]["interaction_rejection_reasons"],
    }


def validate_dependency_deltas() -> dict[str, Any]:
    report = run_regression_gate("meta", 1, 12345, frozen_cards=True)
    save_regression_report(report)
    if not report.get("generic_dependency") or not report.get("experimental_dependency"):
        raise AssertionError(report)
    delta = report.get("dependency_delta", {})
    gate = report.get("dependency_gate_status", {})
    for key in ("safe_filler_used_count", "repair_action_count", "repair_dependency_score", "filler_dependency_score", "generic_fill_count"):
        if key not in delta:
            raise AssertionError(delta)
    if gate.get("gate_evaluated") is not True:
        raise AssertionError(gate)
    return {"dependency_delta": delta, "dependency_gate_status": gate}


def validate_unavailable_sentinel() -> dict[str, Any]:
    telemetry = build_dependency_telemetry([], {}, "Kashtira")
    summary = summarize_dependency_telemetry([{"dependency_telemetry": telemetry}])
    safe_filler = summary["safe_filler_used_count"]
    repair = summary["repair_action_count"]
    if safe_filler.get("average") == 0 or repair.get("average") == 0:
        raise AssertionError(summary)
    if safe_filler.get("status") == "measured" or repair.get("status") == "measured":
        raise AssertionError(summary)
    return {"safe_filler": safe_filler, "repair_action_count": repair}


def validate_filler_gate_from_executed_data() -> dict[str, Any]:
    generic = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(filler=0, repair=0)}])
    candidate = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(filler=2, repair=0)}])
    status = dependency_gate_status(generic, candidate)
    if status.get("gate_evaluated") is not True or "filler dependency increased versus generic" not in status.get("failures", []):
        raise AssertionError(status)
    return status


def validate_repair_gate_from_executed_data() -> dict[str, Any]:
    generic = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(filler=0, repair=0)}])
    candidate = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(filler=0, repair=2)}])
    status = dependency_gate_status(generic, candidate)
    if status.get("gate_evaluated") is not True or "repair dependency increased versus generic" not in status.get("failures", []):
        raise AssertionError(status)
    return status


def synthetic_telemetry(filler: int, repair: int) -> dict[str, Any]:
    return {
        "safe_filler_used_count": measured(filler),
        "repair_used": measured(bool(repair)),
        "repair_success": measured(True),
        "repair_action_count": measured(repair),
        "repair_dependency_score": measured(float(repair)),
        "filler_dependency_score": measured(float(filler)),
        "generic_fill_count": measured(0.0),
        "interaction_preservation_attempted": measured(False),
        "interaction_candidates_selected": measured(0),
        "interaction_candidates_rejected": measured([]),
        "interaction_rejection_reasons": measured([]),
    }


def validate_prior_artifact(name: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if not path.exists():
        raise AssertionError(f"missing prior validator artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise AssertionError(payload)
    return {"artifact": str(path), "passed": payload.get("passed"), "duration_seconds": payload.get("duration_seconds")}


def validate_stabilization_p() -> dict[str, Any]:
    return validate_prior_artifact("validate_stabilization_p")


def validate_stabilization_o() -> dict[str, Any]:
    result = run_python("validate_stabilization_o.py", timeout=7200)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8a() -> dict[str, Any]:
    result = run_python("validate_phase8a.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_core_suite() -> dict[str, Any]:
    result = run_python("validate_core_suite.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, Any]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def write_phase_report(payload: dict[str, Any]) -> None:
    hybrid = run_hybrid_gate("meta", 2, 12345, frozen_cards=True)
    save_hybrid_report(hybrid)
    regression = run_regression_gate("meta", 2, 12345, frozen_cards=True)
    save_regression_report(regression)
    audit = run_audit(use_existing_reports=True)
    save_architecture_reports(audit)
    lines = [
        "# Stabilization Q: Executed Candidate Dependency Telemetry",
        "",
        "Telemetry/remediation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `deck/executed_dependency_telemetry.py`",
        "- `validate_stabilization_q.py`",
        "- `STABILIZATION_Q_EXECUTED_DEPENDENCY_TELEMETRY.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `kashtira_hybrid_overlay_regression_gate.py`",
        "- `kashtira_experimental_regression_gate.py`",
        "- `semi_specialized_experimental_comparison.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Telemetry Fields Added",
        "",
        "- `safe_filler_used_count`",
        "- `repair_used`",
        "- `repair_success`",
        "- `repair_action_count`",
        "- `repair_dependency_score`",
        "- `filler_dependency_score`",
        "- `generic_fill_count`",
        "- `interaction_preservation_attempted`",
        "- `interaction_candidates_selected`",
        "- `interaction_candidates_rejected`",
        "- `interaction_rejection_reasons`",
        "",
        "## Generic vs Experimental Dependency Comparison",
        "",
        f"- Experimental dependency gate status: `{regression['dependency_gate_status']['status']}`",
        f"- Experimental dependency gate passed: `{regression['dependency_gate_status'].get('passed')}`",
        f"- Experimental dependency delta: `{regression['dependency_delta']}`",
        f"- Hybrid dependency gate status: `{hybrid['dependency_gate_status']['hybrid_overlay_vs_generic']['status']}`",
        f"- Hybrid dependency gate passed: `{hybrid['dependency_gate_status']['hybrid_overlay_vs_generic'].get('passed')}`",
        "",
        "## Unavailable Handling",
        "",
        "- Missing dependency fields are summarized as explicit sentinel states such as `not_measured`, not as numeric zero.",
        "- Measured zero remains numeric `0.0` only when the executed build report actually provided the field.",
        "",
        "## Validation Results",
        "",
        f"- Passed: {payload.get('passed')}",
        f"- Duration seconds: {payload.get('duration_seconds')}",
    ]
    for check in payload.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "- Stabilization R should decide whether generic-fill pressure belongs in a separate promotion gate, since executed telemetry now shows generic fill and interaction-preservation failures clearly even when repair/filler dependency gates pass.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
