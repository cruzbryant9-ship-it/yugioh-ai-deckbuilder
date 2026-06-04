from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_package_planner import build_semi_specialized_package_plan
from semi_specialization_pilot_report import run_pilot_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8C_SEMI_SPECIALIZATION_PILOT.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8c.json"
REPORT_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_semi_specialization_report.json"
REPORT_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_semi_specialization_report.md"


def main() -> None:
    checks = [
        ("Kashtira profile loads", validate_profile_loads),
        ("package planner runs", validate_planner_runs),
        ("semi-specialized plan is not activated", validate_plan_not_activated),
        ("generic builder still works", validate_generic_builder),
        ("Blue-Eyes authored builder remains untouched", validate_blue_eyes_authored),
        ("comparison report generates", validate_report_generates),
        ("Phase 8B validator still passes", validate_phase8b),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8c", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8C validation complete.")


def validate_profile_loads() -> dict[str, Any]:
    profile = load_specialization_profile("Kashtira")
    if not profile or profile.get("archetype") != "Kashtira":
        raise AssertionError(profile)
    for key in ("core_cards", "starters", "extenders", "payoffs", "package_quotas", "known_risk_flags"):
        if not profile.get(key):
            raise AssertionError(f"profile missing {key}")
    return {"core_cards": len(profile["core_cards"]), "starters": len(profile["starters"])}


def validate_planner_runs() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    plan = build_semi_specialized_package_plan("Kashtira", "meta", cards)
    if not plan.get("profile_used") or not plan.get("package_plan") or not plan.get("quota_targets"):
        raise AssertionError(plan)
    return {"quota_targets": plan["quota_targets"], "risk_flags": plan["risk_flags"]}


def validate_plan_not_activated() -> dict[str, Any]:
    plan = build_semi_specialized_package_plan("Kashtira", "meta", CardDatabase().load_cards())
    if plan.get("not_activated") is not True:
        raise AssertionError(plan)
    report = run_pilot_report("Kashtira", "meta", 1)
    if report.get("semi_specialization_activated") is not False or report["comparison"].get("not_activated") is not True:
        raise AssertionError(report)
    return {"plan_not_activated": plan["not_activated"], "report_activated": report["semi_specialization_activated"]}


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


def validate_report_generates() -> dict[str, Any]:
    report = run_pilot_report("Kashtira", "meta", 3)
    save_report(report)
    assert_json_report_exists(REPORT_JSON, ("plan", "comparison", "semi_specialization_activated"))
    assert_markdown_report_exists(REPORT_MD, ("Package Plan", "Generic Comparison", "Semi-specialization activated: False"))
    return {"average_generic_score": report["comparison"]["average_generic_score"], "activated": report["semi_specialization_activated"]}


def validate_phase8b() -> dict[str, Any]:
    result = run_python("validate_phase8b.py", timeout=7200)
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
    report = run_pilot_report("Kashtira", "meta", 3)
    save_report(report)
    plan = report["plan"]
    comparison = report["comparison"]
    lines = [
        "# Phase 8C: Semi-Specialization Pilot Design",
        "",
        "Design/scaffolding only. No semi-specialized builder was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, neural networks, reinforcement learning, self-play, duel engine, or combo graphs were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/archetype_specialization_profiles.py`",
        "- `deck/semi_specialized_package_planner.py`",
        "- `semi_specialization_pilot_report.py`",
        "- `validate_phase8c.py`",
        "- `PHASE8C_SEMI_SPECIALIZATION_PILOT.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Kashtira Profile Summary",
        "",
        f"- Core cards: {', '.join(plan['package_plan']['core'])}",
        f"- Starters: {', '.join(plan['package_plan']['starters'])}",
        f"- Extenders: {', '.join(plan['package_plan']['extenders'])}",
        f"- Payoffs: {', '.join(plan['package_plan']['payoffs'])}",
        f"- Not activated: {plan['not_activated']}",
        "",
        "## Package Plan Summary",
        "",
    ]
    for key, value in plan.get("quota_targets", {}).items():
        lines.append(f"- `{key}` target: {value}")
    lines.extend(
        [
            "",
            "## Generic Vs Semi-Specialized Comparison",
            "",
            f"- Average generic score: {comparison['average_generic_score']}",
            f"- Average generic confidence: {comparison['average_generic_confidence']}",
            f"- Generic decks 40+: {comparison['legality_readiness']['all_decks_40_plus']}",
            f"- Repair success rate: {comparison['legality_readiness']['repair_success_rate']}",
            f"- Average repair actions: {comparison['repair_dependency']['average_repair_action_count']}",
            f"- Average safe filler count: {comparison['filler_dependency']['average_safe_filler_used_count']}",
            "- Semi-specialized plan was compared only as a proposed package plan and was not used for deck construction.",
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
            "## Recommended Phase 8D",
            "",
            "- Add a non-activating generic-vs-profile quota replay harness for Kashtira.",
            "- Review whether payoff/interruption underrepresentation is a generic role-classification issue before writing combo graphs.",
            "- Keep semi-specialized building behind an explicit experimental flag until a regression comparison proves it is safe.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
