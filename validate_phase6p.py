from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.generic_filler_impact import analyze_filler_impact
from deck.generic_filler_memory import load_generic_filler_memory, update_generic_filler_memory
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("phase6p_memory_"):
        checks = [
            ("filler impact classification works", validate_positive_classification),
            ("completion-only filler is detected", validate_completion_only_classification),
            ("performance-negative filler is recorded without rejection", validate_negative_classification),
            ("filler memory writes safely with provenance", validate_filler_memory),
            ("contextual filler respects blocked cards/copy limits", validate_phase6o_legality_checks),
            ("Runick still completes to 40", validate_runick_completion),
            ("benchmark includes filler impact and memory updates", validate_benchmark_filler_impact),
            ("Phase 6O validator still passes", validate_phase6o_still_passes),
            ("Stabilization G validator still passes", validate_stabilization_g_still_passes),
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
        print("Phase 6P validation complete.")


def validate_positive_classification() -> None:
    report = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.5, "main_count": 39, "package_counts": {"interruptions": 2}},
        filler_result("Ash Blossom & Joyous Spring", score=101.2, confidence=0.6),
    )
    if report["impact_classification"].get("Ash Blossom & Joyous Spring") != "performance_positive":
        raise AssertionError(report)
    if "Ash Blossom & Joyous Spring" not in report["performance_positive_fillers"]:
        raise AssertionError(report)


def validate_completion_only_classification() -> None:
    report = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.5, "main_count": 39, "package_counts": {}},
        filler_result("Infinite Impermanence", score=100.1, confidence=0.55),
    )
    if report["impact_classification"].get("Infinite Impermanence") != "completion_only":
        raise AssertionError(report)
    if report["completion_required"] is not True:
        raise AssertionError(report)


def validate_negative_classification() -> None:
    report = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.6, "main_count": 40, "package_counts": {}},
        filler_result("D.D. Crow", score=99.2, confidence=0.6, pre_count=40),
    )
    if report["impact_classification"].get("D.D. Crow") != "performance_negative":
        raise AssertionError(report)
    if "D.D. Crow" not in report["negative_fillers"]:
        raise AssertionError(report)


def validate_filler_memory() -> None:
    impact = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.5, "main_count": 39, "package_counts": {}},
        filler_result("Infinite Impermanence", score=100.2, confidence=0.56),
    )
    update_generic_filler_memory("Probe", "meta", [impact], provenance=validator_provenance())
    memory = load_generic_filler_memory("Probe", "meta")
    entry = memory.get("fillers", {}).get("Infinite Impermanence", {})
    if entry.get("times_used", 0) < 1 or entry.get("completion_only_count", 0) < 1:
        raise AssertionError(memory)
    if not memory.get("last_update_provenance", {}).get("validator_generated"):
        raise AssertionError(memory)


def validate_phase6o_legality_checks() -> None:
    import validate_phase6o as phase6o

    phase6o.validate_blocked_fillers()
    phase6o.validate_copy_limits()


def validate_runick_completion() -> None:
    cards = CardDatabase().load_cards()
    deck, report = build_generic_deck("Runick", cards, mode="meta", use_ratio_memory=False)
    main, _extra = split_deck(deck)
    if len(main) != 40:
        raise AssertionError(report)


def validate_benchmark_filler_impact() -> None:
    from generic_archetype_benchmark import run_benchmark

    report = run_benchmark(["Runick"], mode="meta", runs=1, provenance=validator_provenance())
    summary = report.get("summary", {})
    if "filler_impact_summary" not in summary or "filler_impact_classification_summary" not in summary:
        raise AssertionError(summary)
    result = report.get("results", [{}])[0]
    if result.get("contextual_filler_usage_count") and not result.get("filler_impact_reports"):
        raise AssertionError(result)
    if result.get("filler_impact_reports") and result.get("filler_memory_update") not in {"updated", "skipped"}:
        raise AssertionError(result)


def validate_phase6o_still_passes() -> None:
    import validate_phase6o as phase6o

    phase6o.validate_interruption_pressure()
    phase6o.validate_spell_trap_texture()
    phase6o.validate_benchmark_metadata()


def validate_stabilization_g_still_passes() -> None:
    import validate_stabilization_g as stab_g

    stab_g.validate_isolated_memory_writes()
    stab_g.validate_phase6l_keeps_production_memory_clean()
    stab_g.validate_provenance_metadata()
    stab_g.validate_validator_records_ignored_in_production()
    stab_g.validate_rejection_cause_classification()
    stab_g.validate_legality_rejection_not_harmful()
    stab_g.validate_repair_idempotence()
    stab_g.validate_advisory_budget()


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def filler_result(name: str, score: float, confidence: float, pre_count: int = 39) -> dict[str, Any]:
    return {
        "score": score,
        "confidence": confidence,
        "main_count": 40,
        "package_counts": {"interruptions": 3},
        "selected_fillers": [name],
        "filler_roles": {"counts": {"handtrap": 1}, "by_card": {name: "handtrap"}},
        "contextual_filler_used": True,
        "repair_used": pre_count < 40,
        "pre_contextual_filler_main_count": pre_count,
        "quota_warnings": [],
        "remaining_warnings": [],
    }


def validator_provenance() -> dict[str, Any]:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True, confidence_score=1.0, improvement=0.0)


def print_sample() -> None:
    cards = CardDatabase().load_cards()
    deck, report = build_generic_deck("Runick", cards, mode="meta", use_ratio_memory=False)
    main, _extra = split_deck(deck)
    print("SAMPLE: Runick main count:", len(main))
    print("SAMPLE: Runick selected fillers:", report.get("selected_fillers", [])[:5])


def run_command(*args: str, timeout: int = 180) -> str:
    env = os.environ.copy()
    env.pop("YUGIOH_AI_MEMORY_ROOT", None)
    env.pop("YUGIOH_AI_TEST_MODE", None)
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
