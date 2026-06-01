from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.generic_card_shift_explainer import explain_card_shifts
from deck.generic_ratio_memory import load_generic_ratio_memory, record_targeted_recommendation_result
from deck.generic_ratio_recommender import recommend_ratio_adjustments
from deck.generic_targeted_retest import run_targeted_retest
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("added cards are detected", validate_added_cards),
        ("removed cards are detected", validate_removed_cards),
        ("copy increase/decrease works", validate_copy_changes),
        ("role delta is computed", validate_role_delta),
        ("rejected recommendation includes explanation", lambda: validate_rejected_recommendation_explanation(cards)),
        ("benchmark report includes card-shift section", validate_benchmark_card_shift_section),
        ("memory records helpful/harmful card movement", validate_memory_card_movement),
        ("Phase 6H validator still passes", validate_phase6h_still_passes),
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
    print("Phase 6I validation complete.")


def validate_added_cards() -> None:
    shift = sample_shift()
    if "New Interruption" not in shift["cards_added"]:
        raise AssertionError(shift)


def validate_removed_cards() -> None:
    shift = sample_shift()
    if "Old Starter" not in shift["cards_removed"]:
        raise AssertionError(shift)


def validate_copy_changes() -> None:
    shift = sample_shift()
    if shift["copy_increases"].get("Shared Extender") != 1:
        raise AssertionError(shift)
    if shift["copy_decreases"].get("Old Brick") != 1:
        raise AssertionError(shift)


def validate_role_delta() -> None:
    shift = sample_shift()
    if shift["role_delta"]["interruptions"]["gained"] < 1:
        raise AssertionError(shift)
    if shift["role_delta"]["starters_searchers"]["lost"] < 1:
        raise AssertionError(shift)


def validate_rejected_recommendation_explanation(cards: list[dict[str, Any]]) -> None:
    recommendations = recommend_ratio_adjustments("Branded", "meta", {"severity": "medium", "suspected_causes": ["interruption_shortage"]}, base_ratio())
    report = run_targeted_retest("Branded", cards, "meta", recommendations, runs_per_recommendation=1)
    rejected = report.get("rejected_recommendations", [])
    if not rejected:
        raise AssertionError(report)
    if not rejected[0].get("card_shift_explanation", {}).get("explanation"):
        raise AssertionError(rejected[0])


def validate_benchmark_card_shift_section() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    for marker in ("## Card Shift Summary", "## Accepted Card Shifts", "## Rejected Card Shifts"):
        if marker not in text:
            raise AssertionError(text[-2500:])
    summary = report.get("summary", {}).get("card_shift_summary", {})
    if "most_common_harmful_additions" not in summary:
        raise AssertionError(report.get("summary", {}))


def validate_memory_card_movement() -> None:
    retest = {
        "tested_recommendations": 2,
        "accepted_recommendation": {
            "ratio_profile": base_ratio(),
            "score": 140.0,
            "improvement": 3.0,
            "diagnosis_causes": ["interruption_shortage"],
            "card_shift_explanation": {
                "copy_increases": {"Helpful Starter": 1},
                "copy_decreases": {"Helpful Cut": 1},
            },
        },
        "rejected_recommendations": [
            {
                "recommendation": {"ratio_profile": base_ratio(), "diagnosis_causes": ["brick_pressure_high"]},
                "improvement": -1.0,
                "runs": 1,
                "legal_run_count": 1,
                "confidence": 0.5,
                "repair_success": True,
                "rejection_reason": "no_safe_improvement",
                "card_shift_explanation": {
                    "copy_increases": {"Harmful Brick": 2},
                    "copy_decreases": {"Lost Starter": 1},
                },
            }
        ],
        "best_score": 140.0,
        "baseline_score": 137.0,
        "improvement": 3.0,
    }
    record_targeted_recommendation_result("Card Shift Memory Probe", "meta", retest)
    memory = load_generic_ratio_memory("Card Shift Memory Probe", "meta")
    helpful = memory.get("helpful_card_movement_counts", {})
    harmful = memory.get("harmful_card_movement_counts", {})
    if helpful.get("additions", {}).get("Helpful Starter", 0) < 1:
        raise AssertionError(memory)
    if harmful.get("additions", {}).get("Harmful Brick", 0) < 1:
        raise AssertionError(memory)


def validate_phase6h_still_passes() -> None:
    run_command("validate_phase6h.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def sample_shift() -> dict[str, Any]:
    baseline = ["Old Starter", "Old Starter", "Shared Extender", "Old Brick", "Old Brick"]
    candidate = ["Shared Extender", "Shared Extender", "New Interruption", "Old Brick", "Fresh Payoff"]
    role_map = {
        "Old Starter": "starter",
        "Shared Extender": "extender",
        "New Interruption": "interruption",
        "Old Brick": "garnet_brick",
        "Fresh Payoff": "payoff",
    }
    return explain_card_shifts(baseline, candidate, role_map, {}, -1.5)


def print_sample(cards: list[dict[str, Any]]) -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    summary = report.get("summary", {}).get("card_shift_summary", {})
    print("SAMPLE: harmful additions:", summary.get("most_common_harmful_additions", [])[:3])
    print("SAMPLE: harmful removals:", summary.get("most_common_harmful_removals", [])[:3])
    for result in report["results"]:
        retest = result.get("targeted_retest", {})
        rejected = retest.get("rejected_recommendations", [])
        if rejected:
            print(f"SAMPLE: {result['archetype']} rejected explanation:", rejected[0]["card_shift_explanation"]["explanation"])


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
