from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import score_deck_breakdown
from deck.hand_simulator import real_combo_report, simulate_hand
from deck.line_graph import LineGraph, LineNode
from deck.line_validator import validate_line
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4, race: str = "Dragon", attribute: str = "LIGHT", **extra):
    data = {"name": name, "type": card_type, "level": level, "race": race, "attribute": attribute, "archetype": "Blue-Eyes", "desc": ""}
    data.update(extra)
    return data


def main() -> None:
    checks = [
        ("optional failures are normalized away", validate_optional_failures_are_not_major),
        ("best-line failure counts when no line is valid", validate_best_line_failure),
        ("synchro exact level succeeds", validate_synchro_exact_success),
        ("synchro exact level fails", validate_synchro_exact_failure),
        ("ritual level succeeds with enough tribute", validate_ritual_level_success),
        ("ritual level fails without enough tribute", validate_ritual_level_failure),
        ("xyz scaffold validates matching levels", validate_xyz_scaffold),
        ("link scaffold validates material count", validate_link_scaffold),
        ("score breakdown normalized fields", validate_score_fields),
        ("regression gate ignores optional failures", validate_gate_ignores_optional_failures),
        ("regression gate rejects normalized failures", validate_gate_rejects_normalized_failures),
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
    print("Phase 5H validation complete.")


def blue_eyes_test_deck() -> list[dict]:
    return [
        card("Sage with Eyes of Blue", "Effect Monster", 1),
        card("The White Stone of Ancients", "Tuner Monster", 1),
        card("Blue-Eyes White Dragon", "Normal Monster", 8),
        card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9),
        card("Bingo Machine, Go!!!", "Spell Card", 0),
        card("Blue-Eyes Alternative White Dragon", "Effect Monster", 8),
    ]


def validate_optional_failures_are_not_major() -> None:
    deck = blue_eyes_test_deck()
    hand = [deck[0]]
    result = simulate_hand(deck, "Blue-Eyes", hand=hand)
    if not result["graph_valid_lines"]:
        raise AssertionError(result)
    if result["optional_line_failure_count"] <= 0:
        raise AssertionError("fixture should leave optional graph lines failed")
    if result["normalized_failure_categories"]:
        raise AssertionError(result["normalized_failure_categories"])


def validate_best_line_failure() -> None:
    deck = [card("Blue-Eyes White Dragon", "Normal Monster", 8), card("Chaos Form", "Spell Card", 0)]
    result = simulate_hand(deck, "Blue-Eyes", hand=list(deck))
    if not result["best_line_failure"] or not result["no_valid_line"]:
        raise AssertionError(result)


def validate_synchro_exact_success() -> None:
    graph = LineGraph("synchro", "Blue-Eyes", (LineNode("make synchro", "synchro_summon", synchro_requirements=({"tuner": True}, {"non_tuner": True}), extra_deck_card="Blue-Eyes Spirit Dragon", summon_type="synchro"),))
    hand = [card("The White Stone of Ancients", "Tuner Monster", 1), card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    spirit = card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)
    result = validate_line(hand, graph, deck=[*hand, spirit], extra_deck=[spirit])
    if not result["valid"]:
        raise AssertionError(result)


def validate_synchro_exact_failure() -> None:
    graph = LineGraph("synchro", "Blue-Eyes", (LineNode("make synchro", "synchro_summon", synchro_requirements=({"tuner": True}, {"non_tuner": True}), extra_deck_card="Blue-Eyes Spirit Dragon", summon_type="synchro"),))
    hand = [card("Wrong Tuner", "Tuner Monster", 2), card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    spirit = card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)
    result = validate_line(hand, graph, deck=[*hand, spirit], extra_deck=[spirit])
    if result["valid"] or result["failure_reason"] != "synchro_level_mismatch":
        raise AssertionError(result)


