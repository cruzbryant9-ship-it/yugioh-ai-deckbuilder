from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.side_application import apply_side_plan
from deck.side_plan_optimizer import optimize_side_plan

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "", forbidden: bool = False) -> dict:
    banlist_info = {"ban_tcg": "Forbidden"} if forbidden else {}
    return {"name": name, "type": card_type, "desc": desc, "banlist_info": banlist_info, "archetype": "Blue-Eyes"}


def main_deck() -> list[dict]:
    core = [
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon normal monster."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
        card("The White Stone of Ancients", "Tuner Monster", "Special Summon Blue-Eyes from Deck."),
        card("Dictator of D.", desc="Send Blue-Eyes White Dragon to the GY."),
        card("Bingo Machine, Go!!!", "Spell Card", "Add a Blue-Eyes card from Deck."),
        card("True Light", "Trap Card", "Summon Blue-Eyes or set support."),
        card("Raigeki", "Spell Card", "Destroy all monsters your opponent controls."),
        card("Slow Battle Trap", "Trap Card", "Activate during battle."),
    ]
    deck = []
    index = 0
    while len(deck) < 40:
        base = dict(core[index % len(core)])
        base["name"] = base["name"] if index < len(core) * 3 else f"Filler {index}"
        deck.append(base)
        index += 1
    return deck


def side_deck() -> list[dict]:
    return [
        card("Ash Blossom & Joyous Spring", "Tuner Monster", "Negate a search from Deck."),
        card("Droll & Lock Bird", desc="Stop cards being added from Deck to hand."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", "Tuner Monster", "Negate a monster effect."),
        card("Dark Ruler No More", "Spell Card", "Negate all monster effects."),
        card("Evenly Matched", "Trap Card", "Banish cards from the field."),
        card("Book of Eclipse", "Spell Card", "Set monsters face-down."),
        card("D.D. Crow", desc="Banish a card from the GY."),
    ]


def main() -> None:
    checks = [
        ("optimizer generates multiple candidates", validate_candidate_generation),
        ("optimizer selects valid post-side deck", validate_valid_selection),
        ("optimized deck remains 40 cards", validate_deck_size),
        ("blocked side card is rejected", validate_blocked_rejected),
        ("invalid side-in/out is rejected", validate_invalid_side_application),
        ("valid candidate count positive for combo", validate_combo_candidate_count),
        ("post_side_evaluator uses optimization", validate_post_side_command),
        ("train/evaluate/matrix still run", validate_integration_commands),
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
    print("Phase 5O validation complete.")


def optimize() -> dict:
    return optimize_side_plan(main_deck(), side_deck(), "combo", "second", side_deck(), max_candidates=20, archetype="Blue-Eyes", mode="meta")


def validate_candidate_generation() -> None:
    result = optimize()
    if result["candidate_count"] <= 1:
        raise AssertionError(result)


def validate_valid_selection() -> None:
    result = optimize()
    if not result["optimization_used"] or result["valid_candidate_count"] <= 0:
        raise AssertionError(result)


def validate_deck_size() -> None:
    result = optimize()
    if len(result["best_post_side_main"]) != 40:
        raise AssertionError(len(result["best_post_side_main"]))


def validate_blocked_rejected() -> None:
    result = optimize_side_plan(main_deck(), [card("Forbidden Side Card", forbidden=True), *side_deck()], "combo", "second", side_deck(), max_candidates=5)
    if "Forbidden Side Card" in result["best_side_in"]:
        raise AssertionError(result)


def validate_invalid_side_application() -> None:
    result = apply_side_plan(main_deck(), side_deck(), ["Missing Side"], ["Missing Main"])
    if result["valid"] or not result["warnings"]:
        raise AssertionError(result)


def validate_combo_candidate_count() -> None:
    result = optimize()
    if result["valid_candidate_count"] <= 0:
        raise AssertionError(result)


def validate_post_side_command() -> None:
    output = run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=240)
    if "Optimization success rate" not in output:
        raise AssertionError(output[-1000:])


def validate_integration_commands() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=300)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=300)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", timeout=900)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])
    return result.stdout


if __name__ == "__main__":
    main()
