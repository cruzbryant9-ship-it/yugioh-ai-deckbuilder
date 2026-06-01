from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path
from typing import Any

import deck.advisory_influence_budget as advisory_budget_module
from deck.advisory_influence_budget import apply_advisory_nudges
from deck.generic_diff_index import (
    empty_index,
    generic_diff_index_path,
    get_diff_index_advisory_signal,
    load_generic_diff_index,
    scrub_diff_index_memory,
)
from deck.generic_tuner import candidate_selection_key, tune_generic_deck
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root
from generic_archetype_benchmark import run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("phase6m_memory_"):
        checks = [
            ("scrub removes/quarantines known probe records", validate_scrub_quarantines_probe_records),
            ("validator_generated records are ignored", validate_validator_generated_records_ignored),
            ("low-support signals are ignored", validate_low_support_ignored),
            ("contested signals are suppressed", validate_contested_suppressed),
            ("advisory budget caps total influence", validate_budget_cap),
            ("kill switch disables diff-index influence", validate_kill_switch),
            ("diff-index warning does not reject legal improving deck", validate_warning_does_not_override_score),
            ("legality-driven rejected cards do not become harmful tuning bias", validate_legality_rejection_not_bias),
            ("generic benchmark still runs", validate_generic_benchmark_runs),
            ("Phase 6L validator still passes", validate_phase6l_still_passes),
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
        print("Phase 6M validation complete.")


def validate_scrub_quarantines_probe_records() -> None:
    index = dirty_index()
    atomic_write_json(generic_diff_index_path(), index)
    report = scrub_diff_index_memory(provenance=validator_provenance())
    cleaned = load_generic_diff_index()
    if "Helpful Add" in cleaned.get("helpful_cards", {}).get("additions", {}):
        raise AssertionError(cleaned["helpful_cards"])
    if "Index Probe" in cleaned.get("archetype_patterns", {}):
        raise AssertionError(cleaned["archetype_patterns"])
    if report.get("stats", {}).get("removed_entries", 0) < 1:
        raise AssertionError(report)


def validate_validator_generated_records_ignored() -> None:
    index = empty_index()
    index["harmful_cards"]["additions"]["Validator Card"] = movement_entry(10, -2.0, validator_generated=True)
    atomic_write_json(generic_diff_index_path(), index)
    scrub_diff_index_memory(provenance=validator_provenance())
    signal = get_diff_index_advisory_signal("Probe", {"copy_increases": {"Validator Card": 1}})
    if signal["hints"]:
        raise AssertionError(signal)


def validate_low_support_ignored() -> None:
    index = empty_index()
    index["helpful_cards"]["additions"]["Low Support Card"] = movement_entry(1, 2.0)
    atomic_write_json(generic_diff_index_path(), index)
    signal = get_diff_index_advisory_signal("Probe", {"copy_increases": {"Low Support Card": 1}})
    if signal["hints"] or not signal["suppressed_low_support_signals"]:
        raise AssertionError(signal)


def validate_contested_suppressed() -> None:
    index = empty_index()
    index["helpful_cards"]["additions"]["Contested Card"] = movement_entry(6, 2.0)
    index["harmful_cards"]["additions"]["Contested Card"] = movement_entry(7, -2.0)
    atomic_write_json(generic_diff_index_path(), index)
    signal = get_diff_index_advisory_signal("Probe", {"copy_increases": {"Contested Card": 1}})
    if signal["hints"] or not signal["contested_signals"]:
        raise AssertionError(signal)


def validate_budget_cap() -> None:
    result = apply_advisory_nudges({"diagnosis": 0.1, "diff_index": 0.1}, total_cap=0.15)
    used = round(sum(abs(value) for value in result["applied"].values()), 6)
    if used > 0.15:
        raise AssertionError(result)


def validate_kill_switch() -> None:
    previous = advisory_budget_module.ADVISORY_KILL_SWITCH
    try:
        advisory_budget_module.ADVISORY_KILL_SWITCH = True
        cards = CardDatabase().load_cards()
        index = empty_index()
        index["harmful_cards"]["additions"]["Branded in Central Dogmatika"] = movement_entry(10, -4.0)
        atomic_write_json(generic_diff_index_path(), index)
        report = tune_generic_deck("Branded", cards, mode="meta", runs=2, update_memory=False)
        if report.get("diff_index_bias_used"):
            raise AssertionError(report.get("advisory_budget_used"))
    finally:
        advisory_budget_module.ADVISORY_KILL_SWITCH = previous


def validate_warning_does_not_override_score() -> None:
    high_score_negative_advisory = {"score": 100.0, "diff_index_advisory_nudge": -0.08, "confidence": 0.1}
    low_score_positive_advisory = {"score": 99.5, "diff_index_advisory_nudge": 0.08, "confidence": 1.0}
    winner = max([high_score_negative_advisory, low_score_positive_advisory], key=candidate_selection_key)
    if winner is not high_score_negative_advisory:
        raise AssertionError((candidate_selection_key(high_score_negative_advisory), candidate_selection_key(low_score_positive_advisory)))


def validate_legality_rejection_not_bias() -> None:
    index = empty_index()
    result = {
        "archetype": "Probe",
        "targeted_retest": {
            "rejected_recommendations": [
                {
                    "improvement": -4.0,
                    "runs": 1,
                    "legal_run_count": 0,
                    "confidence": 0.5,
                    "repair_success": False,
                    "repair_used": True,
                    "rejection_reason": "illegal_or_unrepaired_deck",
                    "quota_warnings": ["main deck below 40 cards: 35"],
                    "card_shift_explanation": {"copy_increases": {"Illegal Bias Card": 1}},
                    "package_replay_report": {"copy_increases": {"Illegal Bias Card": 1}, "score_delta": -4.0},
                }
            ]
        },
    }
    from deck.generic_diff_index import build_cross_archetype_diff_index

    index = build_cross_archetype_diff_index([result])
    if "Illegal Bias Card" in index.get("harmful_cards", {}).get("additions", {}):
        raise AssertionError(index["harmful_cards"])


def validate_generic_benchmark_runs() -> None:
    report = run_benchmark(["Branded"], mode="meta", runs=1, provenance=validator_provenance())
    if "scrub_report_summary" not in report or "diff_index_bias_used_count" not in report.get("summary", {}):
        raise AssertionError(report.get("summary", {}))


def validate_phase6l_still_passes() -> None:
    run_command("validate_phase6l.py", timeout=1800)


def validate_stabilization_g_still_passes() -> None:
    run_command("validate_stabilization_g.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def dirty_index() -> dict[str, Any]:
    index = empty_index()
    index["helpful_cards"]["additions"]["Helpful Add"] = movement_entry(5, 1.5)
    index["harmful_cards"]["additions"]["Harmful Add"] = movement_entry(5, -1.5)
    index["helpful_cards"]["removals"]["Helpful Remove"] = movement_entry(5, 1.5)
    index["harmful_cards"]["removals"]["Harmful Remove"] = movement_entry(5, -1.5)
    index["archetype_patterns"]["Index Probe"] = {"helpful_additions": {"Helpful Add": movement_entry(1, 1.0)}}
    index["provenance_log"] = [validator_provenance()]
    return index


def movement_entry(count: int, average_delta: float, validator_generated: bool = False) -> dict[str, Any]:
    return {
        "count": count,
        "score_delta_total": round(count * average_delta, 4),
        "average_score_delta": average_delta,
        "affected_archetypes": ["Probe"],
        "last_seen_utc": "2026-01-01T00:00:00+00:00",
        "validator_generated": validator_generated,
    }


def validator_provenance() -> dict[str, Any]:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)


def print_sample() -> None:
    report = scrub_diff_index_memory(provenance=validator_provenance())
    print("SAMPLE: scrub stats:", report.get("stats", {}))
    signal = get_diff_index_advisory_signal("Probe", {"copy_increases": {"Low Support Card": 1}})
    print("SAMPLE: advisory signal:", signal)


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
