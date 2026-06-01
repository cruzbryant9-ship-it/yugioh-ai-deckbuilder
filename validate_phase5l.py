from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from SystemAIYugioh.banlist import get_card_limit
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.side_deck_planner import build_side_deck
from deck.side_deck_scoring import score_side_deck

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Spell Card", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def blue_eyes_main() -> list[dict]:
    return [
        card("Blue-Eyes White Dragon", "Normal Monster", "A Level 8 LIGHT Dragon monster."),
        card("Sage with Eyes of Blue", "Effect Monster", "Searches a LIGHT tuner."),
        card("The White Stone of Ancients", "Tuner Monster", "Sends itself to the GY for Blue-Eyes follow-up."),
        card("Dictator of D.", "Effect Monster", "Sends Blue-Eyes White Dragon to the GY."),
        card("Bingo Machine, Go!!!", "Spell Card", "Reveal Blue-Eyes cards and add one to your hand."),
    ]


def side_pool() -> list[dict]:
    return [
        card("Ash Blossom & Joyous Spring", "Tuner Monster", "Negate a search, summon from deck, or send from deck to GY."),
        card("Droll & Lock Bird", "Effect Monster", "Stops cards from being added from deck to hand."),
        card("Nibiru, the Primal Being", "Effect Monster", "Tribute monsters after many summons."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", "Tuner Monster", "Negate a monster effect on the field."),
        card("D.D. Crow", "Effect Monster", "Banish a card from the opponent's GY."),
        card("Ghost Belle & Haunted Mansion", "Tuner Monster", "Negate GY movement or banish effects."),
        card("Called by the Grave", "Spell Card", "Banish a monster from the GY and negate its effects."),
        card("Harpie's Feather Duster", "Spell Card", "Destroy all spells and traps your opponent controls."),
        card("Lightning Storm", "Spell Card", "Destroy attack position monsters or spell/trap cards."),
        card("Cosmic Cyclone", "Spell Card", "Pay LP, then banish a spell/trap card."),
        card("Evenly Matched", "Trap Card", "Banish cards from the opponent's field face-down."),
        card("Dark Ruler No More", "Spell Card", "Negate all face-up monster effects."),
        card("Book of Eclipse", "Spell Card", "Set monsters face-down."),
        card("Solemn Judgment", "Trap Card", "Negate a summon or spell/trap activation."),
        card("Raigeki", "Spell Card", "Destroy all monsters your opponent controls."),
    ]


def main() -> None:
    checks = [
        ("matchup profiles load", validate_profiles),
        ("side planner returns legal size", validate_side_size),
        ("blocked cards stay out of side deck", validate_no_blocked_cards),
        ("combo matchup recommends anti-combo cards", validate_combo_recommendations),
        ("graveyard matchup recommends graveyard hate", validate_graveyard_recommendations),
        ("backrow matchup recommends backrow removal", validate_backrow_recommendations),
        ("side scoring fields", validate_side_scoring),
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
    print("Phase 5L validation complete.")


def validate_profiles() -> None:
    names = set(list_matchup_names())
    required = {"combo", "control", "stun", "graveyard", "backrow", "spell_heavy", "handtrap_heavy", "board_breaker_heavy", "light_dark", "unknown_meta"}
    missing = required - names
    if missing:
        raise AssertionError(missing)
    profile = get_matchup_profile("combo")
    if not profile.high_value_side_cards or profile.expected_board_strength <= 0:
        raise AssertionError(profile)


def validate_side_size() -> None:
    report = build_side_deck(blue_eyes_main(), "Blue-Eyes", get_matchup_profile("combo"), side_pool(), going="both")
    if not 0 < len(report["side_deck"]) <= 15:
        raise AssertionError(len(report["side_deck"]))


def validate_no_blocked_cards() -> None:
    report = build_side_deck(blue_eyes_main(), "Blue-Eyes", get_matchup_profile("unknown_meta"), side_pool(), going="both")
    blocked = [side_card["name"] for side_card in report["side_deck"] if get_card_limit(side_card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_combo_recommendations() -> None:
    names = side_names("combo")
    if not any(term in name for name in names for term in ("Ash Blossom", "Droll", "Nibiru", "Infinite Impermanence", "Effect Veiler")):
        raise AssertionError(names)


def validate_graveyard_recommendations() -> None:
    names = side_names("graveyard")
    if not any(term in name for name in names for term in ("D.D. Crow", "Ghost Belle", "Called by")):
        raise AssertionError(names)


def validate_backrow_recommendations() -> None:
    names = side_names("backrow")
    if not any(term in name for name in names for term in ("Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched")):
        raise AssertionError(names)


def side_names(matchup: str) -> list[str]:
    report = build_side_deck(blue_eyes_main(), "Blue-Eyes", get_matchup_profile(matchup), side_pool(), going="both")
    return [side_card["name"] for side_card in report["side_deck"]]


def validate_side_scoring() -> None:
    profile = get_matchup_profile("combo")
    report = build_side_deck(blue_eyes_main(), "Blue-Eyes", profile, side_pool(), going="both")
    scoring = score_side_deck(report["side_deck"], blue_eyes_main(), profile, going="both")
    required = {
        "side_deck_score",
        "matchup_coverage_score",
        "going_first_side_score",
        "going_second_side_score",
        "anti_graveyard_coverage",
        "anti_backrow_coverage",
        "anti_combo_coverage",
        "anti_control_coverage",
        "overlap_penalty",
        "legality_score",
    }
    missing = required - set(scoring)
    if missing:
        raise AssertionError(missing)
    if scoring["side_deck_score"] <= 0:
        raise AssertionError(scoring)


def validate_commands() -> None:
    for args in (
        ("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "both"),
        ("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "both"),
        ("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1", "--matchup", "combo", "--going", "both"),
    ):
        run_command(*args)


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
