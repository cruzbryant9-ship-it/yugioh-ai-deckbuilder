from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.semi_specialized_role_audit import audit_profile_roles, audit_specialized_roles
from semi_specialization_role_audit_report import build_report, save_report
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8F_KASHTIRA_ROLE_AUDIT.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8f.json"
ROLE_AUDIT_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_role_audit_report.json"
ROLE_AUDIT_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_role_audit_report.md"


def main() -> None:
    checks = [
        ("role audit runs", validate_role_audit_runs),
        ("report runner generates JSON/Markdown", validate_report_runner),
        ("not_activated remains true", validate_not_activated),
        ("conflicts are detected in synthetic cases", validate_synthetic_conflicts),
        ("Kashtira profile receives a classification", validate_kashtira_classification),
        ("Phase 8E validator still passes", validate_phase8e),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8f", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8F validation complete.")


def validate_role_audit_runs() -> dict[str, Any]:
    audit = audit_specialized_roles("Kashtira", "meta")
    if "role_agreement_score" not in audit or "readiness_classification" not in audit:
        raise AssertionError(audit)
    return {
        "role_agreement_score": audit["role_agreement_score"],
        "readiness_classification": audit["readiness_classification"],
        "conflicts": len(audit.get("role_conflicts", [])),
    }


def validate_report_runner() -> dict[str, Any]:
    report = build_report("Kashtira", "meta")
    save_report(report)
    assert_json_report_exists(ROLE_AUDIT_JSON, ("audit", "semi_specialization_activated"))
    assert_markdown_report_exists(ROLE_AUDIT_MD, ("Role agreement score", "Readiness classification", "Role Conflicts"))
    return {"role_agreement_score": report["audit"]["role_agreement_score"]}


def validate_not_activated() -> dict[str, Any]:
    report = build_report("Kashtira", "meta")
    if report.get("semi_specialization_activated") is not False:
        raise AssertionError(report)
    if report.get("audit", {}).get("not_activated") is not True:
        raise AssertionError(report)
    return {"not_activated": report["audit"]["not_activated"], "report_activated": report["semi_specialization_activated"]}


def validate_synthetic_conflicts() -> dict[str, Any]:
    profile = {
        "archetype": "Kashtira",
        "payoffs": ["Kashtira Test Extender"],
        "interruptions": ["Kashtira Test Blank Trap"],
        "extra_deck_preferences": ["Kashtira Test Main Deck Monster"],
        "known_risk_flags": [],
    }
    cards = [
        {
            "name": "Kashtira Test Extender",
            "type": "Effect Monster",
            "archetype": "Kashtira",
            "level": 4,
            "desc": "You can Special Summon this card from your hand.",
        },
        {
            "name": "Kashtira Test Blank Trap",
            "type": "Trap Card",
            "archetype": "Kashtira",
            "desc": "Draw 1 card.",
        },
        {
            "name": "Kashtira Test Main Deck Monster",
            "type": "Effect Monster",
            "archetype": "Kashtira",
            "level": 4,
            "desc": "This card gains 100 ATK.",
        },
    ]
    audit = audit_profile_roles(profile, cards, "Kashtira", "meta")
    reasons = {row.get("reason") for row in audit.get("role_conflicts", [])}
    expected = {
        "profile payoff but generic inference sees extender",
        "profile interruption but no interruption signal exists",
        "Extra Deck payoff tag is unsupported by card metadata",
    }
    if not expected.issubset(reasons):
        raise AssertionError({"expected": sorted(expected), "reasons": sorted(reasons)})
    return {"detected_reasons": sorted(reasons), "classification": audit["readiness_classification"]}


def validate_kashtira_classification() -> dict[str, Any]:
    audit = audit_specialized_roles("Kashtira", "meta")
    allowed = {"role_safe", "role_safe_with_warnings", "role_unstable"}
    if audit.get("readiness_classification") not in allowed:
        raise AssertionError(audit)
    return {
        "classification": audit["readiness_classification"],
        "role_agreement_score": audit["role_agreement_score"],
        "confirmed_role_count": sum(len(names) for names in audit.get("confirmed_roles", {}).values()),
    }


def validate_phase8e() -> dict[str, Any]:
    result = run_python("validate_phase8e.py", timeout=9000)
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
    report = build_report("Kashtira", "meta")
    save_report(report)
    audit = report["audit"]
    lines = [
        "# Phase 8F: Kashtira Role Classification Audit",
        "",
        "Audit/report-only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_role_audit.py`",
        "- `semi_specialization_role_audit_report.py`",
        "- `validate_phase8f.py`",
        "- `PHASE8F_KASHTIRA_ROLE_AUDIT.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_quota_replay.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Audit Summary",
        "",
        f"- Role agreement score: {audit['role_agreement_score']}",
        f"- Readiness classification: `{audit['readiness_classification']}`",
        f"- Not activated: {audit['not_activated']}",
        "",
        "## Confirmed Roles",
        "",
    ]
    for role, names in audit.get("confirmed_roles", {}).items():
        lines.append(f"- `{role}`: {', '.join(names)}")
    if not audit.get("confirmed_roles"):
        lines.append("- None")
    lines.extend(["", "## Conflicts", ""])
    if audit.get("role_conflicts"):
        for row in audit["role_conflicts"]:
            lines.append(f"- `{row.get('card')}` as `{row.get('profile_role')}` [{row.get('severity')}]: {row.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Low-Confidence Assignments", ""])
    if audit.get("low_confidence_assignments"):
        for row in audit["low_confidence_assignments"]:
            lines.append(f"- `{row.get('card')}` as `{row.get('profile_role')}`: {row.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in audit.get("risk_flags", [])) if audit.get("risk_flags") else lines.append("- None")
    lines.extend(
        [
            "",
            "## Validation Results",
            "",
            f"- Passed: {payload.get('passed')}",
            f"- Duration seconds: {payload.get('duration_seconds')}",
        ]
    )
    for check in payload.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Phase 8G",
            "",
            "- Add a non-activated experimental flag design that can compare generic Kashtira builds against audited quota and role assumptions without changing defaults.",
            "- Require role-audit readiness, quota-sensitivity stability, and generic-vs-experimental regression reports before any default activation.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
