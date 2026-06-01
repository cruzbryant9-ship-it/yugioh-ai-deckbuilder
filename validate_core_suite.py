from __future__ import annotations

from pathlib import Path

from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import (
    assert_success,
    core_suite_env,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


REPORT_PATH = Path("VALIDATION_SUITE_REPORT.md")
VALIDATION_JSON_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "validation"
CORE_VALIDATORS = (
    "validate_phase7a.py",
    "validate_stabilization_m.py",
    "validate_stabilization_l.py",
    "validate_stabilization_k.py",
    "validate_stabilization_j.py",
)


def main() -> None:
    checks = [(validator, validator_check(validator)) for validator in CORE_VALIDATORS]
    checks.append(("matchup matrix smoke", validate_matrix_smoke))
    result = run_checks(
        "validate_core_suite",
        checks,
        json_path=VALIDATION_JSON_DIR / "validate_core_suite.json",
    )
    write_suite_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Core validation suite complete.")


def validator_check(script: str):
    def check() -> dict[str, object]:
        result = run_python(script, timeout=3000, env=core_suite_env())
        assert_success(result)
        return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}

    return check


def validate_matrix_smoke() -> dict[str, object]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def write_suite_report(payload: dict[str, object]) -> None:
    checks = payload.get("checks", []) if isinstance(payload, dict) else []
    total = payload.get("duration_seconds", 0) if isinstance(payload, dict) else 0
    lines = [
        "# Validation Suite Report",
        "",
        "## Validators Migrated",
        "",
    ]
    lines.extend(f"- `{validator}`" for validator in CORE_VALIDATORS)
    lines.extend(
        [
            "",
            "## Commands Deduplicated",
            "",
            "- Core-suite mode skips nested validator calls inside migrated validators.",
            "- Core-suite mode skips nested matchup matrix smoke calls inside migrated validators.",
            "- `validate_core_suite.py` runs matchup matrix smoke once in controlled order.",
            "",
            "## Runtime Summary",
            "",
            "- Baseline runtime before consolidation: not measured by a historical structured runner.",
            f"- Core suite duration: {total} seconds",
            "- Runtime improvement source: nested heavy validator and matchup-matrix smoke calls are skipped in core-suite mode.",
        ]
    )
    for check in checks:
        if isinstance(check, dict):
            lines.append(f"- {check.get('name')}: {check.get('duration_seconds')}s, passed={check.get('passed')}")
    lines.extend(
        [
            "",
            "## Remaining Validators Using Old Local run_command",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in remaining_local_run_command_validators())
    lines.extend(
        [
            "",
            "## Remaining Stdout-Fragile Checks",
            "",
            "- Some legacy validators outside the migrated core suite still check human-readable stdout terms.",
            "- The core suite now prefers return codes, JSON/Markdown report existence, and structured harness results where practical.",
        ]
    )
    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


def remaining_local_run_command_validators() -> list[str]:
    paths = []
    for path in sorted(Path(".").glob("validate_*.py")):
        if path.name in set(CORE_VALIDATORS) | {"validate_core_suite.py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "def run_command" in text:
            paths.append(path.as_posix())
    return paths


if __name__ == "__main__":
    main()
