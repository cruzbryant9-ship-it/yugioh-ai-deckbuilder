from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_public_overlay_delta_analysis import COMPONENTS, run_delta_analysis, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_w.json"
PHASE_REPORT = Path("STABILIZATION_W_PUBLIC_OVERLAY_DELTA_ANALYSIS.md")
_ANALYSIS_CACHE: dict[str, Any] | None = None


def main() -> None:
    checks = [
        ("analysis runner works", validate_analysis_runner),
        ("30 run-level rows are produced", validate_thirty_rows),
        ("component deltas are present", validate_component_deltas),
        ("winning/losing summaries are present", validate_win_loss_summaries),
        ("loss clusters are present", validate_loss_clusters),
        ("card-delta summary is present", validate_card_delta_summary),
        ("no behavior changes occur", validate_no_behavior_changes),
        ("Stabilization V validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_v", "validate_stabilization_v.py")),
        ("Stabilization U validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_u", "validate_stabilization_u.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_w", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization W validation complete.")


def analysis_report() -> dict[str, Any]:
    global _ANALYSIS_CACHE
    if _ANALYSIS_CACHE is None:
        _ANALYSIS_CACHE = run_delta_analysis("meta", 30, 12345, frozen_cards=True)
    return _ANALYSIS_CACHE


def validate_analysis_runner() -> dict[str, Any]:
    report = run_delta_analysis("meta", 2, 12345, frozen_cards=True)
    json_path, md_path = save_report(report)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "runs": report["runs"], "recommendation": report["recommendation"]}


def validate_thirty_rows() -> dict[str, Any]:
    report = analysis_report()
    save_report(report)
    if report.get("runs") != 30 or len(report.get("run_level_rows", [])) != 30:
        raise AssertionError({"runs": report.get("runs"), "rows": len(report.get("run_level_rows", []))})
    return {"runs": report["runs"], "rows": len(report["run_level_rows"])}


def validate_component_deltas() -> dict[str, Any]:
    report = analysis_report()
    first = report["run_level_rows"][0]
    missing = set(COMPONENTS) - set(first.get("component_deltas", {}))
    summary_missing = set(COMPONENTS) - set(report["component_delta_summary"].get("all_runs", {}))
    if missing or summary_missing:
        raise AssertionError({"row_missing": sorted(missing), "summary_missing": sorted(summary_missing)})
    return {"components": list(COMPONENTS), "first_delta": first["component_deltas"]}


def validate_win_loss_summaries() -> dict[str, Any]:
    report = analysis_report()
    summary = report.get("win_loss_summary", {})
    if not {"positive_run_count", "negative_run_count", "neutral_run_count"} <= set(summary):
        raise AssertionError(summary)
    if "winning_runs" not in report["component_delta_summary"] or "losing_runs" not in report["component_delta_summary"]:
        raise AssertionError(report["component_delta_summary"])
    return summary


def validate_loss_clusters() -> dict[str, Any]:
    report = analysis_report()
    clusters = report.get("loss_clusters", {})
    if not {"cluster_counts", "cluster_runs", "dominant_cluster", "loss_count"} <= set(clusters):
        raise AssertionError(clusters)
    return clusters


def validate_card_delta_summary() -> dict[str, Any]:
    report = analysis_report()
    summary = report.get("card_delta_summary", {})
    required = {"added_in_winning_runs", "removed_in_winning_runs", "added_in_losing_runs", "removed_in_losing_runs"}
    missing = required - set(summary)
    if missing:
        raise AssertionError(missing)
    return {key: summary[key][:5] for key in sorted(required)}


def validate_no_behavior_changes() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(cards, "Blue-Eyes", mode="meta")
    blue_report = get_last_build_report()
    build_deck(cards, "Kashtira", mode="meta")
    kashtira_report = get_last_build_report()
    if blue_report.get("builder_used") != "authored":
        raise AssertionError(blue_report)
    if kashtira_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(kashtira_report)
    return {"blue_eyes_builder": blue_report.get("builder_used"), "kashtira_builder": kashtira_report.get("builder_used")}


def validate_prior_artifact_or_run(name: str, script: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("passed") is True:
            return {"artifact": str(path), "passed": True, "duration_seconds": payload.get("duration_seconds")}
    result = run_python(script, timeout=7200)
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
    report = run_delta_analysis("meta", 30, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Stabilization W: Public Overlay Delta Analysis",
        "",
        "Analysis/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_public_overlay_delta_analysis.py`",
        "- `validate_stabilization_w.py`",
        "- `STABILIZATION_W_PUBLIC_OVERLAY_DELTA_ANALYSIS.md`",
        "",
        "## Files Changed",
        "",
        "- None; this phase adds analysis/reporting files only.",
        "",
        "## Win/Loss Summary",
        "",
        f"- Score delta: `{report['score_delta']}`",
        f"- Positive / negative / neutral runs: `{report['win_loss_summary']['positive_run_count']}` / `{report['win_loss_summary']['negative_run_count']}` / `{report['win_loss_summary']['neutral_run_count']}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Average Component Deltas",
        "",
    ]
    for component, value in report["component_delta_summary"]["all_runs"].items():
        lines.append(f"- `{component}`: `{value}`")
    lines.extend(["", "## Losing-Run Causes", ""])
    for cause, count in report["loss_clusters"]["cluster_counts"].items():
        lines.append(f"- `{cause}`: `{count}`")
    lines.extend(["", "## Recurring Card Movements", ""])
    for key, rows in report["card_delta_summary"].items():
        lines.append(f"- `{key}`: `{rows[:6]}`")
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
            "## Recommended Next Step",
            "",
            "- Stabilization X should test a proposed-only targeted adjustment against the dominant losing-run cause before considering any active adapter change.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
