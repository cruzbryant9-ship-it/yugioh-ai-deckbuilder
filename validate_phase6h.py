from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.generic_benchmark_memory import load_generic_benchmark_history
from deck.generic_ratio_memory import load_generic_ratio_memory, record_targeted_recommendation_result, save_generic_ratio_memory
from deck.generic_ratio_recommender import recommend_ratio_adjustments
from deck.generic_targeted_retest import run_targeted_retest
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("interruption_shortage recommends more interruptions", validate_interruption_recommendation),
        ("starter_density_low recommends more starters/searchers", validate_starter_recommendation),
        ("payoff_overfill recommends fewer payoffs", validate_payoff_recommendation),
        ("targeted retest runs at least one recommendation", lambda: validate_targeted_retest_runs(cards)),
        ("unsafe recommendation is rejected", lambda: validate_unsafe_recommendation_rejected(cards)),
        ("accepted recommendation updates memory safely", validate_accepted_recommendation_memory),
        ("benchmark report includes targeted retest section", validate_benchmark_report_targeted_section),
        ("Phase 6G validator still passes", validate_phase6g_still_passes),
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
    print_sample(cards)
    print("Phase 6H validation complete.")


def validate_interruption_recommendation() -> None:
    current = base_ratio()
    recommendations = recommend_ratio_adjustments("Probe", "meta", diagnosis(["interruption_shortage"]), current)["recommendations"]
    if not any(row["ratio_profile"].get("interruptions", 0) > current["interruptions"] for row in recommendations):
        raise AssertionError(recommendations)


def validate_starter_recommendation() -> None:
    current = base_ratio()
    recommendations = recommend_ratio_adjustments("Probe", "meta", diagnosis(["starter_density_low"]), current)["recommendations"]
    if not any(row["ratio_profile"].get("starters_searchers", 0) > current["starters_searchers"] for row in recommendations):
        raise AssertionError(recommendations)


def validate_payoff_recommendation() -> None:
    current = base_ratio()
    recommendations = recommend_ratio_adjustments("Probe", "meta", diagnosis(["payoff_overfill"]), current)["recommendations"]
    if not any(row["ratio_profile"].get("payoffs", 99) < current["payoffs"] for row in recommendations):
        raise AssertionError(recommendations)


def validate_targeted_retest_runs(cards: list[dict[str, Any]]) -> None:
    recommendations = recommend_ratio_adjustments("Branded", "meta", diagnosis(["interruption_shortage"]), base_ratio())
    report = run_targeted_retest("Branded", cards, "meta", recommendations, runs_per_recommendation=1)
    if report["tested_recommendations"] < 1 or not report["targeted_retest_used"]:
        raise AssertionError(report)


def validate_unsafe_recommendation_rejected(cards: list[dict[str, Any]]) -> None:
    save_generic_ratio_memory(
        "Retest Safety Probe",
        "meta",
        {
            "best_result": {"ratio_profile": base_ratio(), "score": 999.0, "confidence": 0.5},
            "results": [],
            "average_score": 999.0,
        },
    )
    recommendation = {
        "recommendations": [
            {
                "ratio_profile": {"starters_searchers": 6, "extenders": 3, "payoffs": 16, "interruptions": 4, "board_breakers": 0, "recovery": 0, "max_bricks": 6},
                "reason": "Unsafe stress recommendation.",
                "diagnosis_causes": ["payoff_overfill"],
                "risk_level": "high",
            }
        ]
    }
    report = run_targeted_retest("Retest Safety Probe", cards, "meta", recommendation, runs_per_recommendation=1)
    if report.get("accepted_recommendation") or not report.get("rejected_recommendations"):
        raise AssertionError(report)


def validate_accepted_recommendation_memory() -> None:
    retest = {
        "tested_recommendations": 1,
        "accepted_recommendation": {
            "ratio_profile": {"starters_searchers": 12, "extenders": 6, "payoffs": 3, "interruptions": 9, "board_breakers": 1, "recovery": 2, "max_bricks": 3},
            "score": 123.0,
            "improvement": 2.0,
            "reason": "Validation accepted recommendation.",
            "diagnosis_causes": ["interruption_shortage"],
            "risk_level": "low",
        },
        "rejected_recommendations": [],
        "best_score": 123.0,
        "baseline_score": 121.0,
        "improvement": 2.0,
    }
    record_targeted_recommendation_result("Targeted Memory Probe", "meta", retest)
    memory = load_generic_ratio_memory("Targeted Memory Probe", "meta")
    if not memory.get("accepted_targeted_recommendations") or memory.get("recommendation_success_rate", 0) <= 0:
        raise AssertionError(memory)
    mapping = memory.get("diagnosis_adjustment_success", {}).get("interruption_shortage", {})
    if mapping.get("accepted", 0) <= 0:
        raise AssertionError(memory)


def validate_benchmark_report_targeted_section() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    if "## Targeted Retests" not in text or "Accepted Ratio" not in text:
        raise AssertionError(text[-2000:])
    if "targeted_retest_count" not in report["summary"]:
        raise AssertionError(report["summary"])
    for result in report["results"]:
        if "targeted_retest" not in result:
            raise AssertionError(result)
    branded = load_generic_benchmark_history("Branded", "meta")
    if not branded.get("latest_targeted_retest"):
        raise AssertionError(branded)


def validate_phase6g_still_passes() -> None:
    run_command("validate_phase6g.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample(cards: list[dict[str, Any]]) -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    for result in report["results"]:
        recommendations = result.get("ratio_recommendations", [])
        retest = result.get("targeted_retest", {})
        print(f"SAMPLE: {result['archetype']} recommendation count:", len(recommendations))
        if recommendations:
            print(f"SAMPLE: {result['archetype']} first recommendation:", recommendations[0]["reason"])
        print(f"SAMPLE: {result['archetype']} retest accepted:", bool(retest.get("accepted_recommendation")))
        print(f"SAMPLE: {result['archetype']} retest delta:", retest.get("improvement", 0))


def diagnosis(causes: list[str]) -> dict[str, Any]:
    return {
        "severity": "medium",
        "suspected_causes": causes,
        "recommended_adjustments": [],
    }


def base_ratio() -> dict[str, int]:
    return {
        "starters_searchers": 11,
        "extenders": 6,
        "payoffs": 3,
        "recovery": 2,
        "interruptions": 8,
        "board_breakers": 2,
        "max_bricks": 4,
    }


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
