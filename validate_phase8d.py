from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_quota_replay import replay_quota_plan
from semi_specialization_quota_replay_report import build_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8D_KASHTIRA_QUOTA_REPLAY.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8d.json"
REPLAY_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_quota_replay_report.json"
REPLAY_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_quota_replay_report.md"


def main() -> None:
    checks = [
        ("replay module runs", validate_replay_module),
        ("report runner generates JSON/Markdown", validate_report_runner),
        ("replay output marks not_activated true", validate_not_activated),
        ("generic builder still works", validate_generic_builder),
        ("Blue-Eyes authored behavior remains untouched", validate_blue_eyes_authored),
        ("Phase 8C validator still passes", validate_phase8c),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8d", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8D validation complete.")


def validate_replay_module() -> dict[str, Any]:
    replay = replay_quota_plan("Kashtira", "meta", 2)
    if "generic_balance" not in replay or "proposed_balance" not in replay:
        raise AssertionError(replay)
    return {"gap_delta": replay["gap_delta"], "improved_roles": replay["improved_roles"], "worsened_roles": replay["worsened_roles"]}


def validate_report_runner() -> dict[str, Any]:
    report = build_report("Kashtira", "meta", 3)
    save_report(report)
    assert_json_report_exists(REPLAY_JSON, ("replay", "semi_specialization_activated"))
    assert_markdown_report_exists(REPLAY_MD, ("Before/After Balance", "Improved Roles", "Worsened Roles"))
    return {"gap_delta": report["replay"]["gap_delta"]}


def validate_not_activated() -> dict[str, Any]:
    replay = replay_quota_plan("Kashtira", "meta", 1)
    if replay.get("not_activated") is not True:
        raise AssertionError(replay)
    report = build_report("Kashtira", "meta", 1)
    if report.get("semi_specialization_activated") is not False:
        raise AssertionError(report)
    return {"replay_not_activated": replay["not_activated"], "report_activated": report["semi_specialization_activated"]}


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


def validate_phase8c() -> dict[str, Any]:
    result = run_python("validate_phase8c.py", timeout=9000)
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
    replay_report = build_report("Kashtira", "meta", 5)
    save_report(replay_report)
    replay = replay_report["replay"]
    lines = [
        "# Phase 8D: Kashtira Quota Replay Harness",
        "",
        "Replay/testing only. No semi-specialized deck building was activated, no generic builder was replaced, and no gameplay scoring, Blue-Eyes authored behavior, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, or duel engine features were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_quota_replay.py`",
        "- `semi_specialization_quota_replay_report.py`",
        "- `validate_phase8d.py`",
        "- `PHASE8D_KASHTIRA_QUOTA_REPLAY.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Quota Replay Behavior",
        "",
        "- Builds normal generic Kashtira decks.",
        "- Compares observed role/package counts against Phase 8C quota targets.",
        "- Projects report-only quota adjustments toward the target balance.",
        "- Does not alter final deck scores or deck construction.",
        f"- Not activated: {replay['not_activated']}",
        "",
        "## Before/After Quota Balance",
        "",
        f"- Generic total gap: {replay['generic_total_gap']}",
        f"- Proposed total gap: {replay['proposed_total_gap']}",
        f"- Gap delta: {replay['gap_delta']}",
    ]
    for role, before in replay["generic_balance"].items():
        after = replay["proposed_balance"].get(role, {})
        lines.append(f"- `{role}`: generic gap {before['gap']} -> projected gap {after.get('gap')}")
    lines.extend(
        [
            "",
            "## Improved Roles",
            "",
        ]
    )
    lines.extend(f"- `{role}`" for role in replay["improved_roles"]) if replay["improved_roles"] else lines.append("- None")
    lines.extend(["", "## Worsened Roles", ""])
    lines.extend(f"- `{role}`" for role in replay["worsened_roles"]) if replay["worsened_roles"] else lines.append("- None")
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in replay["risk_flags"]) if replay["risk_flags"] else lines.append("- None")
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
            "## Recommended Phase 8E",
            "",
            "- Add a non-activating quota replay comparison against alternate target strengths, such as 50%, 75%, and 100% target movement.",
            "- Inspect whether payoff/interruption under-target gaps come from role classification before adding any builder flag.",
            "- Keep any future semi-specialized builder behind an explicit experimental flag plus generic-vs-experimental regression gates.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
