from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.choke_simulator import simulate_choke_points
from deck.curated_opponent_library import curated_to_opponent_profile, find_curated_profile
from deck.opponent_branch_graph import get_opponent_graph, list_opponent_graphs
from deck.opponent_graph_simulator import simulate_opponent_graph
from deck.side_deck_planner import build_side_deck

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", desc="Negate a monster effect."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Ghost Belle & Haunted Mansion", desc="Negate GY movement."),
        card("Bystial Magnamhut", desc="Banish a LIGHT or DARK monster from either GY."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
    ]


def main() -> None:
    checks = [
        ("opponent branch graph loads", validate_graphs_load),
        ("Snake-Eye graph has ordered nodes", validate_snake_eye_ordered),
        ("Ash maps to search node", validate_ash_node),
        ("Crow maps to GY node", validate_crow_node),
        ("Imperm maps to field-effect node", validate_imperm_node),
        ("simulator finds best interruption node", validate_best_node),
        ("simulator records pivot route", validate_pivot_route),
        ("side planner includes graph reasons", validate_side_reasons),
        ("analyze_opponent_deck prints graph route", validate_analyzer_graph),
        ("fallback works without graph", validate_fallback),
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
    print("Phase 5V validation complete.")


def snake_eye_profile():
    curated = find_curated_profile("Snake-Eye")
    if not curated:
        raise AssertionError("Snake-Eye curated profile missing")
    return curated_to_opponent_profile(curated)


def validate_graphs_load() -> None:
    required = {"Snake-Eye", "Tenpai", "Labrynth", "Branded", "Kashtira", "Runick", "Floowandereeze", "Tearlaments"}
    if not required.issubset(set(list_opponent_graphs())):
        raise AssertionError(list_opponent_graphs())


def validate_snake_eye_ordered() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    if not graph or "se_ash" not in graph.nodes or graph.nodes["se_ash"].if_resolved_go_to != "se_poplar":
        raise AssertionError(graph)


def validate_ash_node() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    report = simulate_opponent_graph(graph, ["Ash Blossom & Joyous Spring"])
    if "se_ash" not in report["best_interruption_nodes"]:
        raise AssertionError(report)


def validate_crow_node() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    report = simulate_opponent_graph(graph, ["D.D. Crow"])
    if "se_princess" not in report["best_interruption_nodes"]:
        raise AssertionError(report)


def validate_imperm_node() -> None:
    graph = get_opponent_graph(snake_eye_profile())
    report = simulate_opponent_graph(graph, ["Infinite Impermanence"])
    if not {"se_ash", "se_poplar", "se_flamb"} & set(report["best_interruption_nodes"]):
        raise AssertionError(report)


def validate_best_node() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring", "D.D. Crow", "Infinite Impermanence"])
    if report["graph_stop_rate"] <= 0 or not report["best_interruption_nodes"]:
        raise AssertionError(report)


def validate_pivot_route() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring"])
    if report["graph_pivot_rate"] <= 0:
        raise AssertionError(report)


def validate_side_reasons() -> None:
    report = build_side_deck(database(), "Blue-Eyes", snake_eye_profile(), database(), going="second")
    reasons = {reason for values in report["reasons"].values() for reason in values}
    if "graph_interruption_node" not in reasons or report["graph_stop_rate"] <= 0:
        raise AssertionError(report)


def validate_analyzer_graph() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=700)
    if "Opponent graph route:" not in output or "Best interruption nodes:" not in output:
        raise AssertionError(output[-2000:])


def validate_fallback() -> None:
    report = simulate_choke_points("unknown_meta", ["Ash Blossom & Joyous Spring"])
    if report["graph_stop_rate"] != 0 or report["likely_lines"]:
        raise AssertionError(report)


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
