from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_reconciled_comparison import compare_reconciled_profile
from semi_specialization_reconciled_comparison_report import build_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8H_RECONCILED_KASHTIRA_COMPARISON.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8h.json"
COMPARISON_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_reconciled_comparison_report.json"
COMPARISON_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_reconciled_comparison_report.md"


def main() -> None:
    checks = [
        ("comparison module runs", validate_comparison_runs),
        ("report runner generates JSON/Markdown", validate_report_runner),
        ("not_activated remains true", validate_not_activated),
        ("active profile remains unchanged", validate_active_profile_unchanged),
        ("generic builder still works", validate_generic_builder),
        ("Blue-Eyes authored behavior remains untouched", validate_blue_eyes_authored),
        ("activation recommendation obeys safety gates", validate_activation_gates),
        ("Phase 8G validator still passes", validate_phase8g),
        ("Phase 8F validator still passes", validate_phase8f),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8h", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8H validation complete.")


def validate_comparison_runs() -> dict[str, Any]:
    comparison = compare_reconciled_profile("Kashtira", "meta", 2)
    for key in ("generic_summary", "active_profile_summary", "reconciled_profile_summary"):
        if key not in comparison:
            raise AssertionError(comparison)
    return {
        "activation_recommendation": comparison["activation_recommendation"],
        "generic_gap": comparison["generic_summary"].get("generic_total_gap"),
        "reconciled_gap": comparison["reconciled_profile_summary"].get("quota_gap"),
    }


def validate_report_runner() -> dict[str, Any]:
    report = build_report("Kashtira", "meta", 3)
    save_report(report)
    assert_json_report_exists(COMPARISON_JSON, ("comparison", "semi_specialization_activated"))
    assert_markdown_report_exists(COMPARISON_MD, ("Generic Summary", "Active Profile Summary", "Reconciled Profile Summary", "Activation Safety Gates"))
    return {"activation_recommendation": report["comparison"]["activation_recommendation"]}


def validate_not_activated() -> dict[str, Any]:
    report = build_report("Kashtira", "meta", 1)
    comparison = report["comparison"]
    if report.get("semi_specialization_activated") is not False or comparison.get("not_activated") is not True:
        raise AssertionError(report)
    if comparison.get("reconciled_profile_summary", {}).get("not_activated") is not True:
        raise AssertionError(comparison)
    return {"not_activated": comparison["not_activated"], "report_activated": report["semi_specialization_activated"]}


def validate_active_profile_unchanged() -> dict[str, Any]:
    before = load_specialization_profile("Kashtira")
    compare_reconciled_profile("Kashtira", "meta", 1)
    after = load_specialization_profile("Kashtira")
    if before != after:
        raise AssertionError({"before": before, "after": after})
    if "Kashtira Riseheart" not in (after or {}).get("payoffs", []):
        raise AssertionError(after)
    return {"active_profile_preserved": True, "riseheart_still_active_payoff": True}


def validate_generic_builder() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_blue_eyes_authored() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_activation_gates() -> dict[str, Any]:
    comparison = compare_reconciled_profile("Kashtira", "meta", 2)
    gates = comparison.get("activation_safety_gates", {})
    expected = "eligible_for_experimental_flag" if all(bool(value) for value in gates.values()) else "do_not_activate"
    if comparison.get("activation_recommendation") != expected:
        raise AssertionError({"expected": expected, "comparison": comparison})
    return {"recommendation": comparison["activation_recommendation"], "gates": gates}


def validate_phase8g() -> dict[str, Any]:
    result = run_python("validate_phase8g.py", timeout=9000)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8f() -> dict[str, Any]:
    result = run_python("validate_phase8f.py", timeout=9000)
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
    report = build_report("Kashtira", "meta", 5)
    save_report(report)
    comparison = report["comparison"]
    generic = comparison["generic_summary"]
    active = comparison["active_profile_summary"]
    reconciled = comparison["reconciled_profile_summary"]
    lines = [
        "# Phase 8H: Reconciled Kashtira Experimental Comparison Harness",
        "",
        "Comparison/reporting only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, duel engine features, or full combo graphs were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_reconciled_comparison.py`",
        "- `semi_specialization_reconciled_comparison_report.py`",
        "- `validate_phase8h.py`",
        "- `PHASE8H_RECONCILED_KASHTIRA_COMPARISON.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Generic Summary",
        "",
        f"- Generic total gap: {generic.get('generic_total_gap')}",
        f"- Full movement projected gap: {generic.get('full_movement_projected_gap')}",
        f"- Filler dependency: {generic.get('filler_dependency')}",
        f"- Repair dependency: {generic.get('repair_dependency')}",
        f"- Blocked-card violations: {', '.join(generic.get('blocked_card_violations', [])) or 'none'}",
        "",
        "## Active Profile Summary",
        "",
        f"- Role audit score: {active.get('role_audit_score')}",
        f"- Readiness: `{active.get('readiness_classification')}`",
        f"- Role conflicts: {active.get('role_conflicts')}",
        f"- Quota gap: {active.get('quota_gap')}",
        "",
        "## Reconciled Profile Summary",
        "",
        f"- Role audit score: {reconciled.get('role_audit_score')}",
        f"- Readiness: `{reconciled.get('readiness_classification')}`",
        f"- Role conflicts: {reconciled.get('role_conflicts')}",
        f"- Quota gap: {reconciled.get('quota_gap')}",
        f"- Quota gap delta vs generic: {reconciled.get('quota_gap_delta_vs_generic')}",
        f"- Worsened core roles: {', '.join(reconciled.get('worsened_core_roles', [])) or 'none'}",
        "",
        "## Activation Recommendation",
        "",
        f"- `{comparison.get('activation_recommendation')}`",
        f"- Reconciled improves balance: {comparison.get('reconciled_improves_balance')}",
        f"- Reconciled improves readiness: {comparison.get('reconciled_improves_readiness')}",
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
            "## Recommended Phase 8I",
            "",
            "- Add a non-activated experimental flag scaffold that can run a candidate reconciled build path only when explicitly requested.",
            "- Keep the default generic builder untouched and require regression reports before any activation.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
