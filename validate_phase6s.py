from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from typing import Any

import deck.generic_filler_selector as filler_selector
from filler_signal_gate_report import apply_holdout_status, build_filler_signal_gate_report
from filler_signal_holdout_review import classify_holdout_delta, run_holdout_review, summarize_filler_holdout
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root


ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("eligible filler signals are loaded", validate_eligible_signals_loaded),
        ("holdout review runs", validate_holdout_review_runs),
        ("positive/negative/neutral counts are recorded", validate_counts_recorded),
        ("holdout failed signal does not become activation-ready", validate_failed_holdout_not_activation_ready),
        ("filler influence remains disabled", validate_filler_influence_disabled),
        ("Phase 6R validator still passes", validate_phase6r_still_passes),
        ("Phase 6Q validator still passes", validate_phase6q_still_passes),
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
    print("Phase 6S validation complete.")


def validate_eligible_signals_loaded() -> None:
    report = build_filler_signal_gate_report()
    eligible = [row.get("card") for row in report.get("eligible_signals", [])]
    if not eligible:
        raise AssertionError(report.get("summary"))
    for row in report.get("eligible_signals", []):
        if "holdout_required" not in row or "activation_ready" not in row:
            raise AssertionError(row)


def validate_holdout_review_runs() -> None:
    review = run_holdout_review(
        ["Branded", "Kashtira", "Runick", "Tearlaments"],
        mode="meta",
        runs=1,
        fillers=["Ash Blossom & Joyous Spring"],
        provenance=validator_provenance(),
    )
    if review.get("summary", {}).get("eligible_signals_reviewed") != 1:
        raise AssertionError(review.get("summary"))
    result = review.get("results", [{}])[0]
    if result.get("holdout_tests", 0) <= 0 or "holdout_passed" not in result:
        raise AssertionError(result)


def validate_counts_recorded() -> None:
    rows = [
        {"score_delta": 1.0, "holdout_classification": "positive", "clean_single_card_attribution": True, "archetype": "A", "run": 1},
        {"score_delta": 0.1, "holdout_classification": "neutral", "clean_single_card_attribution": True, "archetype": "A", "run": 2},
        {"score_delta": -1.0, "holdout_classification": "negative", "clean_single_card_attribution": True, "archetype": "B", "run": 1},
    ]
    summary = summarize_filler_holdout("Probe", rows, {"eligible_signals": [{"card": "Probe"}]})
    if summary.get("positive_count") != 1 or summary.get("neutral_count") != 1 or summary.get("negative_count") != 1:
        raise AssertionError(summary)
    if classify_holdout_delta(0.7) != "positive" or classify_holdout_delta(-0.7) != "negative" or classify_holdout_delta(0.1) != "neutral":
        raise AssertionError("classification thresholds failed")


def validate_failed_holdout_not_activation_ready() -> None:
    rows = [{"card": "Probe", "eligible": True}]
    apply_holdout_status(rows, {"Probe": {"holdout_passed": False, "average_holdout_delta": -1.0, "positive_count": 0, "neutral_count": 0, "negative_count": 3}})
    if rows[0].get("activation_ready"):
        raise AssertionError(rows)
    apply_holdout_status(rows, {"Probe": {"holdout_passed": True, "average_holdout_delta": 1.0, "positive_count": 3, "neutral_count": 0, "negative_count": 0}})
    if not rows[0].get("activation_ready"):
        raise AssertionError(rows)


def validate_filler_influence_disabled() -> None:
    source = inspect.getsource(filler_selector)
    if "generic_filler_memory" in source or "load_generic_filler_memory" in source:
        raise AssertionError("generic_filler_selector reads filler memory; influence should remain disabled")


def validate_phase6r_still_passes() -> None:
    import validate_phase6r as phase6r

    phase6r.validate_single_card_attribution()
    phase6r.validate_multi_card_indeterminate()
    phase6r.validate_memory_confidence()
    phase6r.validate_gate_report_after_run()
    phase6r.validate_filler_influence_disabled()


def validate_phase6q_still_passes() -> None:
    import validate_phase6q as phase6q

    phase6q.validate_gate_predicates()
    phase6q.validate_concentration_blocks_runick_only()
    phase6q.validate_completion_biased_cards_fail()
    phase6q.validate_indeterminate_heavy_cards_fail()
    phase6q.validate_current_memory_no_eligible()


def validate_matrix_smoke() -> None:
    with temporary_isolated_memory_root("phase6s_matrix_"):
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
    report = build_filler_signal_gate_report()
    print("Sample eligible fillers:", [row.get("card") for row in report.get("eligible_signals", [])])
    print("Sample activation-ready fillers:", report.get("summary", {}).get("activation_ready_fillers", []))


if __name__ == "__main__":
    main()
