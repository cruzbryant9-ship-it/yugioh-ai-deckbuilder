from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import score_deck_breakdown
from deck.card_text_parser import parse_card_text
from deck.line_graph import LineGraph, LineNode, line_graphs_for_archetype
from deck.line_validator import validate_line
from deck.resource_state import ResourceState
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4, desc: str = "") -> dict:
    return {"name": name, "type": card_type, "level": level, "race": "Dragon", "attribute": "LIGHT", "archetype": "Blue-Eyes", "desc": desc}


def main() -> None:
    checks = [
        ("parser detects reveal cost", validate_parser_reveal),
        ("parser detects discard/send/banish costs", validate_parser_costs),
        ("parser detects control condition", validate_parser_control),
        ("parser detects GY condition", validate_parser_gy),
        ("Alternative succeeds with reveal", validate_alternative_reveal_success),
        ("Alternative fails without reveal", validate_alternative_reveal_failure),
        ("Dictator send-to-GY cost works", validate_dictator_send_cost),
        ("GY condition fails when missing", validate_gy_condition_failure),
        ("score breakdown condition fields", validate_score_fields),
        ("regression gate checks condition fields", validate_regression_gate),
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
    print("Phase 5I validation complete.")


def validate_parser_reveal() -> None:
    parsed = parse_card_text("Reveal 1 Blue-Eyes White Dragon; Special Summon this card.")
    if not any(cost.get("type") == "reveal" for cost in parsed["costs"]):
        raise AssertionError(parsed)


def validate_parser_costs() -> None:
    text = "Discard 1 card; send 1 card from your Deck to the GY, then banish 1 card from your GY."
    parsed = parse_card_text(text)
    types = {cost["type"] for cost in parsed["costs"]}
    if not {"discard", "send_to_gy", "banish"}.issubset(types):
        raise AssertionError(parsed)


def validate_parser_control() -> None:
    parsed = parse_card_text("If you control a Blue-Eyes monster: add 1 card from your Deck.")
    if not any(condition.get("type") == "control" for condition in parsed["conditions"]):
        raise AssertionError(parsed)


def validate_parser_gy() -> None:
    parsed = parse_card_text(card("Test Dragon", desc="If this card is in your GY: Special Summon it."))
    if not any(condition.get("type") == "in_gy" for condition in parsed["conditions"]):
        raise AssertionError(parsed)


def validate_alternative_reveal_success() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Alternative"))
    hand = [card("Blue-Eyes Alternative White Dragon", level=8), card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    result = validate_line(hand, graph, deck=hand)
    if not result["valid"]:
        raise AssertionError(result)


def validate_alternative_reveal_failure() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Alternative"))
    hand = [card("Blue-Eyes Alternative White Dragon", level=8)]
    result = validate_line(hand, graph, deck=hand)
    if result["valid"] or result["failure_reason"] != "cost_reveal_unavailable":
        raise AssertionError(result)


def validate_dictator_send_cost() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Dictator"))
    hand = [card("Dictator of D.")]
    deck = [*hand, card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    result = validate_line(hand, graph, deck=deck)
    if not result["valid"]:
        raise AssertionError(result)
    if not any("Blue-Eyes White Dragon: deck->graveyard" in move for move in result["resource_movements"]):
        raise AssertionError(result["resource_movements"])


def validate_gy_condition_failure() -> None:
    graph = LineGraph("gy check", "Blue-Eyes", (LineNode("needs gy", "condition", conditions=({"type": "in_gy", "requirement": {"name": "Blue-Eyes White Dragon"}},)),))
    result = validate_line([card("Sage with Eyes of Blue")], graph)
    if result["valid"] or result["failure_reason"] != "condition_gy_unmet":
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = [
        card("Blue-Eyes Alternative White Dragon", level=8),
        card("Blue-Eyes White Dragon", "Normal Monster", 8),
        card("Dictator of D."),
        card("Blue-Eyes Jet Dragon", level=8),
        card("True Light", "Trap Card", 0),
        card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9),
    ] * 8
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "cost_condition_valid_rate",
        "cost_failure_rate_normalized",
        "condition_failure_rate_normalized",
        "reveal_cost_failure_rate",
        "discard_cost_failure_rate",
        "gy_condition_failure_rate",
        "control_condition_failure_rate",
    }
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(missing)


def validate_regression_gate() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "cost_condition_valid_rate": 0.4, "condition_failure_rate_normalized": 0.4}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "cost_condition_valid_rate": 0.9, "condition_failure_rate_normalized": 0.0}},
    )
    if result["accepted"]:
        raise AssertionError("Bad condition regression accepted")


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
