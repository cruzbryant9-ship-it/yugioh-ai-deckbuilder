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


def card(name: str, card_type: str = "Effect Monster", level: int = 4) -> dict:
    return {"name": name, "type": card_type, "level": level, "race": "Dragon", "attribute": "LIGHT", "archetype": "Blue-Eyes", "desc": ""}


def main() -> None:
    checks = [
        ("ResourceState records events", validate_resource_history),
        ("history condition succeeds", validate_history_condition_success),
        ("history condition fails", validate_history_condition_failure),
        ("branch chooses highest valid option", validate_branch_choice),
        ("no valid branch fails", validate_no_valid_branch),
        ("Blue-Eyes Bingo branch resolves", validate_bingo_branch),
        ("Dictator uses GY history", validate_dictator_history),
        ("score breakdown history fields", validate_score_fields),
        ("regression gate checks branch/history", validate_regression_gate),
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
    print("Phase 5J validation complete.")


def validate_resource_history() -> None:
    state = ResourceState(hand=[card("Blue-Eyes Jet Dragon")])
    if not state.summon_from_hand("Blue-Eyes Jet Dragon"):
        raise AssertionError("summon failed")
    state.record_event("activated", "True Light")
    if not state.was_summoned_this_turn("Blue-Eyes Jet Dragon"):
        raise AssertionError(state.snapshot())
    if not state.was_activated_this_turn("True Light"):
        raise AssertionError(state.snapshot())


def validate_history_condition_success() -> None:
    graph = LineGraph(
        "history ok",
        "Blue-Eyes",
        (
            LineNode("summon", "special_summon", summon_card="Blue-Eyes Jet Dragon", summon_type="special"),
            LineNode("check", "condition", conditions=({"type": "was_summoned_this_turn", "card_name": "Blue-Eyes Jet Dragon"},)),
        ),
    )
    result = validate_line([card("Blue-Eyes Jet Dragon", level=8)], graph)
    if not result["valid"]:
        raise AssertionError(result)


def validate_history_condition_failure() -> None:
    graph = LineGraph("history fail", "Blue-Eyes", (LineNode("check", "condition", conditions=({"type": "was_summoned_this_turn", "card_name": "Blue-Eyes Jet Dragon"},)),))
    result = validate_line([card("Sage with Eyes of Blue")], graph)
    if result["valid"] or result["failure_reason"] != "summon_history_missing":
        raise AssertionError(result)


def validate_branch_choice() -> None:
    graph = LineGraph(
        "branch choice",
        "Blue-Eyes",
        (
            LineNode(
                "choose",
                "search",
                branches=(
                    {"name": "low", "effects": ({"type": "search", "card": "Sage with Eyes of Blue"},), "score": 2},
                    {"name": "high", "effects": ({"type": "search", "card": "Blue-Eyes Alternative White Dragon"},), "score": 8},
                ),
            ),
        ),
    )
    deck = [card("Sage with Eyes of Blue"), card("Blue-Eyes Alternative White Dragon", level=8)]
    result = validate_line([], graph, deck=deck)
    if not result["valid"] or result["chosen_branches"][0]["branch"] != "high":
        raise AssertionError(result)


def validate_no_valid_branch() -> None:
    graph = LineGraph("no branch", "Blue-Eyes", (LineNode("choose", "search", branches=({"name": "missing", "effects": ({"type": "search", "card": "Missing Card"},), "score": 9},)),))
    result = validate_line([], graph, deck=[])
    if result["valid"] or "condition_target_unavailable" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_bingo_branch() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Bingo"))
    hand = [card("Bingo Machine, Go!!!", "Spell Card", 0)]
    deck = [*hand, card("Blue-Eyes Alternative White Dragon", level=8), card("Sage with Eyes of Blue")]
    result = validate_line(hand, graph, deck=deck)
    if not result["valid"] or not result["chosen_branches"]:
        raise AssertionError(result)


def validate_dictator_history() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Dictator"))
    hand = [card("Dictator of D.")]
    deck = [*hand, card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    result = validate_line(hand, graph, deck=deck)
    if not result["valid"] or not result["resource_state"]["sent_to_gy_this_turn"]:
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = [
        card("Bingo Machine, Go!!!", "Spell Card", 0),
        card("Blue-Eyes Alternative White Dragon", level=8),
        card("Blue-Eyes White Dragon", "Normal Monster", 8),
        card("Dictator of D."),
        card("Blue-Eyes Jet Dragon", level=8),
        card("True Light", "Trap Card", 0),
        card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9),
    ] * 7
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "branch_valid_rate",
        "no_valid_branch_rate",
        "average_branch_score",
        "history_condition_failure_rate",
        "summon_history_failure_rate",
        "gy_history_failure_rate",
        "activation_history_failure_rate",
        "resolution_history_failure_rate",
    }
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(missing)


def validate_regression_gate() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "branch_valid_rate": 0.2, "no_valid_branch_rate": 0.4, "history_condition_failure_rate": 0.4}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "branch_valid_rate": 0.8, "no_valid_branch_rate": 0.0, "history_condition_failure_rate": 0.0}},
    )
    if result["accepted"]:
        raise AssertionError("Bad branch/history regression accepted")


def validate_commands() -> None:
    for args in (
        ("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1"),
    ):
        run_command(*args)


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
