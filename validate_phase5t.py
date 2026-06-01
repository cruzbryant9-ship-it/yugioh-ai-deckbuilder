from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.choke_simulator import simulate_choke_points
from deck.curated_opponent_library import curated_to_opponent_profile, find_curated_profile
from deck.opponent_choke_model import get_opponent_lines, list_supported_opponents
from deck.side_deck_planner import build_side_deck
from SystemAIYugioh.banlist import get_card_limit

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", desc="Negate a monster effect."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Ghost Belle & Haunted Mansion", desc="Negate GY movement."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Cosmic Cyclone", "Spell Card", "Banish 1 Spell/Trap."),
        card("Lightning Storm", "Spell Card", "Destroy Spell/Trap cards."),
        card("Evenly Matched", "Trap Card", "Banish opponent field."),
    ]


def main() -> None:
    checks = [
        ("opponent choke lines load", validate_lines_load),
        ("Snake-Eye has known choke points", validate_snake_eye_chokes),
        ("Ash/Droll/Crow/Imperm map to choke points", validate_interruption_mapping),
        ("simulator ranks good interruption", validate_ranking),
        ("poor interruptions are identified", validate_poor_interruptions),
        ("side planner uses choke recommendations", validate_side_planner_choke),
        ("analyze_opponent_deck prints choke analysis", validate_analyzer_output),
        ("blocked cards are never recommended", validate_no_blocked),
        ("train/evaluate/matrix/post-side still run", validate_integration),
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
    print("Phase 5T validation complete.")


def snake_eye_profile():
    curated = find_curated_profile("Snake-Eye")
    if not curated:
        raise AssertionError("Snake-Eye curated profile missing")
    return curated_to_opponent_profile(curated)


def validate_lines_load() -> None:
    supported = set(list_supported_opponents())
    required = {"Snake-Eye", "Tenpai", "Labrynth", "Branded", "Kashtira", "Runick", "Floowandereeze", "Tearlaments"}
    if not required.issubset(supported):
        raise AssertionError(supported)


def validate_snake_eye_chokes() -> None:
    lines = get_opponent_lines(snake_eye_profile())
    if not lines or not any("Flamberge" in choke for line in lines for choke in line.choke_points):
        raise AssertionError(lines)


def validate_interruption_mapping() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring", "Droll & Lock Bird", "D.D. Crow", "Infinite Impermanence"])
    if not {"Ash Blossom", "Droll & Lock Bird", "D.D. Crow", "Infinite Impermanence"} & set(report["best_interruptions"]):
        raise AssertionError(report)


def validate_ranking() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Droll & Lock Bird", "D.D. Crow"])
    if not report["recommended_interruptions"] or report["average_stop_rate"] <= 0:
        raise AssertionError(report)


def validate_poor_interruptions() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Harpie's Feather Duster"])
    if not report["poor_interruptions"]:
        raise AssertionError(report)


def validate_side_planner_choke() -> None:
    profile = snake_eye_profile()
    report = build_side_deck(database(), "Blue-Eyes", profile, database(), going="second")
    if report["choke_stop_rate"] <= 0 or "hits_modeled_choke_point" not in {reason for reasons in report["reasons"].values() for reason in reasons}:
        raise AssertionError(report)


def validate_analyzer_output() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=600)
    if "Opponent likely lines:" not in output or "Best interruptions:" not in output:
        raise AssertionError(output[-2000:])


def validate_no_blocked() -> None:
    report = build_side_deck(database(), "Blue-Eyes", snake_eye_profile(), database(), going="second")
    blocked = [card["name"] for card in report["side_deck"] if get_card_limit(card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_integration() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=700)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=700)
    run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=700)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", timeout=1800)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
