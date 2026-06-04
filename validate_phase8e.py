from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_quota_replay import DEFAULT_MOVEMENT_STRENGTHS, replay_quota_plan, replay_quota_sensitivity
from semi_specialization_sensitivity_report import build_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8E_KASHTIRA_QUOTA_SENSITIVITY.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8e.json"
SENSITIVITY_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_sensitivity_report.json"
SENSITIVITY_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_sensitivity_report.md"


def main() -> None:
    checks = [
        ("sensitivity replay runs", validate_sensitivity_replay),
        ("all movement strengths are present", validate_strengths_present),
        ("0% equals generic baseline", validate_baseline_strength),
        ("100% matches Phase 8D proposed replay behavior", validate_full_strength_matches_phase8d),
        ("not_activated remains true", validate_not_activated),
        ("no semi-specialized builder is activated", validate_no_activation),
        ("Phase 8D validator still passes", validate_phase8d),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8e", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8E validation complete.")


def validate_sensitivity_replay() -> dict[str, Any]:
    sensitivity = replay_quota_sensitivity("Kashtira", "meta", 2)
    if not sensitivity.get("sensitivity_results"):
        raise AssertionError(sensitivity)
    return {
        "stability_classification": sensitivity["stability_classification"],
        "movement_strengths": sensitivity["movement_strengths"],
    }


def validate_strengths_present() -> dict[str, Any]:
    sensitivity = replay_quota_sensitivity("Kashtira", "meta", 1)
    expected = [round(float(value), 4) for value in DEFAULT_MOVEMENT_STRENGTHS]
    observed = [round(float(value), 4) for value in sensitivity.get("movement_strengths", [])]
    if observed != expected:
        raise AssertionError({"expected": expected, "observed": observed})
    return {"observed": observed}


def validate_baseline_strength() -> dict[str, Any]:
    sensitivity = replay_quota_sensitivity("Kashtira", "meta", 2)
    baseline = result_for_strength(sensitivity, 0.0)
    if baseline["total_gap"] != sensitivity["generic_total_gap"]:
        raise AssertionError({"baseline": baseline, "generic_total_gap": sensitivity["generic_total_gap"]})
    if baseline["gap_delta_vs_baseline"] != 0.0:
        raise AssertionError(baseline)
    return {"baseline_gap": baseline["total_gap"]}


def validate_full_strength_matches_phase8d() -> dict[str, Any]:
    sensitivity = replay_quota_sensitivity("Kashtira", "meta", 2)
    phase8d = replay_quota_plan("Kashtira", "meta", 2)
    full = result_for_strength(sensitivity, 1.0)
    if full["total_gap"] != phase8d["proposed_total_gap"]:
        raise AssertionError({"full": full, "phase8d": phase8d["proposed_total_gap"]})
    if full["gap_delta_vs_baseline"] != phase8d["gap_delta"]:
        raise AssertionError({"full": full, "phase8d": phase8d["gap_delta"]})
    return {"full_gap": full["total_gap"], "phase8d_gap_delta": phase8d["gap_delta"]}


def validate_not_activated() -> dict[str, Any]:
    report = build_report("Kashtira", "meta", 3)
    save_report(report)
    assert_json_report_exists(SENSITIVITY_JSON, ("sensitivity", "semi_specialization_activated"))
    assert_markdown_report_exists(SENSITIVITY_MD, ("Gap By Movement Strength", "Stability classification"))
    sensitivity = report["sensitivity"]
    if sensitivity.get("not_activated") is not True or report.get("semi_specialization_activated") is not False:
        raise AssertionError(report)
    if any(result.get("not_activated") is not True for result in sensitivity.get("sensitivity_results", [])):
        raise AssertionError(sensitivity)
    return {"not_activated": sensitivity["not_activated"], "report_activated": report["semi_specialization_activated"]}


def validate_no_activation() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    kashtira_deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    kashtira_report = get_last_build_report()
    blue_eyes_deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    blue_eyes_report = get_last_build_report()
    if len(kashtira_deck) < 40 or kashtira_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(kashtira_deck), "report": kashtira_report})
    if len(blue_eyes_deck) < 40 or blue_eyes_report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(blue_eyes_deck), "report": blue_eyes_report})
    return {
        "kashtira_builder": kashtira_report.get("builder_used"),
        "blue_eyes_builder": blue_eyes_report.get("builder_used"),
    }


def validate_phase8d() -> dict[str, Any]:
    result = run_python("validate_phase8d.py", timeout=9000)
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


def result_for_strength(sensitivity: dict[str, Any], strength: float) -> dict[str, Any]:
    target = round(float(strength), 4)
    for result in sensitivity.get("sensitivity_results", []):
        if round(float(result.get("movement_strength", -1)), 4) == target:
            return result
    raise AssertionError({"missing_strength": strength, "sensitivity": sensitivity})


def write_phase_report(payload: dict[str, Any]) -> None:
    report = build_report("Kashtira", "meta", 5)
    save_report(report)
    sensitivity = report["sensitivity"]
    lines = [
        "# Phase 8E: Kashtira Quota Movement Sensitivity Replay",
        "",
        "Replay/testing only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.",
        "",
        "## Files Created",
        "",
        "- `semi_specialization_sensitivity_report.py`",
        "- `validate_phase8e.py`",
        "- `PHASE8E_KASHTIRA_QUOTA_SENSITIVITY.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_quota_replay.py`",
        "",
        "## Sensitivity Results",
        "",
        f"- Stability classification: `{sensitivity['stability_classification']}`",
        f"- Generic total gap: {sensitivity['generic_total_gap']}",
        f"- Not activated: {sensitivity['not_activated']}",
        "",
        "## Gap By Movement Strength",
        "",
    ]
    for result in sensitivity["sensitivity_results"]:
        lines.append(
            f"- `{result['movement_strength']}`: total gap {result['total_gap']}, "
            f"delta vs baseline {result['gap_delta_vs_baseline']}, "
            f"worsened roles {', '.join(result['worsened_roles']) or 'none'}"
        )
    lines.extend(["", "## Worsened Roles", ""])
    worsened = sorted(set(role for row in sensitivity["sensitivity_results"] for role in row.get("worsened_roles", [])))
    lines.extend(f"- `{role}`" for role in worsened) if worsened else lines.append("- None")
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in sensitivity["risk_flags"]) if sensitivity["risk_flags"] else lines.append("- None")
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
            "## Recommended Phase 8F",
            "",
            "- Add a non-activated role-classification audit for Kashtira payoff, interruption, board-breaker, and Extra Deck payoff tags.",
            "- Compare sensitivity using fixed card pools so quota movement can be separated from card database drift.",
            "- Keep any future semi-specialized builder behind an explicit experimental flag and generic-vs-experimental regression gates.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
