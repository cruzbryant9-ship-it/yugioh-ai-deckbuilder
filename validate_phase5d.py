from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import build_deck, score_deck_breakdown
from deck.combo_lines import combo_lines_for_archetype
from deck.hand_simulator import simulate_hand
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("new combo line schema exists", validate_combo_schema),
        ("normal summon conflict detection", validate_normal_summon_conflict),
        ("dead duplicate detection", validate_dead_duplicates),
        ("payoff without enabler detection", validate_payoff_without_enabler),
        ("score breakdown phase 5D fields", validate_score_fields),
        ("training still runs", lambda: run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("evaluation still runs", lambda: run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2")),
        ("engine comparison still runs", lambda: run_command("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1")),
        ("regression gates pass/reject correctly", validate_regression_gates),
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
    print("Phase 5D validation complete.")


def card(name: str, desc: str = "", level: int = 4, card_type: str = "Effect Monster", archetype: str = "Blue-Eyes"):
    return {"name": name, "desc": desc, "level": level, "type": card_type, "archetype": archetype}


def validate_combo_schema() -> None:
    lines = combo_lines_for_archetype("Blue-Eyes")
    if len(lines) < 9:
        raise AssertionError(f"Expected expanded Blue-Eyes combo lines, got {len(lines)}")
    sample = lines[0].to_dict()
    for key in ("searched_cards", "line_score", "once_per_turn_tags", "brick_risk"):
        if key not in sample:
            raise AssertionError(f"Missing combo schema key: {key}")


def validate_normal_summon_conflict() -> None:
    hand = [
        card("Sage with Eyes of Blue", "add 1", 1),
        card("The White Stone of Ancients", "special summon", 1),
        card("Blue-Eyes White Dragon", "", 8),
        card("Dictator of D.", "special summon", 4),
        card("Bingo Machine, Go!!!", "add", 0, "Spell Card"),
    ]
    result = simulate_hand(hand, "Blue-Eyes", hand=hand)
    if not result["normal_summon_conflict"]:
        raise AssertionError(result)


def validate_dead_duplicates() -> None:
    hand = [
        card("Bingo Machine, Go!!!", "add", 0, "Spell Card"),
        card("Bingo Machine, Go!!!", "add", 0, "Spell Card"),
        card("Ultimate Fusion", "fusion summon", 0, "Spell Card"),
        card("Blue-Eyes White Dragon", "", 8),
        card("Blue-Eyes Jet Dragon", "special summon", 8),
    ]
    result = simulate_hand(hand, "Blue-Eyes", hand=hand)
    if result["dead_duplicate_count"] < 1:
        raise AssertionError(result)


def validate_payoff_without_enabler() -> None:
    hand = [
        card("Blue-Eyes Chaos MAX Dragon", "", 8, "Ritual Monster"),
        card("Blue-Eyes Ultimate Dragon", "", 12, "Fusion Monster"),
        card("Blue-Eyes Jet Dragon", "", 8),
        card("Malefic Blue-Eyes White Dragon", "", 8),
        card("Deep-Eyes White Dragon", "", 10),
    ]
    result = simulate_hand(hand, "Blue-Eyes", hand=hand)
    if not result["payoff_without_enabler"]:
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck, _ = build_deck(CardDatabase().load_cards(), "Blue-Eyes")
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "normal_summon_conflict_rate",
        "once_per_turn_conflict_rate",
        "dead_duplicate_rate",
        "payoff_without_enabler_rate",
        "enabler_without_payoff_rate",
        "best_line_average_score",
    }
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(f"Missing score fields: {sorted(missing)}")


def validate_regression_gates() -> None:
    bad = evaluate_training_batch(
        {
            "successful_runs": 2,
            "average_score": 150,
            "average_real_combo_values": {
                "playable_hand_rate": 0.9,
                "brick_rate": 0.05,
                "normal_summon_conflict_rate": 0.5,
                "once_per_turn_conflict_rate": 0.4,
                "dead_duplicate_rate": 0.4,
                "payoff_without_enabler_rate": 0.4,
                "best_line_average_score": 3,
            },
            "average_package_quality_score": 70,
            "package_quota_violations": [],
        },
        {
            "average_score": 150,
            "average_real_combo_report_values": {
                "playable_hand_rate": 0.9,
                "brick_rate": 0.05,
                "normal_summon_conflict_rate": 0.0,
                "once_per_turn_conflict_rate": 0.0,
                "dead_duplicate_rate": 0.0,
                "payoff_without_enabler_rate": 0.0,
                "best_line_average_score": 7,
            },
        },
    )
    good = evaluate_training_batch(
        {
            "successful_runs": 2,
            "average_score": 152,
            "average_real_combo_values": {
                "playable_hand_rate": 0.92,
                "brick_rate": 0.04,
                "normal_summon_conflict_rate": 0.02,
                "once_per_turn_conflict_rate": 0.02,
                "dead_duplicate_rate": 0.02,
                "payoff_without_enabler_rate": 0.01,
                "best_line_average_score": 7.5,
            },
            "average_package_quality_score": 70,
            "package_quota_violations": [],
        },
        {
            "average_score": 150,
            "average_real_combo_report_values": {
                "playable_hand_rate": 0.9,
                "brick_rate": 0.05,
                "normal_summon_conflict_rate": 0.0,
                "once_per_turn_conflict_rate": 0.0,
                "dead_duplicate_rate": 0.0,
                "payoff_without_enabler_rate": 0.0,
                "best_line_average_score": 7,
            },
        },
    )
    if bad["accepted"]:
        raise AssertionError("Bad conflict batch was accepted.")
    if not good["accepted"]:
        raise AssertionError(f"Good conflict batch was rejected: {good}")


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

