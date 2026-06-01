from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.choke_simulator import simulate_choke_points
from deck.curated_opponent_library import curated_to_opponent_profile, find_curated_profile
from deck.opponent_branch_graph import get_opponent_graph
from deck.opponent_graph_simulator import simulate_opponent_graph, initial_resource_state, validate_and_apply_node_resources
from deck.opponent_resource_state import OpponentResourceState

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("OpponentResourceState moves cards", validate_moves),
        ("normal summon is enforced", validate_normal_summon),
        ("once-per-turn is enforced", validate_once_per_turn),
        ("Snake-Eye graph resolves with resources", validate_snake_eye_resources),
        ("graph fails when starter is missing", validate_missing_starter),
        ("graph pivots when interrupted", validate_interruption_pivot),
        ("resource metrics appear in choke simulation", validate_choke_resource_metrics),
        ("analyze_opponent_deck prints resource output", validate_analyzer_output),
        ("post-side/evaluate/matrix still run", validate_integration),
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
    print("Phase 5W validation complete.")


def snake_eye_profile():
    curated = find_curated_profile("Snake-Eye")
    if not curated:
        raise AssertionError("Snake-Eye curated profile missing")
    return curated_to_opponent_profile(curated)


def validate_moves() -> None:
    state = OpponentResourceState(hand=["Snake-Eye Ash"], deck=["Snake-Eyes Poplar"])
    if not state.summon_from_hand("Snake-Eye Ash") or not state.search_deck("Snake-Eyes Poplar"):
        raise AssertionError(state.__dict__)


def validate_normal_summon() -> None:
    state = OpponentResourceState(hand=["A", "B"])
    state.used_normal_summon = True
    node = get_opponent_graph(snake_eye_profile()).nodes["se_ash"]
    result = validate_and_apply_node_resources(state, node)
    if result["reason"] != "normal_summon_used":
        raise AssertionError(result)


def validate_once_per_turn() -> None:
    state = OpponentResourceState(hand=["Snake-Eye Ash"], deck=["Snake-Eyes Poplar"])
    node = get_opponent_graph(snake_eye_profile()).nodes["se_ash"]
    first = validate_and_apply_node_resources(state, node)
    second = validate_and_apply_node_resources(state, node)
    if not first["valid"] or second["reason"] != "normal_summon_used":
        raise AssertionError((first, second))


def validate_snake_eye_resources() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    report = simulate_opponent_graph(graph, ["Ash Blossom & Joyous Spring", "D.D. Crow"])
    if report["opponent_resource_valid_rate"] <= 0:
        raise AssertionError(report)


def validate_missing_starter() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    state = initial_resource_state(graph)
    state.hand = [card for card in state.hand if card != "Snake-Eye Ash"]
    result = validate_and_apply_node_resources(state, graph.nodes["se_ash"])
    if result["reason"] != "missing_required_card":
        raise AssertionError(result)


def validate_interruption_pivot() -> None:
    report = simulate_opponent_graph(get_opponent_graph(snake_eye_profile()), ["Ash Blossom & Joyous Spring"])
    if report["graph_pivot_rate"] <= 0 or "se_ash" not in report["best_interruption_nodes"]:
        raise AssertionError(report)


def validate_choke_resource_metrics() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring", "D.D. Crow"])
    if "opponent_resource_valid_rate" not in report or report["opponent_resource_valid_rate"] <= 0:
        raise AssertionError(report)


def validate_analyzer_output() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=700)
    if "Opponent resource valid rate:" not in output or "Opponent missing card failures:" not in output:
        raise AssertionError(output[-2000:])


def validate_integration() -> None:
    run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=800)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=800)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", timeout=2200)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
