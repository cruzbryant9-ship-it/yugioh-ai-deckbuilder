from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from SystemAIYugioh.card_database import CardDatabase
from deck.decklist_parser import parse_decklist_file
from deck.opponent_analyzer import analyze_opponent_deck
from deck.opponent_branch_graph import get_opponent_graph
from deck.opponent_graph_simulator import simulate_opponent_graph
from deck.opponent_probability_simulator import simulate_opponent_openings
from config.settings import MONTE_CARLO_DEFAULT_RUNS, MONTE_CARLO_SMOKE_RUNS

ROOT = Path(__file__).resolve().parent
VALIDATION_MODE = "smoke"


def main() -> None:
    global VALIDATION_MODE
    args = parse_args()
    VALIDATION_MODE = "full" if args.full else "smoke"
    checks = [
        ("probability simulator runs on sample decklist", validate_probability_simulator),
        ("rates are normalized", validate_rate_bounds),
        ("graph simulator includes probability fields", validate_graph_probability_fields),
        ("analyze_opponent_deck prints probability estimates", validate_analyzer_output),
        ("Phase 5W graph/resource primitive still passes", validate_phase5w_primitive),
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
    print("Phase 5X-lite validation complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 5X-lite probability support.")
    parser.add_argument("--smoke", action="store_true", help="Run fast primitive checks. Default.")
    parser.add_argument("--full", action="store_true", help="Use full Monte Carlo runs for probability checks.")
    return parser.parse_args()


def sample_profile_and_probability() -> tuple[dict[str, list[str]], object, dict[str, float]]:
    database = CardDatabase()
    cards = database.load_cards()
    parsed = parse_decklist_file(ROOT / "sample_opponent_deck.txt")
    profile = analyze_opponent_deck(parsed, cards)
    runs = MONTE_CARLO_DEFAULT_RUNS if VALIDATION_MODE == "full" else MONTE_CARLO_SMOKE_RUNS
    probability = simulate_opponent_openings(parsed, profile, runs=runs)
    return parsed, profile, probability


def validate_probability_simulator() -> None:
    _parsed, _profile, probability = sample_profile_and_probability()
    required = {
        "opponent_starter_open_rate",
        "opponent_extender_open_rate",
        "opponent_interruption_open_rate",
        "opponent_board_breaker_open_rate",
        "opponent_likely_line_access_rate",
        "opponent_backup_line_access_rate",
        "opponent_brick_rate",
        "opponent_graveyard_access_rate",
        "opponent_search_access_rate",
    }
    missing = required - set(probability)
    if missing:
        raise AssertionError(missing)


def validate_rate_bounds() -> None:
    _parsed, _profile, probability = sample_profile_and_probability()
    for key, value in probability.items():
        if not 0 <= value <= 1:
            raise AssertionError((key, value))


def validate_graph_probability_fields() -> None:
    _parsed, profile, probability = sample_profile_and_probability()
    graph = get_opponent_graph(profile)
    report = simulate_opponent_graph(graph, ["Ash Blossom & Joyous Spring"], probability_estimates=probability)
    required = {
        "opponent_starter_open_rate",
        "opponent_extender_open_rate",
        "opponent_interruption_open_rate",
        "opponent_brick_rate",
        "probability_weighted_resource_valid_rate",
        "probability_weighted_stop_rate",
        "probability_weighted_pivot_rate",
        "probability_weighted_backup_rate",
    }
    missing = required - set(report)
    if missing:
        raise AssertionError(missing)
    if report["probability_weighted_stop_rate"] > report["graph_stop_rate"]:
        raise AssertionError(report)


def validate_analyzer_output() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=900)
    required = ("Opponent starter open rate:", "Opponent brick rate:", "Probability-weighted stop rate:")
    if not all(text in output for text in required):
        raise AssertionError(output[-2500:])


def validate_phase5w_primitive() -> None:
    _parsed, profile, _probability = sample_profile_and_probability()
    graph = get_opponent_graph(profile)
    report = simulate_opponent_graph(graph, ["Ash Blossom & Joyous Spring"])
    if report.get("opponent_resource_valid_rate", 0) <= 0:
        raise AssertionError(report)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
