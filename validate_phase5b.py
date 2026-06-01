from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from data.card_limits import get_blocked_card_names, normalize_card_name
from deck.package_builder import SAFEGUARDS, build_package_deck
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("package builder creates 40-card decks", validate_deck_size),
        ("blocked cards do not appear", validate_blocked_cards),
        ("starter minimum is respected", validate_starter_minimum),
        ("brick cap is respected", validate_brick_cap),
        ("train_agent.py still runs", lambda: run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("evaluate_learning.py still runs", lambda: run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("compare_engines.py still runs", lambda: run_command("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1")),
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

    print("Phase 5B validation complete.")


def package_deck():
    database = CardDatabase()
    cards = database.load_cards()
    deck, metrics = build_package_deck(cards, "Blue-Eyes", mode="meta")
    return deck, metrics


def validate_deck_size() -> None:
    deck, metrics = package_deck()
    if len(deck) != 40:
        raise AssertionError(f"Expected 40 cards, got {len(deck)}: {metrics}")


def validate_blocked_cards() -> None:
    deck, _ = package_deck()
    blocked = get_blocked_card_names()
    found = [
        card.get("name", "")
        for card in deck
        if normalize_card_name(str(card.get("name", ""))) in blocked
    ]
    if found:
        raise AssertionError(f"Blocked cards appeared: {found}")


def validate_starter_minimum() -> None:
    _, metrics = package_deck()
    if int(metrics.get("starter_count", 0)) < SAFEGUARDS["min_starters"]:
        raise AssertionError(f"Starter minimum missed: {metrics}")


def validate_brick_cap() -> None:
    _, metrics = package_deck()
    if int(metrics.get("brick_count", 0)) > SAFEGUARDS["max_bricks"]:
        raise AssertionError(f"Brick cap exceeded: {metrics}")


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

