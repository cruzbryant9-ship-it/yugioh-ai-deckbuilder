from __future__ import annotations

from pathlib import Path
from typing import Any

from archetype_specialization_report import LATEST_JSON, LATEST_MD, build_report, save_report
from deck.archetype_specialization_detector import evaluate_specialization_candidate
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import (
    assert_json_report_exists,
    assert_markdown_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


PHASE_REPORT = Path("PHASE8B_ARCHETYPE_SPECIALIZATION_CANDIDATES.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8b.json"


def main() -> None:
    checks = [
        ("detector runs", validate_detector_runs),
        ("report runner works", validate_report_runner),
        ("readiness score is produced", validate_readiness_score),
        ("watchlist or ready supported by evidence", validate_watchlist_or_ready),
        ("insufficient evidence produces not_ready", validate_insufficient_evidence),
        ("blocked-card contamination fails candidate status", validate_blocked_contamination),
        ("high repair dependency prevents ready status", validate_high_repair_dependency),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8b", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8B validation complete.")


def validate_detector_runs() -> dict[str, Any]:
    row = evaluate_specialization_candidate("Branded", "meta")
    if row["candidate_status"] not in {"ready", "watchlist", "not_ready"}:
        raise AssertionError(row)
    return {"archetype": row["archetype"], "status": row["candidate_status"], "score": row["readiness_score"]}


def validate_report_runner() -> dict[str, Any]:
    report = build_report(["Branded", "Kashtira", "Runick", "Tearlaments"], "meta")
    save_report(report)
    assert_json_report_exists(LATEST_JSON, ("results", "ready_candidates", "watchlist_candidates", "not_ready_candidates"))
    assert_markdown_report_exists(LATEST_MD, ("Ready Candidates", "Watchlist Candidates", "Not-Ready Candidates"))
    return report["summary"]


def validate_readiness_score() -> dict[str, Any]:
    row = evaluate_specialization_candidate("Kashtira", "meta")
    score = row.get("readiness_score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        raise AssertionError(row)
    return {"score": score, "status": row["candidate_status"]}


def validate_watchlist_or_ready() -> dict[str, Any]:
    report = build_report(["Branded", "Kashtira", "Runick", "Tearlaments"], "meta")
    supported = [row for row in report["results"] if row["candidate_status"] in {"watchlist", "ready"}]
    if not supported:
        raise AssertionError(report)
    return {"supported": [(row["archetype"], row["candidate_status"], row["readiness_score"]) for row in supported]}


def validate_insufficient_evidence() -> dict[str, Any]:
    row = evaluate_specialization_candidate("NoEvidenceProbe", "meta", evidence_override={**base_ready_evidence(), "benchmark_runs": 0})
    if row["candidate_status"] != "not_ready" or "minimum_benchmark_runs" not in row["failed_gates"]:
        raise AssertionError(row)
    return {"status": row["candidate_status"], "failed_gates": row["failed_gates"]}


def validate_blocked_contamination() -> dict[str, Any]:
    row = evaluate_specialization_candidate(
        "BlockedProbe",
        "meta",
        evidence_override={**base_ready_evidence(), "blocked_card_violations": ["Forbidden Card"]},
    )
    if row["candidate_status"] == "ready" or "blocked_card_clean" not in row["failed_gates"]:
        raise AssertionError(row)
    return {"status": row["candidate_status"], "failed_gates": row["failed_gates"]}


def validate_high_repair_dependency() -> dict[str, Any]:
    row = evaluate_specialization_candidate(
        "RepairProbe",
        "meta",
        evidence_override={**base_ready_evidence(), "average_repair_actions": 8.0},
    )
    if row["candidate_status"] == "ready" or "low_repair_dependency" not in row["failed_gates"]:
        raise AssertionError(row)
    return {"status": row["candidate_status"], "failed_gates": row["failed_gates"]}


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


def base_ready_evidence() -> dict[str, Any]:
    return {
        "benchmark_runs": 50,
        "average_tuned_improvement": 1.0,
        "repair_success_rate": 1.0,
        "average_repair_actions": 1.0,
        "rejected_deck_count": 0,
        "rejected_deck_rate": 0.0,
        "quota_warning_count": 0,
        "quota_warning_rate": 0.0,
        "generic_confidence_score": 0.8,
        "role_inference_confidence": 0.8,
        "role_coverage_count": 6,
        "archetype_card_count": 20,
        "package_stability": 0.8,
        "ratio_memory_stability": 0.8,
        "benchmark_trend": "stable",
        "blocked_card_violations": [],
        "filler_dependency": 0.0,
        "filler_observation_count": 10,
        "tuning_hurt_count": 0,
        "best_improvement": 2.0,
        "worst_improvement": 0.1,
    }


def write_phase_report(payload: dict[str, Any]) -> None:
    report = build_report(["Branded", "Kashtira", "Runick", "Tearlaments"], "meta")
    save_report(report)
    ready = [row["archetype"] for row in report["ready_candidates"]]
    watchlist = [row["archetype"] for row in report["watchlist_candidates"]]
    not_ready = [row["archetype"] for row in report["not_ready_candidates"]]
    lines = [
        "# Phase 8B: Archetype Specialization Candidate Detection",
        "",
        "Detection/reporting only. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression thresholds, neural networks, reinforcement learning, self-play, or duel-engine features were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/archetype_specialization_detector.py`",
        "- `archetype_specialization_report.py`",
        "- `validate_phase8b.py`",
        "- `PHASE8B_ARCHETYPE_SPECIALIZATION_CANDIDATES.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Readiness Gates",
        "",
        "- minimum benchmark runs",
        "- average tuned improvement",
        "- repair success rate",
        "- rejected deck rate",
        "- quota warning rate",
        "- generic confidence score",
        "- role inference confidence",
        "- package stability",
        "- ratio memory stability",
        "- benchmark trend not declining",
        "- blocked-card clean",
        "- low repair dependency",
        "- filler dependency not excessive",
        "",
        "## Candidate Results",
        "",
        f"- Ready: {', '.join(ready) if ready else 'None'}",
        f"- Watchlist: {', '.join(watchlist) if watchlist else 'None'}",
        f"- Not ready: {', '.join(not_ready) if not_ready else 'None'}",
        "",
        "## Evidence Summary",
        "",
    ]
    for row in report["results"]:
        evidence = row["evidence"]
        lines.append(
            f"- `{row['archetype']}`: {row['candidate_status']} score {row['readiness_score']}; "
            f"runs={evidence.get('benchmark_runs')}, improvement={evidence.get('average_tuned_improvement')}, "
            f"repair={evidence.get('repair_success_rate')}, failed={', '.join(row['failed_gates']) or 'none'}"
        )
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
            "## Recommended Phase 8C",
            "",
            "- Manually review watchlist/ready archetypes and choose one semi-specialization pilot.",
            "- Draft archetype-specific package constraints and role maps only; still avoid authored combo graphs until evidence is reviewed.",
            "- Add a pre-promotion regression report comparing generic vs semi-specialized behavior before any activation.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
