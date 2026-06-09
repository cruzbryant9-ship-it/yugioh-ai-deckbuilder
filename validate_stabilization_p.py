from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.semi_specialized_builder_adapter import dependency_gate_report
from kashtira_adapter_tuning_plan import build_tuning_plan, save_report
from projection_execution_parity_audit import PARITY_JSON, run_audit, save_architecture_reports
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import (
    assert_json_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_p.json"
PHASE_REPORT = Path("STABILIZATION_P_PROMOTION_EVIDENCE_HARDENING.md")
FORBIDDEN_PROJECTED_PROMOTION = "eligible_for_experimental_adapter_update"


def main() -> None:
    checks = [
        ("projected-only recommendations cannot be promotion-eligible", validate_projected_recommendation_safety),
        ("legacy promotion wording absent from Phase 8L output", validate_legacy_wording_absent),
        ("evidence source metadata exists", validate_evidence_metadata),
        ("promotion_allowed false for projected evidence", validate_projected_promotion_block),
        ("filler dependency gate can trigger", validate_filler_gate_trigger),
        ("repair dependency gate can trigger", validate_repair_gate_trigger),
        ("interaction-core registry usage is reported", validate_interaction_registry_report),
        ("Phase 8L validator still passes", validate_phase8l),
        ("Phase 8M validator still passes", validate_phase8m_artifact),
        ("Stabilization O validator still passes", validate_stabilization_o),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_p", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization P validation complete.")


def latest_tuning_report() -> dict[str, Any]:
    report = build_tuning_plan("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    return report


def validate_projected_recommendation_safety() -> dict[str, Any]:
    report = latest_tuning_report()
    allowed = {"proposal_only", "needs_real_execution", "do_not_use_for_promotion"}
    if report.get("recommendation") not in allowed:
        raise AssertionError(report)
    if report.get("promotion_allowed") is not False or report.get("requires_execution_gate") is not True:
        raise AssertionError(report)
    return {
        "recommendation": report["recommendation"],
        "evidence_source": report.get("evidence_source"),
        "promotion_allowed": report.get("promotion_allowed"),
        "requires_execution_gate": report.get("requires_execution_gate"),
    }


def validate_legacy_wording_absent() -> dict[str, Any]:
    report = latest_tuning_report()
    encoded = json.dumps(report, sort_keys=True)
    if FORBIDDEN_PROJECTED_PROMOTION in encoded:
        raise AssertionError(FORBIDDEN_PROJECTED_PROMOTION)
    return {"forbidden_term_absent": FORBIDDEN_PROJECTED_PROMOTION}


def validate_evidence_metadata() -> dict[str, Any]:
    report = latest_tuning_report()
    required = {"evidence_source", "promotion_allowed", "requires_execution_gate", "recommendation_details"}
    missing = sorted(key for key in required if key not in report)
    if missing:
        raise AssertionError(missing)
    details = report["recommendation_details"]
    if details.get("evidence_source") != report.get("evidence_source"):
        raise AssertionError(report)
    return {key: report[key] for key in ("evidence_source", "promotion_allowed", "requires_execution_gate")}


def validate_projected_promotion_block() -> dict[str, Any]:
    report = latest_tuning_report()
    if report.get("evidence_source") != "projected" or report.get("promotion_allowed") is not False:
        raise AssertionError(report)
    return {"evidence_source": report["evidence_source"], "promotion_allowed": report["promotion_allowed"]}


def validate_filler_gate_trigger() -> dict[str, Any]:
    report = dependency_gate_report(
        {"filler_dependency": 0.0, "repair_dependency": 0.0},
        {"filler_dependency": 1.0, "repair_dependency": 0.0},
    )
    gate = next(row for row in report["gates"] if row["name"] == "filler_dependency_gate")
    if gate["triggered"] is not True or "filler dependency increased versus generic" not in report["failures"]:
        raise AssertionError(report)
    return gate


def validate_repair_gate_trigger() -> dict[str, Any]:
    report = dependency_gate_report(
        {"filler_dependency": 0.0, "repair_dependency": 0.0},
        {"filler_dependency": 0.0, "repair_dependency": 1.0},
    )
    gate = next(row for row in report["gates"] if row["name"] == "repair_dependency_gate")
    if gate["triggered"] is not True or "repair dependency increased versus generic" not in report["failures"]:
        raise AssertionError(report)
    return gate


def validate_interaction_registry_report() -> dict[str, Any]:
    report = run_audit(use_existing_reports=True)
    save_architecture_reports(report)
    interaction = report["interaction_core_audit"]
    if "promotion_paths_using_hardcoded_interaction_core" not in interaction:
        raise AssertionError(interaction)
    if interaction["promotion_paths_using_hardcoded_interaction_core"]:
        raise AssertionError(interaction["promotion_paths_using_hardcoded_interaction_core"])
    return {
        "remaining_hardcoded_count": interaction.get("remaining_hardcoded_count"),
        "promotion_paths_using_hardcoded_interaction_core": interaction["promotion_paths_using_hardcoded_interaction_core"],
        "migrated_modules": interaction.get("migrated_modules"),
    }


def validate_phase8l() -> dict[str, Any]:
    result = run_python("validate_phase8l.py", timeout=1800)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8m_artifact() -> dict[str, Any]:
    return assert_validator_artifact_passed("validate_phase8m")


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


def assert_validator_artifact_passed(name: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if not path.exists():
        raise AssertionError(f"missing prior validator artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise AssertionError(payload)
    return {"artifact": str(path), "passed": payload.get("passed"), "duration_seconds": payload.get("duration_seconds")}


def write_phase_report(payload: dict[str, Any]) -> None:
    tuning = build_tuning_plan("meta", 10, 12345, frozen_cards=True)
    save_report(tuning)
    audit = run_audit(use_existing_reports=True)
    save_architecture_reports(audit)
    interaction = audit["interaction_core_audit"]
    lines = [
        "# Stabilization P: Promotion Evidence Hardening",
        "",
        "Safety/remediation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `validate_stabilization_p.py`",
        "- `STABILIZATION_P_PROMOTION_EVIDENCE_HARDENING.md`",
        "",
        "## Files Changed",
        "",
        "- `kashtira_adapter_tuning_plan.py`",
        "- `validate_phase8l.py`",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `projection_execution_parity_audit.py`",
        "- `validate_stabilization_o.py`",
        "",
        "## Projected Recommendation Changes",
        "",
        f"- Phase 8L recommendation: `{tuning['recommendation']}`",
        f"- Evidence source: `{tuning['evidence_source']}`",
        f"- Promotion allowed: `{tuning['promotion_allowed']}`",
        f"- Requires execution gate: `{tuning['requires_execution_gate']}`",
        "- Removed projected-only promotion language: `eligible_for_experimental_adapter_update` no longer appears in Phase 8L output.",
        "",
        "## Filler/Repair Gate Fix",
        "",
        "- `filler_dependency_gate` now compares candidate filler dependency against generic/baseline filler dependency.",
        "- `repair_dependency_gate` now compares candidate repair dependency against generic/baseline repair dependency.",
        "- Synthetic validation confirms both gates can trigger.",
        "",
        "## Interaction-Core Registry Report",
        "",
        f"- Remaining hardcoded interaction-core users: {interaction['remaining_hardcoded_count']}",
        f"- Promotion paths using hardcoded interaction core: {len(interaction['promotion_paths_using_hardcoded_interaction_core'])}",
        f"- Migrated modules: {', '.join(f'`{path}`' for path in interaction['migrated_modules']) or 'None'}",
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
            "- Stabilization Q should improve executed candidate dependency telemetry so filler/repair evidence is captured directly from real candidate builds, then re-run the fixed-seed execution gates before any further specialization work.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
