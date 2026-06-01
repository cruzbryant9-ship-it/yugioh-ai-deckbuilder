from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.post_side_memory import (
    MEMORY_WEIGHT_CAP,
    POST_SIDE_STATS_PATH,
    load_post_side_memory,
    memory_card_adjustment,
    update_post_side_memory,
)
from deck.side_plan_optimizer import optimize_side_plan

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", forbidden: bool = False) -> dict:
    banlist_info = {"ban_tcg": "Forbidden"} if forbidden else {}
    return {"name": name, "type": card_type, "desc": "Blue-Eyes support card.", "banlist_info": banlist_info, "archetype": "Blue-Eyes"}


def main_deck() -> list[dict]:
    cards = [card(f"Main {index}") for index in range(40)]
    cards[0] = card("Blue-Eyes White Dragon", "Normal Monster")
    cards[1] = card("Sage with Eyes of Blue")
    cards[2] = card("Bingo Machine, Go!!!", "Spell Card")
    return cards


def side_deck() -> list[dict]:
    return [
        card("Ash Blossom & Joyous Spring"),
        card("Droll & Lock Bird"),
        card("Nibiru, the Primal Being"),
        card("Infinite Impermanence", "Trap Card"),
        card("Dark Ruler No More", "Spell Card"),
        card("Forbidden Side Memory Card", forbidden=True),
    ]


def main() -> None:
    checks = [
        ("post_side_stats can be created", validate_memory_create),
        ("side-in/out stats update", validate_stats_update),
        ("optimizer reads memory", validate_optimizer_reads_memory),
        ("blocked cards are not boosted", validate_blocked_not_boosted),
        ("memory weights are capped", validate_weight_cap),
        ("evaluator updates memory", validate_evaluator_updates_memory),
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
    print("Phase 5P validation complete.")


def validate_memory_create() -> None:
    update_post_side_memory("Blue-Eyes", "meta", "combo", "second", [sample_result()])
    if not (ROOT / POST_SIDE_STATS_PATH).exists():
        raise AssertionError(POST_SIDE_STATS_PATH)


def validate_stats_update() -> None:
    memory = load_post_side_memory("Blue-Eyes", "meta", "combo", "second")
    if memory.get("side_in_card_counts", {}).get("Ash Blossom & Joyous Spring", 0) <= 0:
        raise AssertionError(memory)
    if memory.get("side_out_card_counts", {}).get("Main 9", 0) <= 0:
        raise AssertionError(memory)


def validate_optimizer_reads_memory() -> None:
    result = optimize_side_plan(main_deck(), side_deck(), "combo", "second", side_deck(), max_candidates=8, archetype="Blue-Eyes", mode="meta")
    if "post_side_memory_used" not in result:
        raise AssertionError(result)


def validate_blocked_not_boosted() -> None:
    memory = load_post_side_memory("Blue-Eyes", "meta", "combo", "second")
    blocked = card("Forbidden Side Memory Card", forbidden=True)
    if memory_card_adjustment(memory, "Forbidden Side Memory Card", "side_in", blocked) != 0:
        raise AssertionError("blocked card received memory adjustment")


def validate_weight_cap() -> None:
    memory = {
        "average_post_side_delta_by_card": {
            "side_in": {"Huge Memory Card": 999},
            "side_out": {},
        }
    }
    value = memory_card_adjustment(memory, "Huge Memory Card", "side_in")
    if abs(value) > MEMORY_WEIGHT_CAP:
        raise AssertionError(value)


def validate_evaluator_updates_memory() -> None:
    output = run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=300)
    if "Post-side memory updated: True" not in output:
        raise AssertionError(output[-1000:])


def validate_integration_commands() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=300)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=420)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", timeout=1200)


def sample_result() -> dict:
    return {
        "post_side_valid": True,
        "post_side_delta": 6.0,
        "post_side_score": 300.0,
        "valid_candidate_rate": 1.0,
        "side_cards_used": ["Ash Blossom & Joyous Spring", "Droll & Lock Bird"],
        "cards_sided_out": ["Main 9", "Main 10"],
    }


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])
    return result.stdout


if __name__ == "__main__":
    main()
