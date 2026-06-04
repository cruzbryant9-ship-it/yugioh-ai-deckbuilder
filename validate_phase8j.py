from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_experimental_regression_gate import recommend_regression_status, run_regression_gate, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8J_KASHTIRA_EXPERIMENTAL_REGRESSION_GATE.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8j.json"
GATE_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_experimental_regression_gate.json"
GATE_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_experimental_regression_gate.md"


def main() -> None:
    checks = [
        ("regression gate runner works", validate_gate_runs),
        ("fixed seed mode is enforced", validate_fixed_seed),
        ("frozen-card mode is enforced", validate_frozen_cards),
        ("generic and experimental are compared", validate_comparison_present),
        ("score regression blocks promotion", validate_score_regression_blocks),
        ("legality failure blocks promotion", validate_legality_failure_blocks),
        ("blocked-card failure blocks promotion", validate_blocked_card_failure_blocks),
        ("fallback path is measured", validate_fallback_measured),
        ("Blue-Eyes authored behavior remains untouched", validate_blue_eyes_authored),
        ("experimental path remains off by default", validate_experimental_off_default),
        ("Phase 8I validator still passes", validate_phase8i),
        ("Phase 8H validator still passes", validate_phase8h),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8j", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8J validation complete.")


def validate_gate_runs() -> dict[str, Any]:
    report = run_regression_gate("meta", 3, 12345, frozen_cards=True)
    save_report(report)
    assert_json_report_exists(GATE_JSON, ("generic", "experimental", "recommendation"))
    assert_markdown_report_exists(GATE_MD, ("Generic", "Experimental", "Recommendation"))
    return {"recommendation": report["recommendation"], "score_delta": report["score_delta"]}


def validate_fixed_seed() -> dict[str, Any]:
    first = run_regression_gate("meta", 2, 12345, frozen_cards=True)
    second = run_regression_gate("meta", 2, 12345, frozen_cards=True)
    fields = ("average_score", "best_score", "worst_score", "score_variance")
    for side in ("generic", "experimental"):
        for field in fields:
            if first[side][field] != second[side][field]:
                raise AssertionError({"side": side, "field": field, "first": first[side][field], "second": second[side][field]})
    return {"seed": first["seed"], "deterministic": True}


def validate_frozen_cards() -> dict[str, Any]:
    report = run_regression_gate("meta", 1, 12345, frozen_cards=True)
    if report.get("frozen_cards") is not True or report.get("live_refresh_used") is not False:
        raise AssertionError(report)
    return {"frozen_cards": report["frozen_cards"], "live_refresh_used": report["live_refresh_used"]}


def validate_comparison_present() -> dict[str, Any]:
    report = run_regression_gate("meta", 1, 12345, frozen_cards=True)
    if not report.get("generic") or not report.get("experimental"):
        raise AssertionError(report)
    return {"generic_builder": report["generic"]["builders_used"], "experimental_builder": report["experimental"]["builders_used"]}


def validate_score_regression_blocks() -> dict[str, Any]:
    generic = clean_summary(average_score=190, legality_rate=1.0, quota_balance=5)
    experimental = clean_summary(average_score=189, legality_rate=1.0, quota_balance=3)
    recommendation = recommend_regression_status(generic, experimental, 10)
    if recommendation != "promote_blocked":
        raise AssertionError(recommendation)
    return {"recommendation": recommendation}


def validate_legality_failure_blocks() -> dict[str, Any]:
    generic = clean_summary(average_score=190, legality_rate=1.0, quota_balance=5)
    experimental = clean_summary(average_score=191, legality_rate=0.9, quota_balance=3)
    recommendation = recommend_regression_status(generic, experimental, 10)
    if recommendation != "promote_blocked":
        raise AssertionError(recommendation)
    return {"recommendation": recommendation}


def validate_blocked_card_failure_blocks() -> dict[str, Any]:
    generic = clean_summary(average_score=190, legality_rate=1.0, quota_balance=5)
    experimental = clean_summary(average_score=191, legality_rate=1.0, quota_balance=3)
    experimental["blocked_card_violations"] = ["Strength in Unity"]
    recommendation = recommend_regression_status(generic, experimental, 10)
    if recommendation != "promote_blocked":
        raise AssertionError(recommendation)
    return {"recommendation": recommendation}


def validate_fallback_measured() -> dict[str, Any]:
    generic = clean_summary(average_score=190, legality_rate=1.0, quota_balance=5)
    experimental = clean_summary(average_score=191, legality_rate=1.0, quota_balance=3, fallback_rate=0.2)
    recommendation = recommend_regression_status(generic, experimental, 10)
    if recommendation != "needs_retest":
        raise AssertionError(recommendation)
    return {"recommendation": recommendation}


def validate_blue_eyes_authored() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_experimental_off_default() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_phase8i() -> dict[str, Any]:
    result = run_python("validate_phase8i.py", timeout=9000)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8h() -> dict[str, Any]:
    result = run_python("validate_phase8h.py", timeout=9000)
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


def clean_summary(**overrides: Any) -> dict[str, Any]:
    summary = {
        "average_score": 190,
        "legality_rate": 1.0,
        "blocked_card_violations": [],
        "fallback_rate": 0.0,
        "quota_balance": 5,
        "score_variance": 0.0,
    }
    summary.update(overrides)
    return summary


def write_phase_report(payload: dict[str, Any]) -> None:
    report = run_regression_gate("meta", 10, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Phase 8J: Kashtira Experimental Regression Gate",
        "",
        "Deterministic regression testing only. The experimental builder was not promoted, semi-specialized building was not made default, and scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, full combo graphs, generic builder behavior, and legality enforcement were not changed.",
        "",
        "## Files Created",
        "",
        "- `kashtira_experimental_regression_gate.py`",
        "- `validate_phase8j.py`",
        "- `PHASE8J_KASHTIRA_EXPERIMENTAL_REGRESSION_GATE.md`",
        "",
        "## Files Changed",
        "",
        "- None",
        "",
        "## Regression Gate Behavior",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Live refresh used: {report['live_refresh_used']}",
        "",
        "## Fixed-Seed Results",
        "",
        f"- Generic average score: {report['generic']['average_score']}",
        f"- Experimental average score: {report['experimental']['average_score']}",
        f"- Score delta: {report['score_delta']}",
        f"- Generic quota balance: {report['generic']['quota_balance']}",
        f"- Experimental quota balance: {report['experimental']['quota_balance']}",
        f"- Experimental fallback rate: {report['experimental']['fallback_rate']}",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion blocked: {report['promotion_blocked']}",
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
            "## Recommended Phase 8K",
            "",
            "- Improve the explicit experimental Kashtira adapter under the fixed-seed gate, focusing on score parity before any promotion discussion.",
            "- Keep promotion blocked until the gate reports equal-or-better score, clean legality, zero fallback, and equal-or-better quota balance.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
