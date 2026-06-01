from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.side_application import apply_side_plan
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", forbidden: bool = False) -> dict:
    banlist_info = {"ban_tcg": "Forbidden"} if forbidden else {}
    return {"name": name, "type": card_type, "desc": "", "banlist_info": banlist_info}


def main() -> None:
    checks = [
        ("apply_side_plan keeps legal size", validate_legal_size),
        ("blocked side cards are rejected", validate_blocked_side_card),
        ("side-in/out works", validate_side_swap),
        ("invalid side plan returns warnings", validate_invalid_plan),
        ("post_side_evaluator runs", validate_post_side_command),
        ("train/evaluate/matrix still run", validate_integration_commands),
        ("regression gates check post-side fields", validate_regression_gate),
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
    print("Phase 5N validation complete.")


def validate_legal_size() -> None:
    main = [card(f"Main {index}") for index in range(40)]
    side = [card("Ash Blossom & Joyous Spring")]
    result = apply_side_plan(main, side, ["Ash Blossom & Joyous Spring"], ["Main 0"])
    if len(result["post_side_main"]) != 40 or not result["valid"]:
        raise AssertionError(result)


def validate_blocked_side_card() -> None:
    main = [card(f"Main {index}") for index in range(40)]
    side = [card("Forbidden Test Card", forbidden=True)]
    result = apply_side_plan(main, side, ["Forbidden Test Card"], ["Main 0"])
    if result["valid"] or "blocked side-in card rejected: Forbidden Test Card" not in result["warnings"]:
        raise AssertionError(result)


def validate_side_swap() -> None:
    main = [card(f"Main {index}") for index in range(40)]
    side = [card("Droll & Lock Bird")]
    result = apply_side_plan(main, side, ["Droll & Lock Bird"], ["Main 1"])
    names = [item["name"] for item in result["post_side_main"]]
    if "Droll & Lock Bird" not in names or "Main 1" in names:
        raise AssertionError(result)


def validate_invalid_plan() -> None:
    main = [card(f"Main {index}") for index in range(40)]
    side = [card("Nibiru, the Primal Being")]
    result = apply_side_plan(main, side, ["Missing Side Card"], ["Missing Main Card"])
    if result["valid"] or not result["warnings"]:
        raise AssertionError(result)


def validate_post_side_command() -> None:
    run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=240)


def validate_integration_commands() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=240)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=240)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", timeout=1200)


def validate_regression_gate() -> None:
    summary = {
        "successful_runs": 2,
        "average_score": 100,
        "average_real_combo_values": {},
        "average_post_side_score": 80,
        "average_post_side_delta": -20,
        "post_side_valid_rate": 0.25,
    }
    result = evaluate_training_batch(summary, {"average_score": 100, "average_post_side_score": 100})
    reasons = " ".join(result["reasons"])
    if result["accepted"] or "post-side" not in reasons and "side plan" not in reasons:
        raise AssertionError(result)


def run_command(*args: str, timeout: int = 180) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
