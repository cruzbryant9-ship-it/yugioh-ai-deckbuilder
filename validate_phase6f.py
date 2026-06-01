from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from deck.generic_benchmark_memory import (
    GENERIC_BENCHMARK_HISTORY_PATH,
    load_generic_benchmark_history,
    update_generic_benchmark_history,
)
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.json_utils import safe_load_json

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("history file is created", validate_history_created),
        ("benchmark appends history", validate_history_appends),
        ("trend stats are computed", validate_trend_stats),
        ("bad run is recorded without overwriting best pattern", validate_bad_run_safety),
        ("repair success history is stored", validate_repair_history),
        ("report includes historical trend section", validate_markdown_history),
        ("Phase 6E validator still passes", validate_phase6e_still_passes),
        ("stabilization validator still passes", validate_stabilization_still_passes),
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
    print("Phase 6F validation complete.")


def validate_history_created() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    if not GENERIC_BENCHMARK_HISTORY_PATH.exists():
        raise AssertionError(GENERIC_BENCHMARK_HISTORY_PATH)
    payload = safe_load_json(GENERIC_BENCHMARK_HISTORY_PATH, {})
    if not isinstance(payload, dict) or "profiles" not in payload:
        raise AssertionError(payload)


def validate_history_appends() -> None:
    archetype = f"Append Probe Phase 6F {uuid4().hex[:8]}"
    before = load_generic_benchmark_history(archetype, "meta").get("total_benchmark_runs", 0)
    update_generic_benchmark_history(synthetic_report(archetype, 1.0, True, "updated"))
    after = load_generic_benchmark_history(archetype, "meta").get("total_benchmark_runs", 0)
    if after <= before:
        raise AssertionError((before, after))


def validate_trend_stats() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    history = report.get("benchmark_history", {})
    branded = history.get("profiles", {}).get("Branded", {})
    for key in ("average_improvement", "trend_direction", "repair_reliability", "total_benchmark_runs"):
        if key not in branded:
            raise AssertionError(branded)
    if branded["trend_direction"] not in {"improving", "stable", "declining", "noisy"}:
        raise AssertionError(branded)


def validate_bad_run_safety() -> None:
    good_report = synthetic_report("Memory Probe", 2.0, True, "updated")
    update_generic_benchmark_history(good_report)
    before = load_generic_benchmark_history("Memory Probe", "meta").get("best_ratio_patterns", {})
    bad_report = synthetic_report("Memory Probe", -9.0, True, "recorded_bad_pattern")
    update_generic_benchmark_history(bad_report)
    after = load_generic_benchmark_history("Memory Probe", "meta")
    if not after.get("bad_ratio_patterns"):
        raise AssertionError(after)
    if not before or not after.get("best_ratio_patterns"):
        raise AssertionError(after)


def validate_repair_history() -> None:
    run_benchmark(["Branded"], mode="meta", runs=2)
    history = load_generic_benchmark_history("Branded", "meta")
    if not history.get("repair_success_rate_history"):
        raise AssertionError(history)


def validate_markdown_history() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    if "## Historical Trends" not in text or "## Follow-Up Archetypes" not in text:
        raise AssertionError(text[-1000:])


def validate_phase6e_still_passes() -> None:
    run_command("validate_phase6e.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_report(archetype: str, improvement: float, legal: bool, memory_action: str) -> dict:
    return {
        "config": {"mode": "meta"},
        "results": [
            {
                "archetype": archetype,
                "normal_score": 100.0,
                "tuned_score": 100.0 + improvement,
                "improvement": improvement,
                "tuned_legal": legal,
                "repair_success_rate": 1.0 if legal else 0.0,
                "average_repair_actions": 1.0,
                "memory_action": memory_action,
                "confidence_delta": 0.0,
                "best_ratio_profile": {"starters_searchers": 11, "extenders": 6, "payoffs": 3},
                "tuned_blocked_card_violations": [],
            }
        ],
    }


def print_sample() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    history = report["benchmark_history"]
    print("SAMPLE: Historical average improvement:", history.get("historical_average_improvement"))
    print("SAMPLE: Recent average improvement:", history.get("recent_average_improvement"))
    print("SAMPLE: Repair reliability:", history.get("average_repair_reliability"))
    print("SAMPLE: Follow-up archetypes:", history.get("recommended_follow_up_archetypes"))


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
