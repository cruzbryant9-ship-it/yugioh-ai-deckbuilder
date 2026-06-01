from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from config import settings
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.report_schema import normalize_report, report_schema_fields

ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Stabilization Pass A utilities and smoke workflow.")
    parser.add_argument("--imports-only", action="store_true", help="Only verify imports and shared helpers.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checks = [
        ("config loads", validate_config),
        ("report schema helper works", validate_report_schema),
        ("safe JSON helpers work", validate_json_safety),
        ("main scripts still import", validate_imports),
        ("no blocked-card memory corruption", validate_blocked_memory),
    ]
    if not args.imports_only:
        checks.extend(
            [
                ("smoke validators run", validate_smoke_validators),
                ("profile_runtime.py runs", validate_profile_runtime),
                ("existing Phase 5X validator still passes", validate_phase5x),
            ]
        )
    failures = []
    for label, check in checks:
        try:
            check()
            print(f"PASS: {label}")
        except Exception as exc:
            failures.append(label)
            print(f"FAIL: {label}: {exc}")
    if failures:
        raise SystemExit(1)
    print("Stabilization Pass A validation complete.")


def validate_config() -> None:
    if settings.MONTE_CARLO_DEFAULT_RUNS < settings.MONTE_CARLO_SMOKE_RUNS:
        raise AssertionError("Monte Carlo full runs must be >= smoke runs")
    if not settings.REPORT_VERSION:
        raise AssertionError("missing report version")


def validate_report_schema() -> None:
    report = normalize_report("test", {"summary": {"ok": True}})
    missing = set(report_schema_fields()) - set(report)
    if missing or report["report_type"] != "test":
        raise AssertionError(report)


def validate_json_safety() -> None:
    path = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "_stabilization_json_check.json"
    atomic_write_json(path, {"ok": True})
    loaded = safe_load_json(path, {})
    if loaded.get("ok") is not True:
        raise AssertionError(loaded)


def validate_imports() -> None:
    modules = [
        "config.settings",
        "SystemAIYugioh.report_schema",
        "SystemAIYugioh.logging_utils",
        "SystemAIYugioh.json_utils",
        "deck.opponent_probability_simulator",
        "matchup_matrix",
        "profile_runtime",
    ]
    for module in modules:
        __import__(module)


def validate_blocked_memory() -> None:
    from data.card_limits import get_blocked_card_names

    blocked = get_blocked_card_names()
    if not isinstance(blocked, set):
        raise AssertionError(type(blocked))


def validate_smoke_validators() -> None:
    output = run_command("validate_phase5m.py", "--smoke", timeout=1800)
    if "Phase 5M validation complete." not in output:
        raise AssertionError(output[-2000:])


def validate_profile_runtime() -> None:
    output = run_command("profile_runtime.py", "--smoke", "--quick", timeout=300)
    if "Runtime Profile" not in output:
        raise AssertionError(output[-2000:])


def validate_phase5x() -> None:
    output = run_command("validate_phase5x.py", timeout=3000)
    if "Phase 5X-lite validation complete." not in output:
        raise AssertionError(output[-2000:])


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
