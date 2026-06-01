from __future__ import annotations

from pathlib import Path

from SystemAIYugioh.validation_harness import (
    assert_json_report_exists,
    assert_markdown_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


HARNESS_PATH = Path("SystemAIYugioh") / "validation_harness.py"
PHASE_REPORT = Path("PHASE7B_VALIDATOR_CONSOLIDATION.md")
SUITE_REPORT = Path("VALIDATION_SUITE_REPORT.md")
MIGRATED_VALIDATORS = (
    "validate_phase7a.py",
    "validate_stabilization_m.py",
    "validate_stabilization_l.py",
    "validate_stabilization_k.py",
    "validate_stabilization_j.py",
)


def main() -> None:
    checks = [
        ("shared harness exists", validate_harness_exists),
        ("migrated validators import shared harness", validate_migrated_imports),
        ("composite runner works", validate_core_suite),
        ("core suite passes", validate_core_suite_result),
        ("matrix smoke still passes", validate_matrix_smoke),
        ("validation reports are generated", validate_reports_generated),
    ]
    result = run_checks(
        "validate_phase7b",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase7b.json",
    )
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 7B validation complete.")


def validate_harness_exists() -> dict[str, object]:
    text = HARNESS_PATH.read_text(encoding="utf-8")
    for term in ("run_command", "run_python", "assert_success", "CommandResult", "ValidationResult"):
        if term not in text:
            raise AssertionError(f"harness missing {term}")
    return {"path": HARNESS_PATH.as_posix()}


def validate_migrated_imports() -> dict[str, object]:
    missing = []
    for path in MIGRATED_VALIDATORS:
        text = Path(path).read_text(encoding="utf-8")
        if "SystemAIYugioh.validation_harness" not in text:
            missing.append(path)
    if missing:
        raise AssertionError(missing)
    return {"migrated": list(MIGRATED_VALIDATORS)}


def validate_core_suite() -> dict[str, object]:
    result = run_python("validate_core_suite.py", timeout=3600)
    assert_success(result)
    return {"duration_seconds": round(result.duration_seconds, 4)}


def validate_core_suite_result() -> dict[str, object]:
    payload = assert_json_report_exists(Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_core_suite.json", ("validator", "passed", "checks", "duration_seconds"))
    if not payload.get("passed"):
        raise AssertionError(payload)
    return {"checks": len(payload.get("checks", [])), "duration_seconds": payload.get("duration_seconds")}


def validate_matrix_smoke() -> dict[str, object]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"duration_seconds": round(result.duration_seconds, 4)}


def validate_reports_generated() -> dict[str, object]:
    assert_markdown_report_exists(SUITE_REPORT, ("Validators Migrated", "Commands Deduplicated", "Runtime Summary"))
    for validator in MIGRATED_VALIDATORS:
        json_name = validator.replace(".py", ".json")
        assert_json_report_exists(Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / json_name, ("validator", "passed", "checks", "duration_seconds"))
    return {"suite_report": SUITE_REPORT.as_posix(), "migrated_json_reports": len(MIGRATED_VALIDATORS)}


def write_phase_report(payload: dict[str, object]) -> None:
    lines = [
        "# Phase 7B: Validator Suite Consolidation",
        "",
        "Infrastructure-only phase. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression threshold, filler-memory, or opponent-influence changes were made.",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/validation_harness.py`",
        "- `validate_core_suite.py`",
        "- `validate_phase7b.py`",
        "- `VALIDATION_SUITE_REPORT.md`",
        "- migrated validator scripts listed below",
        "",
        "## Migrated Validators",
        "",
    ]
    lines.extend(f"- `{validator}`" for validator in MIGRATED_VALIDATORS)
    lines.extend(
        [
            "",
            "## Runtime Summary",
            "",
            "- Baseline runtime before consolidation: not available as a structured measurement.",
            f"- Phase 7B validator duration: {payload.get('duration_seconds')} seconds",
            "- Current core suite runtime is recorded in `VALIDATION_SUITE_REPORT.md`.",
            "- Core suite writes machine-readable JSON to `SystemAIYugioh/data/training_runs/validation/`.",
            "- Nested matrix smokes are skipped during core-suite runs and executed once by `validate_core_suite.py`.",
            "",
            "## Remaining Validation Debt",
            "",
            "- Validators outside the migrated core suite may still define local `run_command` helpers.",
            "- Some legacy validators still inspect human-readable stdout strings.",
            "- More validators can be moved into the harness incrementally without changing gameplay systems.",
        ]
    )
    PHASE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