def validate_ritual_level_success() -> None:
    graph = LineGraph("ritual", "Blue-Eyes", (LineNode("ritual", "ritual_summon", ritual_spell="Chaos Form", ritual_level_requirement=8, typed_materials=({"monster": True},), summon_card="Blue-Eyes Chaos MAX Dragon", summon_type="ritual", cost_cards=("Chaos Form",)),))
    hand = [card("Chaos Form", "Spell Card", 0), card("Blue-Eyes Chaos MAX Dragon", "Ritual Monster", 8), card("Blue-Eyes White Dragon", "Normal Monster", 8)]
    result = validate_line(hand, graph, deck=hand)
    if not result["valid"]:
        raise AssertionError(result)


def validate_ritual_level_failure() -> None:
    graph = LineGraph("ritual", "Blue-Eyes", (LineNode("ritual", "ritual_summon", ritual_spell="Chaos Form", ritual_level_requirement=8, typed_materials=({"monster": True},), summon_card="Blue-Eyes Chaos MAX Dragon", summon_type="ritual", cost_cards=("Chaos Form",)),))
    hand = [card("Chaos Form", "Spell Card", 0), card("Blue-Eyes Chaos MAX Dragon", "Ritual Monster", 8), card("Small Dragon", "Effect Monster", 4)]
    result = validate_line(hand, graph, deck=hand)
    if result["valid"] or result["failure_reason"] != "insufficient_levels":
        raise AssertionError(result)


def validate_xyz_scaffold() -> None:
    graph = LineGraph("xyz", "Blue-Eyes", (LineNode("make xyz", "xyz_summon", summon_type="xyz", extra_deck_card="Rank 4 Test Dragon", xyz_material_count=2),))
    hand = [card("Level 4 Dragon A", level=4), card("Level 4 Dragon B", level=4)]
    xyz = card("Rank 4 Test Dragon", "XYZ Monster", 4)
    result = validate_line(hand, graph, deck=[*hand, xyz], extra_deck=[xyz])
    if not result["valid"]:
        raise AssertionError(result)


def validate_link_scaffold() -> None:
    graph = LineGraph("link", "Blue-Eyes", (LineNode("make link", "link_summon", summon_type="link", extra_deck_card="Link Test Dragon", link_requirements=({"monster": True}, {"monster": True})),))
    hand = [card("Dragon A"), card("Dragon B")]
    link = card("Link Test Dragon", "Link Monster", 0, linkval=2)
    result = validate_line(hand, graph, deck=[*hand, link], extra_deck=[link])
    if not result["valid"]:
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = blue_eyes_test_deck() * 8
    report = real_combo_report(deck, "Blue-Eyes", samples=4)
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {
        "optional_line_failure_rate",
        "best_line_failure_rate",
        "no_valid_line_rate",
        "normalized_search_failure_rate",
        "normalized_cost_failure_rate",
        "normalized_material_failure_rate",
        "synchro_exact_level_valid_rate",
        "synchro_level_failure_rate",
        "ritual_level_valid_rate",
        "ritual_level_failure_rate",
        "xyz_material_valid_rate",
        "link_material_valid_rate",
    }
    missing = required - set(report) | (required - set(breakdown))
    if missing:
        raise AssertionError(missing)


def validate_gate_ignores_optional_failures() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "optional_line_failure_rate": 1.0, "normalized_search_failure_rate": 0.0, "normalized_cost_failure_rate": 0.0, "normalized_material_failure_rate": 0.0}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "optional_line_failure_rate": 0.0, "normalized_search_failure_rate": 0.0, "normalized_cost_failure_rate": 0.0, "normalized_material_failure_rate": 0.0}},
    )
    if not result["accepted"]:
        raise AssertionError(result)


def validate_gate_rejects_normalized_failures() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "normalized_search_failure_rate": 0.5}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "normalized_search_failure_rate": 0.0}},
    )
    if result["accepted"]:
        raise AssertionError("Bad normalized failure regression accepted")


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
