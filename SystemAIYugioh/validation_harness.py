from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CORE_SUITE_ENV = "YUGIOH_CORE_VALIDATION_SUITE"


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def combined_output(self) -> str:
        return self.stdout + (("\n" + self.stderr) if self.stderr else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 4),
            "stdout_tail": self.stdout[-2000:],
            "stderr_tail": self.stderr[-2000:],
        }


@dataclass
class CheckResult:
    name: str
    passed: bool
    duration_seconds: float
    details: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "duration_seconds": round(self.duration_seconds, 4),
            "details": self.details,
            "error": self.error,
        }


@dataclass
class ValidationResult:
    validator: str
    passed: bool
    checks: list[CheckResult]
    duration_seconds: float
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator": self.validator,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "duration_seconds": round(self.duration_seconds, 4),
            "created_at_utc": self.created_at_utc,
        }


def in_core_suite() -> bool:
    return os.environ.get(CORE_SUITE_ENV) == "1"


def run_command(*args: str, timeout: int = 900, cwd: Path | str = ROOT, env: dict[str, str] | None = None) -> CommandResult:
    command = [str(arg) for arg in args]
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
    )
    return CommandResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=time.perf_counter() - started,
    )


def run_python(*args: str, timeout: int = 900, cwd: Path | str = ROOT, env: dict[str, str] | None = None) -> CommandResult:
    return run_command(sys.executable, *args, timeout=timeout, cwd=cwd, env=env)


def assert_success(result: CommandResult, expected_terms: tuple[str, ...] = ()) -> str:
    if result.returncode != 0:
        raise AssertionError(result.combined_output[-4000:])
    for term in expected_terms:
        if term not in result.combined_output:
            raise AssertionError(f"missing expected output term {term!r}: {result.combined_output[-4000:]}")
    return result.combined_output


def assert_json_report_exists(path: str | Path, required_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    report_path = ROOT / path if not Path(path).is_absolute() else Path(path)
    if not report_path.exists():
        raise AssertionError(report_path)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid json report {report_path}: {exc}") from exc
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise AssertionError(f"{report_path} missing keys {missing}")
    return payload


def assert_markdown_report_exists(path: str | Path, required_terms: tuple[str, ...] = ()) -> str:
    report_path = ROOT / path if not Path(path).is_absolute() else Path(path)
    if not report_path.exists():
        raise AssertionError(report_path)
    text = report_path.read_text(encoding="utf-8")
    missing = [term for term in required_terms if term not in text]
    if missing:
        raise AssertionError(f"{report_path} missing terms {missing}")
    return text


def smoke_matchup_matrix(timeout: int = 1800, extra_args: tuple[str, ...] = ()) -> CommandResult:
    return run_python(
        "matchup_matrix.py",
        "--archetype",
        "Blue-Eyes",
        "--mode",
        "meta",
        "--runs-per-cell",
        "1",
        "--use-curated-opponents",
        "--smoke",
        *extra_args,
        timeout=timeout,
    )


def run_checks(
    validator: str,
    checks: list[tuple[str, Callable[[], Any]]],
    *,
    json_path: str | Path | None = None,
    emit_json: bool = False,
) -> ValidationResult:
    started = time.perf_counter()
    check_results: list[CheckResult] = []
    for label, check in checks:
        check_started = time.perf_counter()
        try:
            details = check()
            check_results.append(CheckResult(label, True, time.perf_counter() - check_started, details=details))
            print(f"PASS: {label}")
        except Exception as exc:
            check_results.append(CheckResult(label, False, time.perf_counter() - check_started, error=str(exc)))
            print(f"FAIL: {label}: {exc}")
    result = ValidationResult(
        validator=validator,
        passed=all(check.passed for check in check_results),
        checks=check_results,
        duration_seconds=time.perf_counter() - started,
    )
    if json_path:
        output_path = ROOT / json_path if not Path(json_path).is_absolute() else Path(json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    if emit_json:
        print(json.dumps(result.to_dict(), sort_keys=True))
    return result


def core_suite_env() -> dict[str, str]:
    env = dict(os.environ)
    env[CORE_SUITE_ENV] = "1"
    return env
