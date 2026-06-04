from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.semi_specialized_role_reconciliation import reconcile_specialization_roles
from semi_specialization_role_reconciliation_report import build_report, save_report
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8G_KASHTIRA_ROLE_RECONCILIATION.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8g.json"
RECONCILIATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_role_reconciliation_report.json"
RECONCILIATION_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_role_reconciliation_report.md"


def main() -> None:
    checks = [
        ("reconciliation module runs", validate_reconciliation_runs),
        ("report runner generates JSON/Markdown", validate_report_runner),
        ("proposed updates are marked not_activated/proposed_only", validate_proposed_only),
        ("Riseheart conflict is addressed", validate_riseheart_addressed),
        ("active profile is not changed", validate_active_profile_unchanged),
        ("Phase 8F validator still passes", validate_phase8f),
        ("Phase 8E validator still passes", validate_phase8e),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8g", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8G validation complete.")


def validate_reconciliation_runs() -> dict[str, Any]:
    reconciliation = reconcile_specialization_roles("Kashtira", "meta")
    if "proposed_role_updates" not in reconciliation:
        raise AssertionError(reconciliation)
    if reconciliation.get("expected_audit_score_after_reconciliation", 0) <= reconciliation.get("current_audit_score", 0):
        raise AssertionError(reconciliation)
    return {
        "current_score": reconciliation["current_audit_score"],
        "projected_score": reconciliation["expected_audit_score_after_reconciliation"],
        "conflicts_resolved": reconciliation["conflicts_resolved"],
    }


def validate_report_runner() -> dict[str, Any]:
    report = build_report("Kashtira", "meta")
    save_report(report)
    assert_json_report_exists(RECONCILIATION_JSON, ("reconciliation", "semi_specialization_activated"))
    assert_markdown_report_exists(RECONCILIATION_MD, ("Proposed Role Updates", "Dual-Role Assignments", "Projected audit score"))
    return {"projected_score": report["reconciliation"]["expected_audit_score_after_reconciliation"]}


def validate_proposed_only() -> dict[str, Any]:
    reconciliation = reconcile_specialization_roles("Kashtira", "meta")
    if reconciliation.get("not_activated") is not True or reconciliation.get("proposed_only") is not True:
        raise AssertionError(reconciliation)
    for card, update in reconciliation.get("proposed_role_updates", {}).items():
        if update.get("not_activated") is not True or update.get("proposed_only") is not True:
            raise AssertionError({"card": card, "update": update})
    return {"not_activated": reconciliation["not_activated"], "proposed_only": reconciliation["proposed_only"]}


def validate_riseheart_addressed() -> dict[str, Any]:
    reconciliation = reconcile_specialization_roles("Kashtira", "meta")
    riseheart_update = reconciliation.get("proposed_role_updates", {}).get("Kashtira Riseheart")
    if not riseheart_update:
        raise AssertionError(reconciliation)
    to_roles = set(riseheart_update.get("to", []))
    if "extenders" not in to_roles or "payoff_bridge" not in to_roles:
        raise AssertionError(riseheart_update)
    unresolved = [
        row for row in reconciliation.get("unresolved_conflicts", [])
        if row.get("card") == "Kashtira Riseheart" and row.get("profile_role") == "payoffs"
    ]
    if unresolved:
        raise AssertionError(unresolved)
    return {"riseheart_to": sorted(to_roles), "remaining_conflicts": len(reconciliation.get("unresolved_conflicts", []))}


def validate_active_profile_unchanged() -> dict[str, Any]:
    before = load_specialization_profile("Kashtira")
    reconciliation = reconcile_specialization_roles("Kashtira", "meta")
    after = load_specialization_profile("Kashtira")
    if before != after:
        raise AssertionError({"before": before, "after": after})
    if "Kashtira Riseheart" not in (after or {}).get("payoffs", []):
        raise AssertionError({"reason": "active profile was edited instead of projected", "reconciliation": reconciliation})
    return {"active_profile_preserved": True, "riseheart_still_active_payoff": True}


def validate_phase8f() -> dict[str, Any]:
    result = run_python("validate_phase8f.py", timeout=9000)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


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
    reconciliation = report["reconciliation"]
    lines = [
        "# Phase 8G: Kashtira Role Map Reconciliation",
        "",
        "Reconciliation/reporting only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, duel engine features, or full combo graphs were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_role_reconciliation.py`",
        "- `semi_specialization_role_reconciliation_report.py`",
        "- `validate_phase8g.py`",
        "- `PHASE8G_KASHTIRA_ROLE_RECONCILIATION.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Reconciliation Summary",
        "",
        f"- Current audit score: {reconciliation.get('current_audit_score')}",
        f"- Projected audit score: {reconciliation.get('expected_audit_score_after_reconciliation')}",
        f"- Readiness before: `{reconciliation.get('readiness_before')}`",
        f"- Projected readiness after: `{reconciliation.get('projected_readiness_after')}`",
        f"- Conflicts resolved: {reconciliation.get('conflicts_resolved')}",
        f"- Unresolved conflicts: {reconciliation.get('projected_conflict_count')}",
        f"- Proposed only: {reconciliation.get('proposed_only')}",
        f"- Not activated: {reconciliation.get('not_activated')}",
        "",
        "## Proposed Role Updates",
        "",
    ]
    for card, update in reconciliation.get("proposed_role_updates", {}).items():
        lines.append(f"- `{card}`: {', '.join(update.get('from', []))} -> {', '.join(update.get('to', []))}; {update.get('recommendation')}")
    if not reconciliation.get("proposed_role_updates"):
        lines.append("- None")
    lines.extend(["", "## Riseheart Recommendation", ""])
    riseheart = reconciliation.get("proposed_role_updates", {}).get("Kashtira Riseheart", {})
    if riseheart:
        lines.append(f"- `{', '.join(riseheart.get('to', []))}`: {riseheart.get('recommendation')}")
    else:
        lines.append("- No Riseheart update proposed")
    lines.extend(["", "## Unresolved Conflicts", ""])
    if reconciliation.get("unresolved_conflicts"):
        for row in reconciliation["unresolved_conflicts"]:
            lines.append(f"- `{row.get('card', 'unknown')}` as `{row.get('profile_role', 'unknown')}` [{row.get('severity', 'unknown')}]: {row.get('reason')}")
    else:
        lines.append("- None")
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
            "## Recommended Phase 8H",
            "",
            "- Add a non-activated experimental comparison harness that can replay generic Kashtira builds against the reconciled role map without changing defaults.",
            "- Require projected role safety, quota sensitivity stability, and generic-vs-proposed regression reports before any builder flag activation.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
