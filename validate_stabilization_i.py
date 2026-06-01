from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from learning_signal_audit import SIGNAL_ORDER, build_learning_signal_audit, save_reports
from SystemAIYugioh.json_utils import safe_load_json


ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("audit includes every required signal", validate_signal_coverage),
        ("summary buckets are populated", validate_summary_buckets),
        ("filler-memory bias remains no-op/experimental", validate_filler_memory_bias_state),
        ("generic filler memory remains unsafe to influence", validate_filler_memory_safety),
        ("report files are saved", validate_report_save),
        ("CLI runs successfully", validate_cli_runs),
        ("documentation exists", validate_documentation),
    ]
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
    print_sample()
    print("Stabilization I validation complete.")


def validate_signal_coverage() -> None:
    report = build_learning_signal_audit()
    names = [signal.get("name") for signal in report.get("signals", [])]
    missing = [name for name in SIGNAL_ORDER if name not in names]
    if missing:
        raise AssertionError(missing)


def validate_summary_buckets() -> None:
    summary = build_learning_signal_audit().get("summary", {})
    for key in (
        "active_influences",
        "no_op_influences",
        "reporting_only_systems",
        "stale_memories",
        "noisy_memories",
        "unsafe_to_influence_memories",
        "recommendations",
    ):
        if key not in summary:
            raise AssertionError(f"missing summary key {key}")
    if "filler-memory bias" not in summary.get("no_op_influences", []):
        raise AssertionError(summary.get("no_op_influences"))


def validate_filler_memory_bias_state() -> None:
    signal = signal_by_name("filler-memory bias")
    classifications = set(signal.get("classification", []))
    if not {"no-op", "experimental"} <= classifications:
        raise AssertionError(signal)
    if signal.get("active"):
        raise AssertionError("filler-memory bias should not be active by default")


def validate_filler_memory_safety() -> None:
    signal = signal_by_name("generic_filler_memory")
    classifications = set(signal.get("classification", []))
    if "unsafe-to-influence" not in classifications or "reporting-only" not in classifications:
        raise AssertionError(signal)
    if signal.get("active"):
        raise AssertionError("generic filler memory should not directly influence selection")


def validate_report_save() -> None:
    report = build_learning_signal_audit()
    json_path, markdown_path = save_reports(report)
    saved = safe_load_json(json_path, {})
    if saved.get("report_type") != "learning_signal_audit":
        raise AssertionError(saved)
    text = markdown_path.read_text(encoding="utf-8")
    if "Learning Signal Audit" not in text or "filler-memory bias" not in text:
        raise AssertionError(markdown_path)


def validate_cli_runs() -> None:
    output = run_command("learning_signal_audit.py", "--no-save")
    if "Learning Signal Audit Complete" not in output:
        raise AssertionError(output[-2000:])


def validate_documentation() -> None:
    path = ROOT / "STABILIZATION_I_LEARNING_SIGNAL_AUDIT.md"
    if not path.exists():
        raise AssertionError(path)
    text = path.read_text(encoding="utf-8")
    for term in ("learned_card_stats", "generic_filler_memory", "filler-memory bias"):
        if term not in text:
            raise AssertionError(f"documentation missing {term}")


def signal_by_name(name: str) -> dict:
    report = build_learning_signal_audit()
    for signal in report.get("signals", []):
        if signal.get("name") == name:
            return signal
    raise AssertionError(f"missing signal {name}")


def run_command(*args: str, timeout: int = 600) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout[-4000:])
    return result.stdout


def print_sample() -> None:
    report = build_learning_signal_audit()
    summary = report.get("summary", {})
    print("Sample active influences:", summary.get("active_influences", [])[:5])
    print("Sample no-op influences:", summary.get("no_op_influences", []))
    print("Sample recommendations:", {key: summary.get("recommendations", {}).get(key) for key in ("generic_filler_memory", "filler-memory bias")})


if __name__ == "__main__":
    main()
