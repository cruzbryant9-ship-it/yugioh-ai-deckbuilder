from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from typing import Any

import deck.generic_filler_selector as filler_selector
from deck.generic_filler_memory import load_generic_filler_memory, update_generic_filler_memory
from single_filler_attribution_benchmark import (
    build_candidate_deck_with_one_filler,
    classify_attribution_event,
    deck_copy_delta,
    make_impact_report,
    run_attribution_benchmark,
)
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root


ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("one-card filler comparison creates single attribution", validate_single_card_attribution),
        ("multi-card comparison becomes indeterminate", validate_multi_card_indeterminate),
        ("filler memory records attribution confidence 1.0 for single-card events", validate_memory_confidence),
        ("gate report updates after attribution run", validate_gate_report_after_run),
        ("filler influence remains disabled", validate_filler_influence_disabled),
        ("Phase 6Q validator still passes", validate_phase6q_still_passes),
        ("Stabilization H validator still passes", validate_stabilization_h_still_passes),
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
    print("Phase 6R validation complete.")


def validate_single_card_attribution() -> None:
    baseline_main = probe_main(["Starter A", "Starter B", "Low Value Card"])
    candidate_card = probe_card("Infinite Impermanence")
    candidate = build_candidate_deck_with_one_filler(baseline_main, [], candidate_card, {"selected_fillers": ["Low Value Card"]})
    if not candidate.get("valid"):
        raise AssertionError(candidate)
    diff = deck_copy_delta(baseline_main, candidate["main"])
    attribution = classify_attribution_event("Infinite Impermanence", diff, legal=True)
    if not attribution.get("clean"):
        raise AssertionError((diff, attribution))
    impact = make_impact_report("Probe", "meta", baseline_snapshot(), candidate_snapshot(["Infinite Impermanence"], 101.0), attribution, ["Infinite Impermanence"])
    if impact.get("attribution_model") != "single_card" or impact.get("attribution_confidence") != 1.0:
        raise AssertionError(impact)


def validate_multi_card_indeterminate() -> None:
    diff = {
        "copy_increases": {"Infinite Impermanence": 1, "Ash Blossom & Joyous Spring": 1},
        "copy_decreases": {"Low Value Card": 1, "Other Card": 1},
    }
    attribution = classify_attribution_event("Infinite Impermanence", diff, legal=True)
    impact = make_impact_report(
        "Probe",
        "meta",
        baseline_snapshot(),
        candidate_snapshot(["Infinite Impermanence", "Ash Blossom & Joyous Spring"], 103.0),
        attribution,
        ["Infinite Impermanence", "Ash Blossom & Joyous Spring"],
    )
    if not impact.get("attribution_shared") or impact.get("attribution_model") != "shared":
        raise AssertionError(impact)
    if set(impact.get("impact_classification", {}).values()) != {"indeterminate"}:
        raise AssertionError(impact)


def validate_memory_confidence() -> None:
    with temporary_isolated_memory_root("phase6r_memory_"):
        impact = make_impact_report(
            "Probe",
            "meta",
            baseline_snapshot(),
            candidate_snapshot(["Infinite Impermanence"], 101.0),
            {"clean": True, "failure_reason": None},
            ["Infinite Impermanence"],
        )
        update_generic_filler_memory("Probe", "meta", [impact], provenance=validator_provenance())
        memory = load_generic_filler_memory("Probe", "meta")
        entry = memory.get("fillers", {}).get("Infinite Impermanence", {})
        if entry.get("single_card_attribution_count") != 1:
            raise AssertionError(entry)
        if float(entry.get("average_attribution_confidence", 0) or 0) != 1.0:
            raise AssertionError(entry)


def validate_gate_report_after_run() -> None:
    with temporary_isolated_memory_root("phase6r_run_"):
        report = run_attribution_benchmark(
            ["Branded", "Kashtira", "Runick"],
            mode="meta",
            runs=1,
            fillers=["Infinite Impermanence", "Ash Blossom & Joyous Spring"],
            provenance=validator_provenance(),
            auto_extra_archetype=True,
        )
        summary = report.get("summary", {})
        if summary.get("clean_single_card_events", 0) <= 0:
            raise AssertionError(summary)
        if "gate_progress" not in summary or "cards_closest_to_eligibility" not in summary:
            raise AssertionError(summary)


def validate_filler_influence_disabled() -> None:
    source = inspect.getsource(filler_selector)
    if "generic_filler_memory" in source or "load_generic_filler_memory" in source:
        raise AssertionError("generic_filler_selector reads filler memory; influence should remain disabled")


def validate_phase6q_still_passes() -> None:
    import validate_phase6q as phase6q

    phase6q.validate_gate_predicates()
    phase6q.validate_concentration_blocks_runick_only()
    phase6q.validate_completion_biased_cards_fail()
    phase6q.validate_indeterminate_heavy_cards_fail()
    phase6q.validate_current_memory_no_eligible()


def validate_stabilization_h_still_passes() -> None:
    with temporary_isolated_memory_root("phase6r_stabh_"):
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
    with temporary_isolated_memory_root("phase6r_matrix_"):
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


def probe_card(name: str) -> dict[str, Any]:
    return {"name": name, "type": "Trap Card", "desc": "Negate an effect."}


def probe_main(names: list[str]) -> list[dict[str, Any]]:
    return [{"name": name, "type": "Spell Card", "desc": "Probe card."} for name in names]


def baseline_snapshot() -> dict[str, Any]:
    return {"score": 100.0, "confidence": 0.5, "main_count": 40, "package_counts": {"interruptions": 1}}


def candidate_snapshot(fillers: list[str], score: float) -> dict[str, Any]:
    return {
        "score": score,
        "confidence": 0.55,
        "main_count": 40,
        "package_counts": {"interruptions": 2},
        "selected_fillers": fillers,
        "filler_roles": {"counts": {"handtrap": len(fillers)}, "by_card": {name: "handtrap" for name in fillers}},
        "pre_contextual_filler_main_count": 40,
        "quota_warnings": [],
        "remaining_warnings": [],
        "legal_observation": True,
    }


def validator_provenance() -> dict[str, Any]:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True, confidence_score=1.0, improvement=1.0)


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
    with temporary_isolated_memory_root("phase6r_sample_"):
        report = run_attribution_benchmark(
            ["Branded", "Kashtira", "Runick"],
            mode="meta",
            runs=1,
            fillers=["Infinite Impermanence"],
            provenance=validator_provenance(),
            auto_extra_archetype=True,
        )
        print("Sample clean events:", report.get("summary", {}).get("clean_single_card_events"))
        print("Sample gate progress:", report.get("summary", {}).get("gate_progress"))


if __name__ == "__main__":
    main()
