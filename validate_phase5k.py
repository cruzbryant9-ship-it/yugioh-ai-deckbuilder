from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import score_deck_breakdown
from deck.chain_model import build_chain_window, create_chain_link, estimate_recovery_adjusted_resilience
from deck.hand_simulator import simulate_hand, simulate_interrupted_hand
from deck.interruption_profiles import profile_by_name
from deck.line_graph import LineGraph, LineNode
from deck.line_validator import validate_line

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4) -> dict:
    return {"name": name, "type": card_type, "level": level, "race": "Dragon", "attribute": "LIGHT", "archetype": "Blue-Eyes", "desc": ""}


def main() -> None:
    checks = [
        ("chain model creates link", validate_chain_link),
        ("Ash responds to search", validate_ash_response),
        ("Imperm and Veiler respond to monster effect", validate_imperm_veiler),
        ("D.D. Crow responds to GY dependency", validate_crow),
        ("interruption window recorded", validate_window_recorded),
        ("recovery improves resilience", validate_recovery_resilience),
        ("interrupted hand simulation", validate_interrupted_hand),
        ("score breakdown interruption fields", validate_score_fields),
        ("train/evaluate/compare still run", validate_commands),
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
    print("Phase 5K validation complete.")


def validate_chain_link() -> None:
    link = create_chain_link(1, "Bingo Machine, Go!!!", "search")
    if link["chain_link"] != 1 or link["resolution_outcome"] != "resolved":
        raise AssertionError(link)


def validate_ash_response() -> None:
    window = build_chain_window(1, "Bingo Machine, Go!!!", "search", ("Ash Blossom",))
    if "Ash Blossom" not in window["possible_responses"]:
        raise AssertionError(window)


def validate_imperm_veiler() -> None:
    window = build_chain_window(1, "Sage with Eyes of Blue", "monster_effect", ("Infinite Impermanence", "Effect Veiler"))
    if not {"Infinite Impermanence", "Effect Veiler"}.issubset(set(window["possible_responses"])):
        raise AssertionError(window)


def validate_crow() -> None:
    window = build_chain_window(1, "Blue-Eyes White Dragon", "gy_dependency", ("D.D. Crow",))
    if "D.D. Crow" not in window["possible_responses"]:
        raise AssertionError(window)


def validate_window_recorded() -> None:
    graph = LineGraph("chain test", "Blue-Eyes", (LineNode("search", "search", opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom",), branches=({"name": "search", "effects": ({"type": "search", "card": "Sage with Eyes of Blue"},), "score": 3},)),), recovery_options=("Wishes for Eyes of Blue",))
    result = validate_line([], graph, deck=[card("Sage with Eyes of Blue")])
    if not result["valid"] or not result["chain_windows"]:
        raise AssertionError(result)


def validate_recovery_resilience() -> None:
    low = estimate_recovery_adjusted_resilience(5.0, [])
    high = estimate_recovery_adjusted_resilience(5.0, ["Bingo Machine, Go!!!", "True Light"])
    if high <= low:
        raise AssertionError((low, high))


def validate_interrupted_hand() -> None:
    deck = [card("Bingo Machine, Go!!!", "Spell Card", 0), card("Blue-Eyes Alternative White Dragon", level=8), card("Sage with Eyes of Blue")]
    result = simulate_interrupted_hand([deck[0]], deck, "Ash Blossom")
    if "resilience_score" not in result:
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = [
        card("Bingo Machine, Go!!!", "Spell Card", 0),
        card("Wishes for Eyes of Blue", "Spell Card", 0),
        card("Sage with Eyes of Blue"),
        card("The White Stone of Ancients", "Tuner Monster", 1),
        card("Blue-Eyes White Dragon", "Normal Monster", 8),
        card("Blue-Eyes Alternative White Dragon", level=8),
        card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9),
    ] * 7
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "interruption_window_count",
        "average_interruption_risk",
        "ash_vulnerability_rate",
        "imperm_vulnerability_rate",
        "veiler_vulnerability_rate",
        "droll_vulnerability_rate",
        "crow_vulnerability_rate",
        "nibiru_vulnerability_rate",
        "recovery_route_rate",
        "interrupted_line_success_rate",
        "resilience_score",
    }
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(missing)


def validate_commands() -> None:
    for args in (
        ("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1"),
    ):
        run_command(*args)


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
