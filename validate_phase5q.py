from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.decklist_parser import parse_decklist_text
from deck.opponent_analyzer import analyze_opponent_deck
from deck.side_deck_planner import build_side_deck
from SystemAIYugioh.banlist import get_card_limit

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Snake-Eye Ash", desc="Add 1 Snake-Eye monster from your Deck."),
        card("Snake-Eyes Poplar", desc="Special Summon this card and search a Spell."),
        card("Snake-Eye Flamberge Dragon", desc="Send cards to the GY and Special Summon."),
        card("Bonfire", "Spell Card", "Add 1 Level 4 or lower Pyro monster from your Deck."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Harpie's Feather Duster", "Spell Card", "Destroy all Spells and Traps."),
        card("Lightning Storm", "Spell Card", "Destroy monsters or Spell/Trap cards."),
        card("Evenly Matched", "Trap Card", "Banish cards from the field."),
        card("Dark Ruler No More", "Spell Card", "Negate all monster effects."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
    ]


def main() -> None:
    checks = [
        ("parser handles count-prefixed decklist", validate_count_parser),
        ("parser handles one-card-per-line", validate_one_per_line),
        ("analyzer detects hand traps", validate_hand_traps),
        ("analyzer detects graveyard dependency", validate_graveyard_dependency),
        ("analyzer maps matchup", validate_matchup_mapping),
        ("side planner accepts opponent profile", validate_side_planner_profile),
        ("analyze_opponent_deck.py runs", validate_cli),
        ("blocked cards never appear in recommendations", validate_no_blocked_recommendations),
        ("train/evaluate/matrix still run", validate_integration),
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
    print("Phase 5Q validation complete.")


def parsed_sample() -> dict[str, list[str]]:
    return parse_decklist_text(
        """
        Main Deck:
        3 Snake-Eye Ash
        3 Snake-Eyes Poplar
        2 Snake-Eye Flamberge Dragon
        3 Bonfire
        3 Ash Blossom & Joyous Spring
        2 Droll & Lock Bird
        Extra Deck:
        1 Promethean Princess, Bestower of Flames
        Side Deck:
        3 D.D. Crow
        """
    )


def validate_count_parser() -> None:
    parsed = parsed_sample()
    if parsed["main"].count("Snake-Eye Ash") != 3 or parsed["side"].count("D.D. Crow") != 3:
        raise AssertionError(parsed)


def validate_one_per_line() -> None:
    parsed = parse_decklist_text("Ash Blossom & Joyous Spring\nInfinite Impermanence\n")
    if parsed["main"] != ["Ash Blossom & Joyous Spring", "Infinite Impermanence"]:
        raise AssertionError(parsed)


def validate_hand_traps() -> None:
    profile = analyze_opponent_deck(parsed_sample(), database())
    if not any("Ash Blossom" in card for card in profile.key_interruptions):
        raise AssertionError(profile)


def validate_graveyard_dependency() -> None:
    profile = analyze_opponent_deck(parsed_sample(), database())
    if profile.graveyard_dependency <= 0:
        raise AssertionError(profile)


def validate_matchup_mapping() -> None:
    profile = analyze_opponent_deck(parsed_sample(), database())
    if profile.nearest_matchup not in {"combo", "graveyard", "handtrap_heavy"}:
        raise AssertionError(profile)


def validate_side_planner_profile() -> None:
    profile = analyze_opponent_deck(parsed_sample(), database())
    report = build_side_deck(database(), "Blue-Eyes", profile, database(), going="second")
    if not report["side_deck"] or report["matchup"] != profile.name:
        raise AssertionError(report)


def validate_cli() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=300)
    if "Opponent Deck Analysis" not in output:
        raise AssertionError(output[-1000:])


def validate_no_blocked_recommendations() -> None:
    profile = analyze_opponent_deck(parsed_sample(), database())
    report = build_side_deck(database(), "Blue-Eyes", profile, database(), going="second")
    blocked = [side_card["name"] for side_card in report["side_deck"] if get_card_limit(side_card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_integration() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=420)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=500)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", timeout=1500)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])
    return result.stdout


if __name__ == "__main__":
    main()
