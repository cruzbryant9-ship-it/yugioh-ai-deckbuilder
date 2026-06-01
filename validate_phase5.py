from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from data.card_limits import get_blocked_card_names, normalize_card_name
from deck.builder import build_deck, score_deck_breakdown
from deck.combo_lines import combo_lines_for_archetype
from deck.hand_simulator import real_combo_report, simulate_hand
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("blocked cards never appear", validate_blocked_cards),
        ("hand simulator schema", validate_hand_schema),
        ("combo line detection", validate_combo_detection),
        ("score breakdown phase 5 fields", validate_score_fields),
        ("training still runs", lambda: run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("evaluate_learning still runs", lambda: run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("compare_engines still runs", lambda: run_command("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1")),
    ]

    failures = []
    for label, check in checks:
        try:
            check()
            print(f"PASS: {label}")
        except Exception as exc:
            failures.append((label, str(exc)))
            print(f"FAIL: {label}: {exc}")

    if failures:
        raise SystemExit(1)

    print("Phase 5 validation complete.")


def load_blue_eyes_deck() -> list[dict[str, Any]]:
    database = CardDatabase()
    cards = database.load_cards()
    deck, pool = build_deck(cards, "Blue-Eyes")
    if not cards:
        raise AssertionError("No local cards loaded.")
    if not pool:
        raise AssertionError("No Blue-Eyes archetype pool found.")
    if not deck:
        raise AssertionError("No deck generated.")
    return deck


def validate_blocked_cards() -> None:
    deck = load_blue_eyes_deck()
    blocked = get_blocked_card_names()
    found = [
        card.get("name", "")
        for card in deck
        if normalize_card_name(str(card.get("name", ""))) in blocked
    ]
    if found:
        raise AssertionError(f"Blocked cards appeared: {found}")


def validate_hand_schema() -> None:
    deck = load_blue_eyes_deck()
    result = simulate_hand(deck, "Blue-Eyes")
    required = {
        "hand",
        "playable",
        "available_lines",
        "best_line",
        "starter_count",
        "extender_count",
        "brick_count",
        "interruption_count",
        "normal_summon_conflict",
        "estimated_endboard",
        "score",
    }
    missing = required - set(result)
    if missing:
        raise AssertionError(f"Missing hand simulator fields: {sorted(missing)}")


def validate_combo_detection() -> None:
    lines = combo_lines_for_archetype("Blue-Eyes")
    if not lines:
        raise AssertionError("No Blue-Eyes combo lines registered.")

    report = real_combo_report(load_blue_eyes_deck(), "Blue-Eyes", samples=10)
    if "most_common_combo_lines" not in report:
        raise AssertionError("Real combo report missing line frequency.")


def validate_score_fields() -> None:
    deck = load_blue_eyes_deck()
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "consistency_score",
        "starter_score",
        "extender_score",
        "interruption_score",
        "brick_penalty",
        "endboard_score",
        "learned_card_bonus",
        "playable_hand_rate",
        "brick_rate",
        "combo_line_score",
        "interruption_resilience_score",
        "follow_up_score",
        "final_score",
    }
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(f"Missing score fields: {sorted(missing)}")


def run_command(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()

