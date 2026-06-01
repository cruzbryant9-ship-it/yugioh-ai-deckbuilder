from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import score_deck_breakdown
from deck.line_graph import LineGraph, LineNode, line_graphs_for_archetype
from deck.line_validator import validate_line
from deck.resource_state import ResourceState
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4):
    return {"name": name, "type": card_type, "level": level, "desc": "", "archetype": "Blue-Eyes"}


def main() -> None:
    checks = [
        ("ResourceState moves cards", validate_moves),
        ("normal summon once", validate_normal_once),
        ("once-per-turn once", validate_opt_once),
        ("missing material fails", validate_missing_material),
        ("missing search target fails", validate_missing_search),
        ("missing Extra Deck card fails", validate_missing_extra),
        ("valid Sage line reaches Spirit", validate_sage_line),
        ("invalid hand clear reason", validate_clear_reason),
        ("score breakdown resource fields", validate_score_fields),
        ("train/evaluate/compare still run", validate_commands),
        ("regression gates include resource checks", validate_resource_gate),
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
    print("Phase 5F validation complete.")


def validate_moves() -> None:
    state = ResourceState(hand=["A"])
    if not state.move_card("hand", "graveyard", "A"):
        raise AssertionError("move failed")
    if state.has_card("hand", "A") or not state.has_card("graveyard", "A"):
        raise AssertionError(state.snapshot())


def validate_normal_once() -> None:
    state = ResourceState()
    if not state.use_normal_summon() or state.use_normal_summon():
        raise AssertionError("normal summon gating failed")


def validate_opt_once() -> None:
    state = ResourceState()
    if not state.use_once_per_turn("x") or state.use_once_per_turn("x"):
        raise AssertionError("OPT gating failed")


def validate_missing_material() -> None:
    graph = LineGraph("material fail", "Blue-Eyes", (LineNode("fusion", "fusion_summon", required_materials=("Blue-Eyes White Dragon",), consumes_materials=("Blue-Eyes White Dragon",), extra_deck_card="Blue-Eyes Tyrant Dragon"),))
    result = validate_line([], graph, deck=[], extra_deck=[card("Blue-Eyes Tyrant Dragon", "Fusion Monster")])
    if result["valid"] or "missing_material" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_missing_search() -> None:
    graph = LineGraph("search fail", "Blue-Eyes", (LineNode("search", "search", search_card="Sage with Eyes of Blue", requires_in_deck=("Sage with Eyes of Blue",)),))
    result = validate_line([], graph, deck=[], extra_deck=[])
    if result["valid"] or "missing_search_target" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_missing_extra() -> None:
    graph = LineGraph("extra fail", "Blue-Eyes", (LineNode("synchro", "synchro_summon", extra_deck_card="Blue-Eyes Spirit Dragon"),))
    result = validate_line([], graph, deck=[], extra_deck=[])
    if result["valid"] or "missing_extra_deck_card" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_sage_line() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Sage"))
    deck = [card("Sage with Eyes of Blue"), card("The White Stone of Ancients", "Tuner Monster", 1), card("Blue-Eyes White Dragon", level=8), card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)]
    hand = [deck[0], deck[1], deck[2]]
    result = validate_line(hand, graph, deck=deck, extra_deck=[deck[3]])
    if not result["valid"] or "Blue-Eyes Spirit Dragon" not in result["endboard"]:
        raise AssertionError(result)


def validate_clear_reason() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Alternative"))
    result = validate_line([card("Blue-Eyes Alternative White Dragon", level=8)], graph, deck=[], extra_deck=[])
    if result["valid"] or not result["failure_reason"]:
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = [
        card("Sage with Eyes of Blue"),
        card("The White Stone of Ancients"),
        card("Blue-Eyes White Dragon", level=8),
        card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9),
    ] * 10
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {"resource_valid_line_rate", "material_failure_rate", "search_failure_rate", "extra_deck_failure_rate", "cost_failure_rate"}
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


def validate_resource_gate() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "resource_valid_line_rate": 0.2, "missing_material_rate": 0.5}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "resource_valid_line_rate": 0.8, "missing_material_rate": 0.0}},
    )
    if result["accepted"]:
        raise AssertionError("Bad resource regression accepted")


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
