from __future__ import annotations

from pathlib import Path
from typing import Any

from SystemAIYugioh.fingerprint_coverage_audit import COVERAGE_REPORT_MD, run_fingerprint_coverage_audit
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.opponent_signal_sentinel import opponent_signal_sentinel
from SystemAIYugioh.regression_gates import evaluate_training_batch
from SystemAIYugioh.validation_harness import (
    assert_markdown_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


PHASE_REPORT = Path("PHASE8A_EXPANSION_SAFETY_GATES.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8a.json"


def main() -> None:
    checks = [
        ("fingerprint coverage audit works", validate_fingerprint_coverage_audit),
        ("no uncovered score-affecting modules remain", validate_no_uncovered_modules),
        ("sentinel degradation detection reports correctly", validate_sentinel_degradation_detection),
        ("CI entry path works", validate_ci_entry_path),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8a", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8A validation complete.")


def validate_fingerprint_coverage_audit() -> dict[str, Any]:
    report = run_fingerprint_coverage_audit(write_reports=True)
    assert_markdown_report_exists(COVERAGE_REPORT_MD, ("Fingerprint Coverage Audit", "Uncovered Modules", "Exclusions"))
    if "passed" not in report or "uncovered" not in report or "excluded" not in report:
        raise AssertionError(report)
    return {
        "passed": report["passed"],
        "candidate_count": report["candidate_count"],
        "fingerprinted_count": report["fingerprinted_count"],
        "excluded_count": report["excluded_count"],
    }


def validate_no_uncovered_modules() -> dict[str, Any]:
    report = run_fingerprint_coverage_audit(write_reports=True)
    if report["uncovered"] or report["stale_fingerprints"]:
        raise AssertionError({"uncovered": report["uncovered"], "stale": report["stale_fingerprints"]})
    return {
        "uncovered": report["uncovered"],
        "stale_fingerprints": report["stale_fingerprints"],
        "excluded": sorted(report["excluded"]),
    }


def validate_sentinel_degradation_detection() -> dict[str, Any]:
    previous = {
        "average_score": 80,
        "average_choke_stop_rate": 0.7,
        "average_graph_stop_rate": 0.6,
        "average_real_combo_report_values": {"playable_hand_rate": 0.8},
    }
    current = {
        "successful_runs": 1,
        "average_score": 80,
        "average_choke_stop_rate": opponent_signal_sentinel("unavailable", "validator probe"),
        "average_real_combo_values": {"playable_hand_rate": {"unexpected": "shape"}},
    }
    result = evaluate_training_batch(current, previous)
    degradation = result.get("metric_degradation_reasons", [])
    if not result.get("accepted"):
        raise AssertionError("reporting-only degradation changed gate acceptance")
    expected_terms = ("average_choke_stop_rate", "average_graph_stop_rate", "average_real_combo_values.playable_hand_rate")
    missing = [term for term in expected_terms if not any(term in reason for reason in degradation)]
    if missing:
        raise AssertionError({"missing": missing, "degradation": degradation})
    return {"accepted": result["accepted"], "metric_degradation_reasons": degradation}


def validate_ci_entry_path() -> dict[str, Any]:
    result = run_python("ci_validate.py", "--dry-run", timeout=120)
    assert_success(result, ("validate_core_suite.py", "validate_stabilization_n.py"))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_core_suite() -> dict[str, Any]:
    result = run_python("validate_core_suite.py", timeout=4200)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, Any]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def write_phase_report(payload: dict[str, Any]) -> None:
    coverage = run_fingerprint_coverage_audit(write_reports=True)
    lines = [
        "# Phase 8A: Expansion Safety Gates",
        "",
        "Infrastructure-only pass. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression threshold, filler-memory, or opponent influence behavior was changed.",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/source_fingerprint.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "- `SystemAIYugioh/regression_gates.py`",
        "- `validate_core_suite.py`",
        "- `ci_validate.py`",
        "- `validate_phase8a.py`",
        "- `FINGERPRINT_COVERAGE_AUDIT.md`",
        "- `PHASE8A_EXPANSION_SAFETY_GATES.md`",
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
            "## Fingerprint Coverage",
            "",
            f"- Candidate modules: {coverage['candidate_count']}",
            f"- Fingerprinted modules: {coverage['fingerprinted_count']}",
            f"- Explicit exclusions: {coverage['excluded_count']}",
            f"- Uncovered modules found: {len(coverage['uncovered'])}",
            f"- Coverage report: `{COVERAGE_REPORT_MD}`",
            "",
            "## Uncovered Modules Found",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in coverage["uncovered"]) if coverage["uncovered"] else lines.append("- None")
    lines.extend(["", "## Exclusions Added", ""])
    for path, reason in sorted(coverage["excluded"].items()):
        lines.append(f"- `{path}`: {reason}")
    lines.extend(
        [
            "",
            "## Sentinel Degradation Detection",
            "",
            "- Historical numeric metrics that become missing, sentinel, or schema-mismatched now appear in `metric_degradation_reasons` and `reporting_reasons`.",
            "- These reporting fields do not affect `accepted` and do not alter regression thresholds.",
            "",
            "## CI Readiness",
            "",
            "- `ci_validate.py` runs `validate_core_suite.py` and `validate_stabilization_n.py`.",
            "- `validate_stabilization_n.py` has been promoted into `CORE_VALIDATORS`.",
            "- `ci_validate.py --dry-run` exposes the CI command plan without running validators.",
            "",
            "## Remaining Risks",
            "",
            "- New score-affecting modules must be added to `SCORE_AFFECTING_SOURCE_FILES` or documented in `FINGERPRINT_EXCLUSIONS`.",
            "- The coverage heuristic is conservative and may flag future modules for human classification.",
            "- Full CI runtime now includes Stabilization N inside the core suite and as the explicit CI readiness command requested for this phase.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
