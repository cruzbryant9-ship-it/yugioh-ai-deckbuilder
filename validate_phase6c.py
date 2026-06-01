from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import safe_load_json
from deck.builder import build_deck, get_last_build_report
from deck.deck_utils import split_deck
from deck.generic_ratio_memory import GENERIC_RATIO_MEMORY_PATH, load_generic_ratio_memory
from deck.generic_tuner import tune_generic_deck

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("generic tuning runs for Branded", lambda: validate_tuning_runs(cards)),
        ("multiple variants are tested", lambda: validate_multiple_variants(cards)),
        ("best tuned deck is legal 40 cards", lambda: validate_best_deck_legal(cards)),
        ("ratio memory writes safely", lambda: validate_ratio_memory(cards)),
        ("tuned result includes score summaries", lambda: validate_score_fields(cards)),
        ("normal Blue-Eyes authored path still works", lambda: validate_blue_eyes_authored(cards)),
        ("generic_tune_runs build path works", lambda: validate_build_path_tuning(cards)),
        ("Phase 6B validator still passes", validate_phase6b_still_passes),
        ("matchup matrix smoke still works", validate_matrix_smoke),
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
    print("Phase 6C validation complete.")


def validate_tuning_runs(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=3)
    if report["runs"] != 3 or report["variant_count"] < 3:
        raise AssertionError(report)


def validate_multiple_variants(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=4)
    profiles = {tuple(sorted(result["ratio_profile"].items())) for result in report["results"]}
    if len(profiles) < 2:
        raise AssertionError(profiles)


def validate_best_deck_legal(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=3)
    main, extra = split_deck(report["best_deck"])
    if len(main) != 40 or len(extra) > 15:
        raise AssertionError((len(main), len(extra), report["best_result"]))


def validate_ratio_memory(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=3)
    if not report.get("memory_updated"):
        raise AssertionError(report)
    payload = safe_load_json(GENERIC_RATIO_MEMORY_PATH, {})
    if not isinstance(payload, dict) or "profiles" not in payload:
        raise AssertionError(payload)
    memory = load_generic_ratio_memory("Branded", "meta")
    if not memory.get("best_package_ratios"):
        raise AssertionError(memory)


def validate_score_fields(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=3)
    for key in ("best_score", "average_score", "best_result", "combo_skeleton_coverage"):
        if key not in report:
            raise AssertionError(report)


def validate_blue_eyes_authored(cards: list[dict[str, Any]]) -> None:
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta", generic_tune_runs=3)
    report = get_last_build_report()
    if report.get("builder_used") != "authored":
        raise AssertionError(report)
    if not deck:
        raise AssertionError("no Blue-Eyes deck")


def validate_build_path_tuning(cards: list[dict[str, Any]]) -> None:
    deck, _pool = build_deck(cards, "Branded", mode="meta", generic_tune_runs=3)
    main, _extra = split_deck(deck)
    report = get_last_build_report()
    if report.get("builder_used") != "generic_tuned":
        raise AssertionError(report)
    if len(main) != 40 or not report.get("generic_tuning"):
        raise AssertionError((len(main), report))


def validate_phase6b_still_passes() -> None:
    run_command("validate_phase6b.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Branded", cards, mode="meta", runs=4)
    print("SAMPLE: Branded tuned best score:", report["best_score"])
    print("SAMPLE: Branded tuned average score:", report["average_score"])
    print("SAMPLE: Branded tuned best ratio:", report["best_result"]["ratio_profile"])
    print("SAMPLE: Ratio memory updated:", report["memory_updated"])


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
