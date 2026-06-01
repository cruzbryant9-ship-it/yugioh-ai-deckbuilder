from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from data.card_limits import get_blocked_card_names, normalize_card_name
from deck.builder import build_deck, score_deck_breakdown
from deck.package_builder import build_package_deck
from deck.package_quality import score_package_quality
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("package quality fields", validate_package_quality_fields),
        ("bad learning can be rejected", validate_bad_rejection),
        ("good learning can be accepted", validate_good_acceptance),
        ("evaluate_learning includes regression summary", lambda: command_contains(("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"), "Regression recommendation")),
        ("compare_engines includes package quality", lambda: command_contains(("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1"), "package quality")),
        ("blocked cards still never appear", validate_blocked_cards),
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
    print("Phase 5C validation complete.")


def sample_deck():
    cards = CardDatabase().load_cards()
    deck, metrics = build_package_deck(cards, "Blue-Eyes", mode="meta")
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    return deck, metrics, breakdown


def validate_package_quality_fields() -> None:
    deck, metrics, breakdown = sample_deck()
    quality = score_package_quality(deck, metrics, breakdown)
    expected = {
        "package_balance_score",
        "starter_quota_score",
        "brick_quota_score",
        "non_engine_score",
        "engine_coherence_score",
        "extra_deck_score",
        "quota_violation_penalty",
        "final_package_quality_score",
    }
    missing = expected - set(quality)
    if missing:
        raise AssertionError(f"Missing quality fields: {sorted(missing)}")


def validate_bad_rejection() -> None:
    result = evaluate_training_batch(
        {
            "successful_runs": 2,
            "average_score": 80,
            "average_real_combo_values": {"playable_hand_rate": 0.2, "brick_rate": 0.5},
            "average_package_quality_score": 20,
            "package_quota_violations": [("brick cap exceeded", 2)],
        },
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.05}},
    )
    if result["accepted"]:
        raise AssertionError("Bad batch was accepted.")


def validate_good_acceptance() -> None:
    result = evaluate_training_batch(
        {
            "successful_runs": 2,
            "average_score": 150,
            "average_real_combo_values": {"playable_hand_rate": 0.95, "brick_rate": 0.03},
            "average_package_quality_score": 70,
            "package_quota_violations": [],
        },
        {"average_score": 145, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.05}},
    )
    if not result["accepted"]:
        raise AssertionError(f"Good batch was rejected: {result}")


def validate_blocked_cards() -> None:
    deck, _ = build_deck(CardDatabase().load_cards(), "Blue-Eyes")
    blocked = get_blocked_card_names()
    found = [card.get("name", "") for card in deck if normalize_card_name(str(card.get("name", ""))) in blocked]
    if found:
        raise AssertionError(f"Blocked cards appeared: {found}")


def command_contains(args: tuple[str, ...], needle: str) -> None:
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
    if needle not in result.stdout:
        raise AssertionError(f"Expected output to contain {needle!r}")


if __name__ == "__main__":
    main()

