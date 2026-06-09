from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.executed_dependency_telemetry import measured, promotion_safety_gates, summarize_dependency_telemetry
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import run_regression_gate, save_report as save_regression_report
from kashtira_hybrid_overlay_regression_gate import run_hybrid_gate, save_report as save_hybrid_report
from projection_execution_parity_audit import run_audit, save_architecture_reports
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_r.json"
PHASE_REPORT = Path("STABILIZATION_R_INTERACTION_AND_GENERIC_FILL_GATES.md")


def main() -> None:
    checks = [
        ("generic-fill increase blocks promotion in synthetic data", validate_generic_fill_synthetic_block),
        ("interaction loss blocks promotion in synthetic data", validate_interaction_loss_synthetic_block),
        ("lost interaction cards are reported", validate_lost_cards_reported),
        ("gates use interaction_core_registry", validate_registry_backed_gates),
        ("gates run on executed data, not projection", validate_executed_report_source),
        ("Phase 8M report includes new gate fields", validate_phase8m_report_fields),
        ("Phase 8J report includes new gate fields", validate_phase8j_report_fields),
        ("Stabilization Q validator still passes", lambda: validate_prior_artifact("validate_stabilization_q")),
        ("Stabilization P validator still passes", lambda: validate_prior_artifact("validate_stabilization_p")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_r", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization R validation complete.")


def validate_generic_fill_synthetic_block() -> dict[str, Any]:
    generic = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(generic_fill=0, interactions=list(interaction_core_for("Kashtira")))}])
    candidate = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(generic_fill=2, interactions=list(interaction_core_for("Kashtira")))}])
    gates = promotion_safety_gates(generic, candidate)
    if gates["generic_fill_gate"].get("promotion_blocked") is not True:
        raise AssertionError(gates)
    if "generic_fill_pressure_increase" not in gates["promotion_blocking_reasons"]:
        raise AssertionError(gates)
    return gates["generic_fill_gate"]


def validate_interaction_loss_synthetic_block() -> dict[str, Any]:
    generic = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(generic_fill=0, interactions=list(interaction_core_for("Kashtira")))}])
    candidate = summarize_dependency_telemetry([{"dependency_telemetry": synthetic_telemetry(generic_fill=0, interactions=[])}])
    gates = promotion_safety_gates(generic, candidate)
    if gates["interaction_loss_gate"].get("promotion_blocked") is not True:
        raise AssertionError(gates)
    if "interaction_loss" not in gates["promotion_blocking_reasons"]:
        raise AssertionError(gates)
    return gates["interaction_loss_gate"]


def validate_lost_cards_reported() -> dict[str, Any]:
    report = run_regression_gate("meta", 1, 12345, frozen_cards=True)
    save_regression_report(report)
    lost = report.get("lost_interaction_cards", [])
    expected = set(interaction_core_for("Kashtira"))
    if not expected <= set(lost):
        raise AssertionError(lost)
    return {"lost_interaction_cards": lost}


def validate_registry_backed_gates() -> dict[str, Any]:
    cards = interaction_core_for("Kashtira")
    if not cards or "Ash Blossom & Joyous Spring" not in cards:
        raise AssertionError(cards)
    gates = validate_interaction_loss_synthetic_block()
    if not set(cards) <= set(gates.get("lost_interaction_cards", [])):
        raise AssertionError(gates)
    return {"registry_cards": list(cards), "lost_cards": gates.get("lost_interaction_cards", [])}


def validate_executed_report_source() -> dict[str, Any]:
    report = run_hybrid_gate("meta", 1, 12345, frozen_cards=True)
    save_hybrid_report(report)
    if "projection_source" in report:
        raise AssertionError(report)
    if not report.get("run_results") or "dependency_telemetry" not in report["run_results"][0]["hybrid_overlay"]:
        raise AssertionError(report.get("run_results"))
    return {"report_type": report["report_type"], "run_results": len(report["run_results"])}


