from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from deck import advisory_influence_budget as budget_module
import deck.generic_filler_selector as selector
from filler_influence_ab_test import (
    classify_ab_result,
    run_ab_test,
    save_reports,
)
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root


ROOT = Path(__file__).resolve().parent


def main() -> None:
    with TemporaryDirectory(prefix="phase6u_gate_") as folder:
        gate_path = Path(folder) / "phase6u_gate_report.json"
        write_gate_report(gate_path)
        previous_gate_path = selector.FILLER_GATE_REPORT_PATH
        previous_enabled = budget_module.ENABLE_FILLER_MEMORY_INFLUENCE
        previous_kill = budget_module.ADVISORY_KILL_SWITCH
        try:
            selector.FILLER_GATE_REPORT_PATH = gate_path
            checks = [
                ("A/B runner runs at least 2 trials", validate_ab_runner_two_trials),
                ("control influence is off", validate_control_off),
                ("experiment influence is on", validate_experiment_on),
                ("no-op classification works", validate_noop_classification),
                ("Nibiru and Infinite Impermanence remain blocked", validate_blocked_fillers),
                ("influence remains off by default elsewhere", validate_default_off_after_run),
                ("report files are saved", validate_report_save),
                ("Phase 6T validator still passes", validate_phase6t_still_passes),
                ("matchup matrix smoke still passes", validate_matrix_smoke),
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
            print("Phase 6U validation complete.")
        finally:
            selector.FILLER_GATE_REPORT_PATH = previous_gate_path
            budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = previous_enabled
            budget_module.ADVISORY_KILL_SWITCH = previous_kill


def validate_ab_runner_two_trials() -> None:
    report = run_small_ab_report()
    if report.get("summary", {}).get("total_trials") != 2:
        raise AssertionError(report.get("summary"))
    if len(report.get("trials", [])) != 2:
        raise AssertionError("expected two trial rows")


def validate_control_off() -> None:
    report = run_small_ab_report()
    for trial in report.get("trials", []):
        if trial.get("control", {}).get("filler_memory_influence_enabled"):
            raise AssertionError(trial.get("control"))


def validate_experiment_on() -> None:
    report = run_small_ab_report()
    for trial in report.get("trials", []):
        if not trial.get("experiment", {}).get("filler_memory_influence_enabled"):
            raise AssertionError(trial.get("experiment"))


def validate_noop_classification() -> None:
    if classify_ab_result(10.0, ordering_changes=0, selection_changes=0) != "no_effect":
        raise AssertionError("positive score delta without ordering/selection change must be no_effect")
    if classify_ab_result(0.5, ordering_changes=1, selection_changes=0) != "helped":
        raise AssertionError("positive selection-changing run should be helped")
    if classify_ab_result(-0.5, ordering_changes=0, selection_changes=1) != "hurt":
        raise AssertionError("negative selection-changing run should be hurt")


def validate_blocked_fillers() -> None:
    report = run_small_ab_report()
    for trial in report.get("trials", []):
        blocked = set(
            trial.get("experiment", {})
            .get("filler_memory_influence", {})
            .get("fillers_blocked_from_influence", [])
        )
        applied = set(
            trial.get("experiment", {})
            .get("filler_memory_influence", {})
            .get("filler_memory_bias_applied", {})
        )
        for card in {"Nibiru, the Primal Being", "Infinite Impermanence"}:
            if card not in blocked:
                raise AssertionError({"missing_blocked": card, "blocked": sorted(blocked)})
            if card in applied:
                raise AssertionError({"applied_to_blocked": card, "applied": sorted(applied)})


def validate_default_off_after_run() -> None:
    budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = False
    budget_module.ADVISORY_KILL_SWITCH = False
    run_small_ab_report()
    if budget_module.ENABLE_FILLER_MEMORY_INFLUENCE:
        raise AssertionError("A/B runner leaked the filler-memory influence module flag")


def validate_report_save() -> None:
    report = run_small_ab_report()
    latest_json, markdown_path = save_reports(report)
    saved = safe_load_json(latest_json, {})
    if saved.get("report_type") != "filler_influence_ab_test":
        raise AssertionError(saved)
    if not markdown_path.exists() or "Filler Influence A/B Test" not in markdown_path.read_text(encoding="utf-8"):
        raise AssertionError(markdown_path)


def validate_phase6t_still_passes() -> None:
    output = run_command("validate_phase6t.py", timeout=1800)
    if "Phase 6T validation complete." not in output:
        raise AssertionError(output[-2500:])


def validate_matrix_smoke() -> None:
    with temporary_isolated_memory_root("phase6u_matrix_"):
        output = run_command(
            "matchup_matrix.py",
            "--archetype",
            "Blue-Eyes",
            "--mode",
            "meta",
            "--runs-per-cell",
            "1",
            "--use-curated-opponents",
            "--smoke",
            timeout=1800,
        )
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


_SMALL_REPORT_CACHE: dict[str, Any] | None = None


def run_small_ab_report() -> dict[str, Any]:
    global _SMALL_REPORT_CACHE
    if _SMALL_REPORT_CACHE is not None:
        return _SMALL_REPORT_CACHE
    provenance = provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)
    with temporary_isolated_memory_root("phase6u_ab_"):
        _SMALL_REPORT_CACHE = run_ab_test(
            ["Runick"],
            mode="meta",
            runs=1,
            trials=2,
            provenance=provenance,
            refresh_gate_report=False,
        )
    return _SMALL_REPORT_CACHE


def write_gate_report(path: Path) -> None:
    rows = []
    for name, holdout in {
        "Ash Blossom & Joyous Spring": True,
        "Effect Veiler": True,
        "Ghost Belle & Haunted Mansion": True,
        "Nibiru, the Primal Being": False,
        "Infinite Impermanence": False,
    }.items():
        rows.append({"card": name, "eligible": True, "holdout_passed": holdout, "activation_ready": holdout})
    atomic_write_json(
        path,
        {
            "summary": {
                "activation_ready_fillers": [
                    "Ash Blossom & Joyous Spring",
                    "Effect Veiler",
                    "Ghost Belle & Haunted Mansion",
                ],
                "activation_ready_count": 3,
            },
            "eligible_signals": rows,
        },
    )


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
    report = run_small_ab_report()
    summary = report.get("summary", {})
    print("Sample A/B classification:", summary.get("overall_classification"))
    print("Sample ordering changes:", summary.get("ordering_change_count"))
    print("Sample selection changes:", summary.get("selection_change_count"))


if __name__ == "__main__":
    main()
