from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.advisory_influence_budget import AdvisoryInfluenceBudget
import deck.advisory_influence_budget as budget_module
from deck.generic_filler_impact import analyze_filler_impact
from deck.generic_filler_memory import (
    build_cross_archetype_index,
    completion_bias_flag,
    is_filler_signal_eligible,
    load_generic_filler_memory,
    migrate_filler_memory,
    update_generic_filler_memory,
)
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("stabilization_h_memory_"):
        checks = [
            ("multi-card filler events do not assign full credit", validate_shared_attribution),
            ("single-card filler events receive full attribution", validate_single_card_attribution),
            ("completion-only suppression works", validate_completion_suppression),
            ("archetype-first storage works", validate_archetype_first_storage),
            ("Runick-only evidence does not create global signals", validate_runick_only_not_global),
            ("support thresholds block weak signals", validate_support_thresholds),
            ("advisory budget tracks filler memory source", validate_budget_source),
            ("kill switch disables all advisory sources", validate_budget_kill_switch),
            ("generic_filler_memory migration succeeds", validate_memory_migration),
            ("Phase 6P validator still passes", validate_phase6p_still_passes),
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
        print("Stabilization H validation complete.")


def validate_shared_attribution() -> None:
    report = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.5, "main_count": 37, "package_counts": {}},
        filler_result(["Infinite Impermanence", "Ash Blossom & Joyous Spring", "Droll & Lock Bird"], score=103, confidence=0.6),
    )
    if report.get("attribution_model") != "shared" or report.get("attribution_confidence") >= 1:
        raise AssertionError(report)
    if report.get("attributed_score_delta") >= report.get("score_delta"):
        raise AssertionError(report)
    if set(report.get("impact_classification", {}).values()) != {"indeterminate"}:
        raise AssertionError(report)


def validate_single_card_attribution() -> None:
    report = analyze_filler_impact(
        "Probe",
        "meta",
        {"score": 100, "confidence": 0.5, "main_count": 39, "package_counts": {}},
        filler_result(["Infinite Impermanence"], score=101.2, confidence=0.6),
    )
    if report.get("attribution_model") != "single_card" or report.get("attribution_confidence") != 1.0:
        raise AssertionError(report)
    if report.get("impact_classification", {}).get("Infinite Impermanence") != "performance_positive":
        raise AssertionError(report)


def validate_completion_suppression() -> None:
    entry = {"times_used": 4, "completion_only_count": 2, "legal_observation_count": 4, "affected_archetypes": ["Probe", "Other"], "archetype_breadth": 2}
    if not completion_bias_flag(entry):
        raise AssertionError(entry)
    status = is_filler_signal_eligible(entry, provenance={"validator_generated": False})
    if status:
        raise AssertionError(entry)


def validate_archetype_first_storage() -> None:
    update_generic_filler_memory("Runick", "meta", [completion_impact("Infinite Impermanence", "completion_only")], provenance=production_like_provenance())
    memory = load_generic_filler_memory()
    if "runick" not in memory.get("profiles", {}) or "meta" not in memory["profiles"]["runick"]:
        raise AssertionError(memory)


def validate_runick_only_not_global() -> None:
    memory = load_generic_filler_memory()
    cross = memory.get("cross_archetype_index", {})
    if "Infinite Impermanence" in cross:
        raise AssertionError(cross)


def validate_support_thresholds() -> None:
    weak = {"times_used": 1, "legal_observation_count": 1, "affected_archetypes": ["Probe", "Other"], "archetype_breadth": 2}
    if is_filler_signal_eligible(weak, provenance={"validator_generated": False}):
        raise AssertionError(weak)
    illegal = {"times_used": 3, "legal_observation_count": 2, "affected_archetypes": ["Probe", "Other"], "archetype_breadth": 2}
    if is_filler_signal_eligible(illegal, provenance={"validator_generated": False}):
        raise AssertionError(illegal)


def validate_budget_source() -> None:
    budget = AdvisoryInfluenceBudget()
    budget.apply("diagnosis", 0.05)
    budget.apply("diff_index", 0.04)
    budget.apply("filler_memory", 0.04)
    summary = budget.summary()
    for source in ("diagnosis", "diff_index", "filler_memory"):
        if source not in summary.get("used_by_source", {}):
            raise AssertionError(summary)


def validate_budget_kill_switch() -> None:
    previous = budget_module.ADVISORY_KILL_SWITCH
    try:
        budget_module.ADVISORY_KILL_SWITCH = True
        budget = AdvisoryInfluenceBudget()
        if budget.apply("diagnosis", 0.05) or budget.apply("diff_index", 0.05) or budget.apply("filler_memory", 0.05):
            raise AssertionError(budget.summary())
        if budget.summary().get("enabled"):
            raise AssertionError(budget.summary())
    finally:
        budget_module.ADVISORY_KILL_SWITCH = previous


def validate_memory_migration() -> None:
    old = {
        "version": 1,
        "profiles": {
            "runick": {
                "meta": {
                    "fillers": {
                        "Infinite Impermanence": {
                            "times_used": 3,
                            "completion_only_count": 2,
                            "performance_positive_count": 1,
                            "average_score_delta": 1.0,
                        }
                    }
                }
            }
        },
    }
    migrated = migrate_filler_memory(old)
    entry = migrated["profiles"]["runick"]["meta"]["fillers"]["Infinite Impermanence"]
    if "eligibility" not in entry or "completion_bias_flag" not in entry:
        raise AssertionError(migrated)
    if "cross_archetype_index" not in migrated:
        raise AssertionError(migrated)


def validate_phase6p_still_passes() -> None:
    import validate_phase6p as phase6p

    phase6p.validate_positive_classification()
    phase6p.validate_completion_only_classification()
    phase6p.validate_negative_classification()
    phase6p.validate_filler_memory()
    phase6p.validate_runick_completion()


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


def filler_result(names: list[str], score: float, confidence: float) -> dict[str, Any]:
    return {
        "score": score,
        "confidence": confidence,
        "main_count": 40,
        "package_counts": {"interruptions": len(names)},
        "selected_fillers": names,
        "filler_roles": {"counts": {"handtrap": len(names)}, "by_card": {name: "handtrap" for name in names}},
        "contextual_filler_used": True,
        "repair_used": True,
        "pre_contextual_filler_main_count": 40 - len(names),
        "quota_warnings": [],
        "remaining_warnings": [],
        "legal_observation": True,
    }


def completion_impact(name: str, classification: str) -> dict[str, Any]:
    return {
        "filler_cards": [name],
        "impact_classification": {name: classification},
        "score_delta": 0.1,
        "confidence_delta": 0.01,
        "attributed_score_delta": 0.1,
        "attributed_confidence_delta": 0.01,
        "attribution_model": "single_card",
        "attribution_shared": False,
        "attribution_confidence": 1.0,
        "completion_required": True,
        "package_pressure_relieved": {"interruptions": 1},
        "legal_observation": True,
    }


def production_like_provenance() -> dict[str, Any]:
    return provenance_metadata(source="benchmark", validator_generated=False, smoke=True, legal=True, confidence_score=1.0, improvement=0.1)


def print_sample() -> None:
    memory = load_generic_filler_memory()
    print("SAMPLE: cross-archetype filler signals:", memory.get("cross_archetype_index", {}))
    print("SAMPLE: concentration warnings:", memory.get("concentration_warnings", [])[:3])


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