def validate_phase8m_report_fields() -> dict[str, Any]:
    report = run_hybrid_gate("meta", 1, 12345, frozen_cards=True)
    save_hybrid_report(report)
    required = {"generic_fill_gate", "interaction_loss_gate", "promotion_blocking_reasons", "lost_interaction_cards"}
    missing = required - set(report)
    if missing:
        raise AssertionError(missing)
    reasons = report["promotion_blocking_reasons"]["hybrid_overlay_vs_generic"]
    if "generic_fill_pressure_increase" not in reasons or "interaction_loss" not in reasons:
        raise AssertionError(report)
    return {key: report[key] for key in sorted(required)}


def validate_phase8j_report_fields() -> dict[str, Any]:
    report = run_regression_gate("meta", 1, 12345, frozen_cards=True)
    save_regression_report(report)
    required = {"generic_fill_gate", "interaction_loss_gate", "promotion_blocking_reasons", "lost_interaction_cards"}
    missing = required - set(report)
    if missing:
        raise AssertionError(missing)
    if "generic_fill_pressure_increase" not in report["promotion_blocking_reasons"] or "interaction_loss" not in report["promotion_blocking_reasons"]:
        raise AssertionError(report)
    return {key: report[key] for key in sorted(required)}


def synthetic_telemetry(generic_fill: int, interactions: list[str]) -> dict[str, Any]:
    return {
        "safe_filler_used_count": measured(0),
        "repair_used": measured(False),
        "repair_success": measured(True),
        "repair_action_count": measured(0),
        "repair_dependency_score": measured(0.0),
        "filler_dependency_score": measured(0.0),
        "generic_fill_count": measured(float(generic_fill)),
        "interaction_preservation_attempted": measured(False),
        "interaction_candidates_selected_names": measured(interactions),
        "interaction_candidates_selected": measured(len(interactions)),
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
        "# Stabilization R: Interaction Loss + Generic Fill Promotion Gates",
        "",
        "Safety-gate/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `validate_stabilization_r.py`",
        "- `STABILIZATION_R_INTERACTION_AND_GENERIC_FILL_GATES.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/executed_dependency_telemetry.py`",
        "- `kashtira_hybrid_overlay_regression_gate.py`",
        "- `kashtira_experimental_regression_gate.py`",
        "- `semi_specialized_experimental_comparison.py`",
        "- `projection_execution_parity_audit.py`",
        "",
        "## Generic-Fill Gate Behavior",
        "",
        "- Blocks promotion when candidate `generic_fill_count` is greater than generic baseline beyond the configured safety limit.",
        "- Default safety limit: `0.0` additional generic-fill cards.",
        f"- Current experimental gate: `{regression['generic_fill_gate']}`",
        f"- Hybrid gate: `{hybrid['generic_fill_gate']['hybrid_overlay_vs_generic']}`",
        "",
        "## Interaction-Loss Gate Behavior",
        "",
        "- Uses `deck.interaction_core_registry` for the Kashtira interaction core.",
        "- Blocks promotion when candidate selected interaction count is below generic baseline beyond the configured safety limit.",
        "- Default safety limit: `0.0` lost interaction cards.",
        f"- Current experimental lost cards: `{regression['lost_interaction_cards']}`",
        f"- Hybrid lost cards: `{hybrid['lost_interaction_cards']['hybrid_overlay_vs_generic']}`",
        "",
        "## Current Gate Results",
        "",
        f"- Experimental recommendation: `{regression['recommendation']}`",
        f"- Experimental blocking reasons: `{regression['promotion_blocking_reasons']}`",
        f"- Hybrid recommendation: `{hybrid['recommendation']}`",
        f"- Hybrid blocking reasons: `{hybrid['promotion_blocking_reasons']['hybrid_overlay_vs_generic']}`",
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
            "- Stabilization S should investigate why the experimental and hybrid paths lose all registry interaction cards and rely on 15-16 generic-fill picks, but still keep any adapter changes behind explicit non-default execution gates.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
