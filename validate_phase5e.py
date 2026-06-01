from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import build_deck, score_deck_breakdown
from deck.hand_simulator import simulate_hand
from deck.line_graph import LineGraph, LineNode, line_graphs_for_archetype
from deck.line_validator import validate_line
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4, desc: str = ""):
    return {"name": name, "type": card_type, "level": level, "desc": desc, "archetype": "Blue-Eyes"}


def main() -> None:
    checks = [
        ("graph schema exists", validate_graph_schema),
        ("valid Sage + Stone completes Spirit line", validate_sage_graph),
        ("invalid hand fails with useful reason", validate_invalid_failure),
        ("normal summon duplicate fails", validate_normal_duplicate),
        ("once-per-turn duplicate fails", validate_opt_duplicate),
        ("payoff without material fails", validate_payoff_material_failure),
        ("hand simulator includes graph metrics", validate_hand_graph_metrics),
        ("score breakdown includes graph fields", validate_score_graph_fields),
        ("train/evaluate/compare still run", validate_commands),
        ("regression gates include graph checks", validate_gate_graph_checks),
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
    print("Phase 5E validation complete.")


def validate_graph_schema() -> None:
    graphs = line_graphs_for_archetype("Blue-Eyes")
    if len(graphs) < 9:
        raise AssertionError(f"Expected graph lines, got {len(graphs)}")
    node = graphs[0].nodes[0].to_dict()
    for key in ("action_type", "requires_cards", "produces_cards", "once_per_turn_tag", "payoff_score"):
        if key not in node:
            raise AssertionError(f"Missing node key {key}")


def validate_sage_graph() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Sage"))
    spirit = card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)
    hand = [card("Sage with Eyes of Blue"), card("The White Stone of Ancients", "Tuner Monster", 1), card("Blue-Eyes White Dragon", level=8)]
    result = validate_line(hand, graph, deck=[*hand, spirit], extra_deck=[spirit])
    if not result["valid"] or "Blue-Eyes Spirit Dragon" not in result["endboard"]:
        raise AssertionError(result)


def validate_invalid_failure() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Chaos Form"))
    result = validate_line([card("Blue-Eyes Chaos MAX Dragon", "Ritual Monster", 8)], graph)
    if result["valid"] or not result["failure_reason"]:
        raise AssertionError(result)


def validate_normal_duplicate() -> None:
    graph = LineGraph("bad normal", "Blue-Eyes", (LineNode("n1", "opener", normal_summon_required=True), LineNode("n2", "summon", normal_summon_required=True)))
    result = validate_line([], graph)
    if result["valid"] or "normal_summon_used" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_opt_duplicate() -> None:
    graph = LineGraph("bad opt", "Blue-Eyes", (LineNode("a", "search", once_per_turn_tag="same"), LineNode("b", "search", once_per_turn_tag="same")))
    result = validate_line([], graph)
    if result["valid"] or "once_per_turn_conflict" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_payoff_material_failure() -> None:
    graph = next(graph for graph in line_graphs_for_archetype("Blue-Eyes") if graph.name.startswith("Alternative"))
    result = validate_line([card("Blue-Eyes Alternative White Dragon", level=8)], graph)
    if result["valid"] or not any(reason in str(result["failure_reason"]) for reason in ("missing_required_card", "cost_reveal_unavailable")):
        raise AssertionError(result)


def validate_hand_graph_metrics() -> None:
    hand = [card("Sage with Eyes of Blue"), card("The White Stone of Ancients"), card("Blue-Eyes White Dragon", level=8), card("Bingo Machine, Go!!!", "Spell Card"), card("True Light", "Trap Card")]
    result = simulate_hand(hand, "Blue-Eyes", hand=hand)
    for key in ("graph_valid_lines", "best_graph_line", "graph_failures", "graph_payoff_score"):
        if key not in result:
            raise AssertionError(f"Missing hand graph metric {key}")


def validate_score_graph_fields() -> None:
    deck, _ = build_deck(CardDatabase().load_cards(), "Blue-Eyes")
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {"graph_valid_line_rate", "graph_average_line_score", "graph_average_payoff_score", "graph_average_resource_score", "graph_average_risk_score", "graph_failed_line_rate", "most_common_graph_failure_reason"}
    missing = required - set(breakdown)
    if missing:
        raise AssertionError(f"Missing graph fields: {missing}")


def validate_commands() -> None:
    for args in (
        ("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2"),
        ("compare_engines.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-engine", "1"),
    ):
        run_command(*args)


def validate_gate_graph_checks() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "graph_valid_line_rate": 0.2, "graph_average_line_score": 2, "graph_failed_line_rate": 0.7, "graph_average_risk_score": 4}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "graph_valid_line_rate": 0.8, "graph_average_line_score": 7, "graph_failed_line_rate": 0.1, "graph_average_risk_score": 1}},
    )
    if result["accepted"]:
        raise AssertionError("Bad graph regression was accepted")


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
