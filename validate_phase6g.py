from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.generic_benchmark_memory import load_generic_benchmark_history, update_generic_benchmark_history
from deck.generic_trend_diagnosis import diagnose_generic_trend
from deck.generic_tuner import tune_generic_deck
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("declining archetype receives diagnosis", validate_declining_diagnosis),
        ("low starter count triggers starter_density_low", validate_low_starter_cause),
        ("high brick count triggers brick_pressure_high", validate_brick_pressure_cause),
        ("repair dependency triggers repair_dependency_high", validate_repair_dependency_cause),
        ("diagnosis is stored in benchmark memory", validate_memory_stores_diagnosis),
        ("tuner can read diagnosis without crashing", lambda: validate_tuner_reads_diagnosis(cards)),
        ("benchmark report includes diagnosis", validate_benchmark_report_diagnosis),
        ("Phase 6F validator still passes", validate_phase6f_still_passes),
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
    print("Phase 6G validation complete.")


def validate_declining_diagnosis() -> None:
    diagnosis = diagnose_generic_trend("Decliner", "meta", synthetic_history("declining"), synthetic_result(starters=6, bricks=5, improvement=-2.0))
    if diagnosis["severity"] not in {"medium", "high"} or not diagnosis["suspected_causes"]:
        raise AssertionError(diagnosis)


def validate_low_starter_cause() -> None:
    diagnosis = diagnose_generic_trend("Starter Probe", "meta", synthetic_history(), synthetic_result(starters=5, extenders=6, interruptions=8))
    if "starter_density_low" not in diagnosis["suspected_causes"]:
        raise AssertionError(diagnosis)


def validate_brick_pressure_cause() -> None:
    diagnosis = diagnose_generic_trend("Brick Probe", "meta", synthetic_history(), synthetic_result(starters=10, bricks=7, max_bricks=4))
    if "brick_pressure_high" not in diagnosis["suspected_causes"]:
        raise AssertionError(diagnosis)


def validate_repair_dependency_cause() -> None:
    latest = synthetic_result(starters=10, bricks=2)
    latest["repair_success_rate"] = 0.35
    latest["average_repair_actions"] = 3.5
    diagnosis = diagnose_generic_trend("Repair Probe", "meta", synthetic_history(), latest)
    if "repair_dependency_high" not in diagnosis["suspected_causes"]:
        raise AssertionError(diagnosis)


def validate_memory_stores_diagnosis() -> None:
    update_generic_benchmark_history(synthetic_report("Diagnosis Probe", synthetic_result(starters=5, bricks=6, improvement=-1.0)))
    profile = load_generic_benchmark_history("Diagnosis Probe", "meta")
    diagnosis = profile.get("latest_diagnosis", {})
    if not diagnosis or "starter_density_low" not in diagnosis.get("suspected_causes", []):
        raise AssertionError(profile)


def validate_tuner_reads_diagnosis(cards: list[dict[str, Any]]) -> None:
    update_generic_benchmark_history(synthetic_report("Branded", synthetic_result(starters=5, bricks=5, improvement=-0.5)))
    report = tune_generic_deck("Branded", cards, mode="meta", runs=2, update_memory=False)
    if "diagnosis_influenced_tuning" not in report or "diagnosis_bias" not in report:
        raise AssertionError(report)


def validate_benchmark_report_diagnosis() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    if "## Trend Diagnosis" not in text or "Suspected Causes" not in text:
        raise AssertionError(text[-1500:])


def validate_phase6f_still_passes() -> None:
    run_command("validate_phase6f.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_history(trend: str = "stable") -> dict[str, Any]:
    return {
        "trend_direction": trend,
        "total_benchmark_runs": 4,
        "bad_ratio_patterns": [
            {"ratio_profile": {"starters_searchers": 6, "extenders": 4, "payoffs": 6}, "reason": "negative_improvement"},
            {"ratio_profile": {"starters_searchers": 6, "extenders": 4, "payoffs": 6}, "reason": "negative_improvement"},
        ],
        "history": [
            {"improvement": -0.5, "confidence_delta": -0.12, "repair_success_rate": 0.7, "average_repair_actions": 2.0, "tuned_package_counts": {"starters_searchers": 6, "extenders": 4, "garnet_brick": 5}},
            {"improvement": -1.0, "confidence_delta": -0.09, "repair_success_rate": 0.6, "average_repair_actions": 2.5, "tuned_package_counts": {"starters_searchers": 8, "extenders": 3, "garnet_brick": 4}},
            {"improvement": -0.25, "confidence_delta": -0.11, "repair_success_rate": 0.8, "average_repair_actions": 1.0, "tuned_package_counts": {"starters_searchers": 5, "extenders": 7, "garnet_brick": 6}},
        ],
    }


def synthetic_result(
    starters: int = 10,
    extenders: int = 6,
    interruptions: int = 8,
    board_breakers: int = 2,
    bricks: int = 2,
    max_bricks: int = 4,
    improvement: float = 0.0,
) -> dict[str, Any]:
    return {
        "archetype": "Synthetic",
        "normal_score": 100.0,
        "tuned_score": 100.0 + improvement,
        "improvement": improvement,
        "tuned_legal": True,
        "confidence_delta": -0.1 if improvement < 0 else 0.0,
        "tuned_package_counts": {
            "starters_searchers": starters,
            "extenders": extenders,
            "interruptions": interruptions,
            "board_breakers": board_breakers,
            "garnet_brick": bricks,
        },
        "best_ratio_profile": {
            "starters_searchers": starters,
            "extenders": extenders,
            "interruptions": interruptions,
            "board_breakers": board_breakers,
            "payoffs": 3,
            "max_bricks": max_bricks,
        },
        "repair_success_rate": 1.0,
        "average_repair_actions": 0.0,
        "variant_count": 3,
        "memory_action": "updated" if improvement >= 0 else "recorded_bad_pattern",
        "tuned_blocked_card_violations": [],
    }


def synthetic_report(archetype: str, result: dict[str, Any]) -> dict[str, Any]:
    row = dict(result)
    row["archetype"] = archetype
    return {"config": {"mode": "meta"}, "results": [row]}


def print_sample() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    for archetype, profile in sorted(report.get("benchmark_history", {}).get("profiles", {}).items()):
        diagnosis = profile.get("latest_diagnosis", {})
        print(f"SAMPLE: {archetype} diagnosis severity:", diagnosis.get("severity"))
        print(f"SAMPLE: {archetype} causes:", diagnosis.get("suspected_causes", []))
        print(f"SAMPLE: {archetype} adjustments:", diagnosis.get("recommended_adjustments", [])[:2])


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
