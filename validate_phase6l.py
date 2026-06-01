from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.generic_diff_index import (
    GENERIC_DIFF_INDEX_PATH,
    build_cross_archetype_diff_index,
    build_diff_index_warnings,
    generic_diff_index_path,
    load_generic_diff_index,
    update_cross_archetype_diff_index,
)
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("phase6l_memory_"):
        run_checks()


def run_checks() -> None:
    checks = [
        ("diff index is created", validate_index_created),
        ("helpful/harmful card movement counts update", validate_card_counts),
        ("package movement counts update", validate_package_counts),
        ("repeated risk flags update", validate_risk_flags),
        ("benchmark report includes diff index section", validate_benchmark_diff_index_section),
        ("index warning appears for known harmful movement", validate_index_warning),
        ("Phase 6K validator still passes", validate_phase6k_still_passes),
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
    print("Phase 6L validation complete.")


def validate_index_created() -> None:
    update_cross_archetype_diff_index([synthetic_result("Index Probe")], provenance=validator_provenance())
    if not generic_diff_index_path().exists():
        raise AssertionError(generic_diff_index_path())


def validate_card_counts() -> None:
    index = build_cross_archetype_diff_index([synthetic_result("Card Probe")])
    helpful = index["helpful_cards"]["additions"].get("Helpful Add", {})
    harmful = index["harmful_cards"]["additions"].get("Harmful Add", {})
    if helpful.get("count", 0) < 1 or harmful.get("count", 0) < 1:
        raise AssertionError(index)


def validate_package_counts() -> None:
    index = build_cross_archetype_diff_index([synthetic_result("Package Probe")])
    helpful = index["helpful_package_movements"]["gains"].get("starters_searchers:+1", {})
    harmful = index["harmful_package_movements"]["losses"].get("interruptions:-1", {})
    if helpful.get("count", 0) < 1 or harmful.get("count", 0) < 1:
        raise AssertionError(index["helpful_package_movements"])


def validate_risk_flags() -> None:
    index = build_cross_archetype_diff_index([synthetic_result("Risk Probe")])
    if index["recurring_risk_flags"].get("package_instability", {}).get("count", 0) < 1:
        raise AssertionError(index["recurring_risk_flags"])


def validate_benchmark_diff_index_section() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=1, provenance=validator_provenance())
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    for marker in ("## Cross-Archetype Diff Index", "Top Harmful Additions", "Common Risk Flags", "Archetypes Needing Review"):
        if marker not in text:
            raise AssertionError(text[-3000:])


def validate_index_warning() -> None:
    historical = build_cross_archetype_diff_index([synthetic_result("Warning Probe")])
    result = {
        "archetype": "Warning Probe",
        "targeted_retest": {
            "rejected_recommendations": [
                {
                    "package_replay_report": {
                        "copy_increases": {"Harmful Add": 1},
                        "copy_decreases": {},
                        "package_gains_losses": {"interruptions": -1},
                    },
                    "improvement": -1.0,
                    "runs": 1,
                    "legal_run_count": 1,
                    "confidence": 0.5,
                    "repair_success": True,
                    "rejection_reason": "no_safe_improvement",
                }
            ]
        },
    }
    warnings = build_diff_index_warnings(result, historical)
    if not any("Harmful Add" in warning for warning in warnings):
        raise AssertionError(warnings)


def validate_phase6k_still_passes() -> None:
    run_command("validate_phase6k.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_result(archetype: str) -> dict:
    return {
        "archetype": archetype,
        "provenance": validator_provenance(),
        "normal_repair_actions": ["filled missing main slot with starter"],
        "tuned_repair_actions": ["added Extra Deck repair card"],
        "targeted_retest": {
            "accepted_recommendation": {
                "improvement": 2.5,
                "card_shift_explanation": {
                    "copy_increases": {"Helpful Add": 1},
                    "copy_decreases": {"Helpful Remove": 1},
                },
                "package_replay_report": {
                    "copy_increases": {"Helpful Add": 1},
                    "copy_decreases": {"Helpful Remove": 1},
                    "package_gains_losses": {"starters_searchers": 1},
                    "risk_flags": [],
                    "score_delta": 2.5,
                },
            },
            "rejected_recommendations": [
                {
                    "improvement": -3.0,
                    "runs": 1,
                    "legal_run_count": 1,
                    "confidence": 0.5,
                    "repair_success": True,
                    "rejection_reason": "no_safe_improvement",
                    "card_shift_explanation": {
                        "copy_increases": {"Harmful Add": 1},
                        "copy_decreases": {"Harmful Remove": 1},
                    },
                    "package_replay_report": {
                        "copy_increases": {"Harmful Add": 1},
                        "copy_decreases": {"Harmful Remove": 1},
                        "package_gains_losses": {"interruptions": -1},
                        "risk_flags": ["package_instability"],
                        "score_delta": -3.0,
                    },
                }
            ],
        },
    }


def print_sample() -> None:
    report = run_benchmark(["Branded", "Kashtira", "Runick"], mode="meta", runs=1, provenance=validator_provenance())
    save_reports(report)
    index = load_generic_diff_index()
    summary = report.get("summary", {}).get("diff_index_summary", {})
    print("SAMPLE: top harmful additions:", summary.get("top_harmful_additions", [])[:3])
    print("SAMPLE: common risk flags:", summary.get("common_risk_flags", [])[:3])
    print("SAMPLE: indexed archetypes:", sorted(index.get("archetype_patterns", {}).keys())[:5])


def validator_provenance() -> dict:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
