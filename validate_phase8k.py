from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_experimental_regression_analysis import run_regression_analysis, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8K_KASHTIRA_REGRESSION_ANALYSIS.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8k.json"
ANALYSIS_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_regression_analysis.json"
ANALYSIS_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_regression_analysis.md"


def main() -> None:
    checks = [
        ("analyzer runs", validate_analyzer_runs),
        ("fixed-seed/frozen-card mode is used", validate_fixed_frozen),
        ("generic and experimental are compared", validate_comparison),
        ("component deltas are reported", validate_component_deltas),
        ("card-level differences are reported", validate_card_diffs),
        ("package-level differences are reported", validate_package_diffs),
        ("recommendation is report-only", validate_report_only),
        ("experimental path remains off by default", validate_default_off),
        ("Phase 8J validator still passes", validate_phase8j),
        ("Phase 8I validator still passes", validate_phase8i),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8k", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8K validation complete.")


def validate_analyzer_runs() -> dict[str, Any]:
    report = run_regression_analysis("meta", 3, 12345, frozen_cards=True)
    save_report(report)
    assert_json_report_exists(ANALYSIS_JSON, ("component_deltas", "card_level_differences", "package_level_differences"))
    assert_markdown_report_exists(ANALYSIS_MD, ("Largest Negative Components", "Card-Level Differences", "Likely Root Causes"))
    return {"score_delta": report["score_delta"], "recommendation": report["recommendation"]}


def validate_fixed_frozen() -> dict[str, Any]:
    report = run_regression_analysis("meta", 1, 12345, frozen_cards=True)
    if report.get("seed") != 12345 or report.get("frozen_cards") is not True or report.get("live_refresh_used") is not False:
        raise AssertionError(report)
    return {"seed": report["seed"], "frozen_cards": report["frozen_cards"], "live_refresh_used": report["live_refresh_used"]}


def validate_comparison() -> dict[str, Any]:
    report = run_regression_analysis("meta", 1, 12345, frozen_cards=True)
    if "generic_average_score" not in report or "experimental_average_score" not in report:
        raise AssertionError(report)
    return {"generic": report["generic_average_score"], "experimental": report["experimental_average_score"]}


def validate_component_deltas() -> dict[str, Any]:
    report = run_regression_analysis("meta", 1, 12345, frozen_cards=True)
    required = {"final_score", "consistency_score", "endboard_score", "package_quality_score"}
    if not required.issubset(report.get("component_deltas", {})):
        raise AssertionError(report.get("component_deltas"))
    return {"components": sorted(report["component_deltas"])}


def validate_card_diffs() -> dict[str, Any]:
    report = run_regression_analysis("meta", 2, 12345, frozen_cards=True)
    diffs = report.get("card_level_differences", {})
    if "cards_added_more_often_by_experimental" not in diffs or "cards_removed_more_often_by_experimental" not in diffs:
        raise AssertionError(diffs)
    return {"added": len(diffs["cards_added_more_often_by_experimental"]), "removed": len(diffs["cards_removed_more_often_by_experimental"])}


def validate_package_diffs() -> dict[str, Any]:
    report = run_regression_analysis("meta", 2, 12345, frozen_cards=True)
    package = report.get("package_level_differences", {})
    if "package_count_deltas" not in package:
        raise AssertionError(package)
    return {"package_delta_keys": sorted(package["package_count_deltas"])}


def validate_report_only() -> dict[str, Any]:
    report = run_regression_analysis("meta", 1, 12345, frozen_cards=True)
    allowed = {"adjust_profile_targets", "adjust_role_map", "adjust_adapter_selection", "keep_blocked", "retest_needed"}
    if report.get("recommendation") not in allowed or report.get("report_only") is not True:
        raise AssertionError(report)
    return {"recommendation": report["recommendation"], "report_only": report["report_only"]}


def validate_default_off() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_phase8j() -> dict[str, Any]:
    result = run_python("validate_phase8j.py", timeout=9000)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8i() -> dict[str, Any]:
    result = run_python("validate_phase8i.py", timeout=9000)
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
    report = run_regression_analysis("meta", 10, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Phase 8K: Kashtira Experimental Regression Analysis",
        "",
        "Analysis/reporting only. No gameplay behavior, builder behavior, scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, full combo graphs, or generic builder behavior were changed.",
        "",
        "## Files Created",
        "",
        "- `kashtira_experimental_regression_analysis.py`",
        "- `validate_phase8k.py`",
        "- `PHASE8K_KASHTIRA_REGRESSION_ANALYSIS.md`",
        "",
        "## Files Changed",
        "",
        "- None",
        "",
        "## Largest Negative Components",
        "",
    ]
    lines.extend(f"- `{row['component']}`: {row['delta']}" for row in report["largest_negative_components"]) or lines.append("- None")
    lines.extend(["", "## Largest Positive Components", ""])
    lines.extend(f"- `{row['component']}`: {row['delta']}" for row in report["largest_positive_components"]) or lines.append("- None")
    lines.extend(["", "## Card-Level Differences", ""])
    for row in report["card_level_differences"]["cards_added_more_often_by_experimental"][:8]:
        lines.append(f"- Added `{row['card']}`: +{row['count_delta']} ({row['role_category']})")
    for row in report["card_level_differences"]["cards_removed_more_often_by_experimental"][:8]:
        lines.append(f"- Removed `{row['card']}`: -{row['count_delta']} ({row['role_category']})")
    lines.extend(["", "## Package-Level Differences", ""])
    for key, value in report["package_level_differences"]["package_count_deltas"].items():
        if value:
            lines.append(f"- `{key}`: {value:+}")
    lines.extend(["", "## Root-Cause Summary", ""])
    lines.extend(f"- {cause}" for cause in report["likely_root_causes"])
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- `{report['recommendation']}`",
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
            "## Recommended Phase 8L",
            "",
            "- Create a proposed-only adapter tuning plan based on the regression analysis, then test it under the fixed-seed Phase 8J gate before applying any code behavior change.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
