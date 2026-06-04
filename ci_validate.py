from __future__ import annotations

import argparse
from pathlib import Path

from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "ci_validate.json"
CI_COMMANDS = (
    "validate_core_suite.py",
    "validate_stabilization_n.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight project validation for CI.")
    parser.add_argument("--dry-run", action="store_true", help="Print and validate the command plan without running validators.")
    args = parser.parse_args()
    if args.dry_run:
        print("CI validation command plan:")
        for command in CI_COMMANDS:
            print(f"- python {command}")
        return

    checks = [(command, validator_check(command)) for command in CI_COMMANDS]
    result = run_checks("ci_validate", checks, json_path=VALIDATION_JSON)
    if not result.passed:
        raise SystemExit(1)
    print("CI validation complete.")


def validator_check(script: str):
    def check() -> dict[str, object]:
        result = run_python(script, timeout=4200)
        assert_success(result)
        return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}

    return check


if __name__ == "__main__":
    main()
