from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.curated_opponent_library import find_curated_profile, curated_to_opponent_profile
from deck.curated_opponent_memory import (
    CURATED_MEMORY_WEIGHT_CAP,
    curated_memory_card_adjustment,
    curated_memory_summary,
    load_curated_opponent_memory,
    update_curated_opponent_memory,
)
from deck.side_deck_planner import build_side_deck
from deck.side_plan_optimizer import optimize_side_plan
from SystemAIYugioh.banlist import get_card_limit

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
        card("The White Stone of Ancients", desc="Send to GY and summon Blue-Eyes."),
        card("Bingo Machine, Go!!!", "Spell Card", "Add Blue-Eyes support."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", desc="Negate a monster effect."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Ghost Belle & Haunted Mansion", desc="Negate GY movement."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Dark Ruler No More", "Spell Card", "Negate all monster effects."),
        card("Evenly Matched", "Trap Card", "Banish cards from the field."),
        card("Forbidden One", "Spell Card", "Blocked test card."),
    ]


def main() -> None:
    checks = [
        ("curated_opponent_memory.json can be created", validate_memory_create),
        ("memory updates for Snake-Eye", validate_snake_eye_update),
        ("side optimizer reads curated memory", validate_optimizer_reads_memory),
        ("blocked cards are not boosted", validate_blocked_not_boosted),
        ("memory weights are capped", validate_weight_cap),
        ("analyze_opponent_deck updates memory", validate_analyze_updates_memory),
        ("curated matrix updates memory when gates pass", validate_matrix_updates_memory),
        ("fallback works without curated profile", validate_fallback),
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
    print("Phase 5S validation complete.")


def snake_eye_profile():
    curated = find_curated_profile("Snake-Eye")
    if not curated:
        raise AssertionError("Missing Snake-Eye curated profile.")
    return curated_to_opponent_profile(curated)


def validate_memory_create() -> None:
    profile = update_curated_opponent_memory("Blue-Eyes", "meta", snake_eye_profile(), "second", [sample_result()])
    if not profile or not load_curated_opponent_memory("Blue-Eyes", "meta", snake_eye_profile(), "second"):
        raise AssertionError(profile)


def validate_snake_eye_update() -> None:
    memory = update_curated_opponent_memory("Blue-Eyes", "meta", snake_eye_profile(), "second", [sample_result()])
    summary = curated_memory_summary(memory)
    if not summary.get("best_engine") or not summary.get("top_side_ins"):
        raise AssertionError(summary)


def validate_optimizer_reads_memory() -> None:
    profile = snake_eye_profile()
    cards = database()
    main = cards[:8] * 5
    side_report = build_side_deck(main, "Blue-Eyes", profile, cards, going="second")
    optimized = optimize_side_plan(main[:40], side_report["side_deck"], profile, "second", cards, archetype="Blue-Eyes", mode="meta", max_candidates=5)
    if not optimized.get("curated_opponent_memory_used"):
        raise AssertionError(optimized)


def validate_blocked_not_boosted() -> None:
    blocked = card("Forbidden One")
    if get_card_limit(blocked) <= 0 and curated_memory_card_adjustment({"average_post_side_delta_by_card": {"side_in": {"Forbidden One": 99}}}, "Forbidden One", "side_in", blocked) != 0:
        raise AssertionError("Blocked card received memory boost.")


def validate_weight_cap() -> None:
    boost = curated_memory_card_adjustment({"average_post_side_delta_by_card": {"side_in": {"Droll & Lock Bird": 99}}}, "Droll & Lock Bird", "side_in")
    if abs(boost) > CURATED_MEMORY_WEIGHT_CAP:
        raise AssertionError(boost)


def validate_analyze_updates_memory() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=420)
    if "Curated opponent memory updated: True" not in output and "Curated opponent memory used: True" not in output:
        raise AssertionError(output[-2000:])


def validate_matrix_updates_memory() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", timeout=2700)
    if "Curated opponent memory updated: True" not in output:
        raise AssertionError(output[-2000:])


def validate_fallback() -> None:
    memory = load_curated_opponent_memory("Blue-Eyes", "meta", "combo", "second")
    if memory:
        raise AssertionError(memory)


def sample_result() -> dict:
    return {
        "post_side_valid": True,
        "post_side_delta": 3.5,
        "post_side_score": 301.0,
        "final_score": 299.0,
        "engine_variant": "pure",
        "side_cards_used": ["Droll & Lock Bird", "D.D. Crow"],
        "cards_sided_out": ["Blue-Eyes White Dragon"],
        "resilience_score": 8.0,
        "matchup_coverage_score": 75.0,
    }


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
