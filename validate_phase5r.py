from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.curated_opponent_library import (
    find_curated_profile,
    load_curated_profiles,
    match_profile_from_decklist,
    merge_curated_and_inferred_profile,
)
from deck.decklist_parser import parse_decklist_file, parse_decklist_text
from deck.opponent_analyzer import analyze_opponent_deck
from deck.side_deck_planner import build_side_deck
from SystemAIYugioh.banlist import get_card_limit

ROOT = Path(__file__).resolve().parent
REQUIRED_PROFILES = {"Snake-Eye", "Tenpai", "Labrynth", "Branded", "Kashtira", "Runick", "Floowandereeze", "Tearlaments"}


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Snake-Eye Ash", desc="Add 1 Snake-Eye monster from your Deck."),
        card("Snake-Eyes Poplar", desc="Special Summon this card and search a Spell."),
        card("Snake-Eye Flamberge Dragon", desc="Send cards to the GY and Special Summon."),
        card("Bonfire", "Spell Card", "Add 1 Level 4 or lower Pyro monster from your Deck."),
        card("Original Sinful Spoils - Snake-Eye", "Spell Card", "Send a card and summon Snake-Eye."),
        card("WANTED: Seeker of Sinful Spoils", "Spell Card", "Add Diabellstar from your Deck."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", desc="Negate a monster effect on field."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Ghost Belle & Haunted Mansion", desc="Negate GY movement."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Harpie's Feather Duster", "Spell Card", "Destroy all Spells and Traps."),
        card("Lightning Storm", "Spell Card", "Destroy monsters or Spell/Trap cards."),
        card("Cosmic Cyclone", "Spell Card", "Banish 1 Spell/Trap."),
        card("Evenly Matched", "Trap Card", "Banish cards from the field."),
        card("Dark Ruler No More", "Spell Card", "Negate all monster effects."),
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
    ]


def main() -> None:
    checks = [
        ("curated profiles JSON loads", validate_profiles_load),
        ("each required profile exists", validate_required_profiles),
        ("aliases match correctly", validate_alias_matching),
        ("Snake-Eye sample matches curated profile", validate_snake_eye_match),
        ("curated and inferred merge works", validate_merge),
        ("side planner uses curated counters", validate_side_planner_curated),
        ("blocked cards are never recommended", validate_no_blocked_recommendations),
        ("analyze_opponent_deck.py prints profile source", validate_cli_source),
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
    print("Phase 5R validation complete.")


def validate_profiles_load() -> None:
    profiles = load_curated_profiles()
    if len(profiles) < 8:
        raise AssertionError(profiles)


def validate_required_profiles() -> None:
    names = {profile.get("archetype") for profile in load_curated_profiles()}
    missing = REQUIRED_PROFILES - names
    if missing:
        raise AssertionError(sorted(missing))


def validate_alias_matching() -> None:
    if not find_curated_profile("floo") or find_curated_profile("floo")["archetype"] != "Floowandereeze":
        raise AssertionError("Floo alias did not resolve.")
    if not find_curated_profile("snake eyes") or find_curated_profile("snake eyes")["archetype"] != "Snake-Eye":
        raise AssertionError("Snake-Eyes alias did not resolve.")


def validate_snake_eye_match() -> None:
    parsed = parse_decklist_file(ROOT / "sample_opponent_deck.txt")
    profile = match_profile_from_decklist(parsed)
    if not profile or profile.get("archetype") != "Snake-Eye":
        raise AssertionError(profile)


def validate_merge() -> None:
    parsed = parse_decklist_text("3 Snake-Eye Ash\n3 Bonfire\n3 Ash Blossom & Joyous Spring\n")
    inferred = analyze_opponent_deck(parsed, database())
    curated = find_curated_profile("Snake-Eye")
    merged = merge_curated_and_inferred_profile(curated, inferred)
    if merged.profile_source != "hybrid" or merged.matched_curated_profile != "Snake-Eye":
        raise AssertionError(merged)


def validate_side_planner_curated() -> None:
    parsed = parse_decklist_file(ROOT / "sample_opponent_deck.txt")
    profile = analyze_opponent_deck(parsed, database())
    report = build_side_deck(database(), "Blue-Eyes", profile, database(), going="second")
    names = {card["name"] for card in report["side_deck"]}
    expected = {"Droll & Lock Bird", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being", "Infinite Impermanence"}
    if profile.profile_source != "hybrid" or not (names & expected):
        raise AssertionError((profile, names))


def validate_no_blocked_recommendations() -> None:
    profile = analyze_opponent_deck(parse_decklist_file(ROOT / "sample_opponent_deck.txt"), database())
    report = build_side_deck(database(), "Blue-Eyes", profile, database(), going="second")
    blocked = [side_card["name"] for side_card in report["side_deck"] if get_card_limit(side_card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_cli_source() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=420)
    if "Profile source: hybrid" not in output and "Profile source: curated" not in output:
        raise AssertionError(output[-2000:])


def validate_integration() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=600)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=600)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", timeout=2400)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
