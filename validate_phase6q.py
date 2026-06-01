from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck import advisory_influence_budget as budget_module
from deck.advisory_influence_budget import AdvisoryInfluenceBudget
from deck.filler_signal_gates import (
    archetype_breadth,
    attribution_majority,
    completion_bias_suppression,
    concentration_clearance,
    evaluate_filler_signal_eligibility,
    indeterminate_suppression,
    observation_floor,
)
from deck.generic_filler_memory import empty_payload, migrate_filler_memory
from filler_signal_gate_report import build_filler_signal_gate_report
from SystemAIYugioh.json_utils import safe_load_json
from SystemAIYugioh.memory_context import temporary_isolated_memory_root


ROOT = Path(__file__).resolve().parent
PRODUCTION_FILLER_MEMORY = ROOT / "SystemAIYugioh" / "data" / "deck_profiles" / "generic_filler_memory.json"


def main() -> None:
    checks = [
        ("gate predicates function correctly", validate_gate_predicates),
        ("concentration blocks Runick-only signals", validate_concentration_blocks_runick_only),
        ("completion-biased cards cannot pass", validate_completion_biased_cards_fail),
        ("indeterminate-heavy cards fail", validate_indeterminate_heavy_cards_fail),
        ("no current filler memory signal becomes eligible incorrectly", validate_current_memory_no_eligible),
        ("gate report summarizes failures", validate_gate_report),
        ("Phase 6P still passes", validate_phase6p_still_passes),
        ("Stabilization H still passes", validate_stabilization_h_still_passes),
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
    print("Phase 6Q validation complete.")


def eligible_probe_entry() -> dict[str, Any]:
    return {
        "times_used": 6,
        "completion_only_count": 1,
        "performance_positive_count": 4,
        "performance_neutral_count": 1,
        "performance_negative_count": 0,
        "indeterminate_count": 0,
        "shared_attribution_count": 0,
        "single_card_attribution_count": 6,
        "average_attribution_confidence": 1.0,
        "legal_observation_count": 6,
        "illegal_observation_count": 0,
        "completion_bias_flag": False,
        "archetype_observations": {"branded": 3, "kashtira": 3},
        "affected_archetypes": ["branded", "kashtira"],
        "archetype_breadth": 2,
        "average_score_delta": 0.8,
        "last_observation_provenance": {"validator_generated": False, "source": "benchmark"},
    }


def validate_gate_predicates() -> None:
    entry = eligible_probe_entry()
    budget = AdvisoryInfluenceBudget()
    budget.apply("diagnosis", 0.02)
    evaluation = evaluate_filler_signal_eligibility("Gate Probe", entry, budget_summary=budget.summary())
    if not evaluation.get("eligible"):
        raise AssertionError(evaluation)
    for predicate in (
        observation_floor,
        archetype_breadth,
        concentration_clearance,
        attribution_majority,
        indeterminate_suppression,
        completion_bias_suppression,
    ):
        passed, _score = predicate(entry)
        if not passed:
            raise AssertionError((predicate.__name__, entry))


def validate_concentration_blocks_runick_only() -> None:
    entry = eligible_probe_entry()
    entry["archetype_observations"] = {"runick": 6}
    entry["affected_archetypes"] = ["runick"]
    entry["archetype_breadth"] = 1
    evaluation = evaluate_filler_signal_eligibility("Runick Filler", entry)
    if evaluation.get("eligible"):
        raise AssertionError(evaluation)
    for gate in ("archetype_breadth", "concentration_clearance"):
        if gate not in evaluation.get("failed_gates", []):
            raise AssertionError(evaluation)


def validate_completion_biased_cards_fail() -> None:
    entry = eligible_probe_entry()
    entry["completion_only_count"] = 3
    evaluation = evaluate_filler_signal_eligibility("Completion Filler", entry)
    if evaluation.get("eligible") or "completion_bias_suppression" not in evaluation.get("failed_gates", []):
        raise AssertionError(evaluation)


def validate_indeterminate_heavy_cards_fail() -> None:
    entry = eligible_probe_entry()
    entry["indeterminate_count"] = 4
    entry["single_card_attribution_count"] = 2
    entry["shared_attribution_count"] = 4
    entry["average_attribution_confidence"] = 0.45
    evaluation = evaluate_filler_signal_eligibility("Shared Filler", entry)
    if evaluation.get("eligible"):
        raise AssertionError(evaluation)
    for gate in ("indeterminate_suppression", "attribution_majority", "confidence_floor"):
        if gate not in evaluation.get("failed_gates", []):
            raise AssertionError(evaluation)


def validate_current_memory_no_eligible() -> None:
    payload = safe_load_json(PRODUCTION_FILLER_MEMORY, empty_payload())
    if not isinstance(payload, dict):
        payload = empty_payload()
    payload = migrate_filler_memory(payload)
    report = build_filler_signal_gate_report(payload)
    for row in report.get("eligible_signals", []) or []:
        if row.get("failed_gates"):
            raise AssertionError(row)
        if row.get("scope") != "cross_archetype_aggregate":
            raise AssertionError(row)
        if "probe" in str(row.get("card", "")).casefold():
            raise AssertionError(row)
        scores = row.get("gate_scores", {})
        if scores.get("completion_bias_suppression") or not scores.get("provenance_clean", {}).get("legal_observation_count"):
            raise AssertionError(row)


def validate_gate_report() -> None:
    memory = {
        "profiles": {
            "runick": {"meta": {"fillers": {"Infinite Impermanence": runick_only_entry()}}},
            "branded": {"meta": {"fillers": {"Shared Probe": indeterminate_entry()}}},
        },
        "concentration_warnings": [],
    }
    report = build_filler_signal_gate_report(memory)
    summary = report.get("summary", {})
    if summary.get("eligible_count") != 0:
        raise AssertionError(report)
    if "Infinite Impermanence" not in summary.get("cards_blocked_by_concentration", []):
        raise AssertionError(summary)
    if "Shared Probe" not in summary.get("cards_blocked_by_attribution", []):
        raise AssertionError(summary)


def runick_only_entry() -> dict[str, Any]:
    entry = eligible_probe_entry()
    entry["archetype_observations"] = {"runick": 6}
    entry["affected_archetypes"] = ["runick"]
    entry["archetype_breadth"] = 1
    return entry


def indeterminate_entry() -> dict[str, Any]:
    entry = eligible_probe_entry()
    entry["indeterminate_count"] = 5
    entry["single_card_attribution_count"] = 1
    entry["average_attribution_confidence"] = 0.4
    return entry


def validate_phase6p_still_passes() -> None:
    with temporary_isolated_memory_root("phase6q_phase6p_"):
        import validate_phase6p as phase6p

        phase6p.validate_positive_classification()
        phase6p.validate_completion_only_classification()
        phase6p.validate_negative_classification()
        phase6p.validate_filler_memory()
        phase6p.validate_runick_completion()


def validate_stabilization_h_still_passes() -> None:
    with temporary_isolated_memory_root("phase6q_stabh_"):
        import validate_stabilization_h as stab_h

        stab_h.validate_shared_attribution()
        stab_h.validate_single_card_attribution()
        stab_h.validate_completion_suppression()
        stab_h.validate_archetype_first_storage()
        stab_h.validate_runick_only_not_global()
        stab_h.validate_support_thresholds()
        stab_h.validate_budget_source()
        stab_h.validate_budget_kill_switch()


def validate_matrix_smoke() -> None:
    with temporary_isolated_memory_root("phase6q_matrix_"):
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
    previous = budget_module.ADVISORY_KILL_SWITCH
    try:
        sample = evaluate_filler_signal_eligibility("Infinite Impermanence", runick_only_entry())
        budget_module.ADVISORY_KILL_SWITCH = True
        killed = evaluate_filler_signal_eligibility("Gate Probe", eligible_probe_entry())
    finally:
        budget_module.ADVISORY_KILL_SWITCH = previous
    print("Sample Runick-only gate failures:", sample.get("failed_gates"))
    print("Sample kill-switch gate failures:", killed.get("failed_gates"))


if __name__ == "__main__":
    main()
