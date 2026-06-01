from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import score_deck_breakdown
from deck.card_metadata import card_matches_requirement, get_card_level, is_light, is_tuner
from deck.line_graph import LineGraph, LineNode
from deck.line_validator import validate_line
from SystemAIYugioh.regression_gates import evaluate_training_batch

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", level: int = 4, race: str = "Dragon", attribute: str = "LIGHT"):
    return {"name": name, "type": card_type, "level": level, "race": race, "attribute": attribute, "archetype": "Blue-Eyes", "desc": ""}


def main() -> None:
    checks = [
        ("metadata helpers", validate_metadata),
        ("tuner requirement", validate_tuner),
        ("non-tuner rejects tuner", validate_non_tuner),
        ("Level 8 Dragon LIGHT requirement", validate_level_dragon_light),
        ("Synchro succeeds", validate_synchro_success),
        ("Synchro fails without tuner", validate_synchro_no_tuner),
        ("Ritual fails without Chaos Form", validate_ritual_no_spell),
        ("Ritual fails without tribute", validate_ritual_no_tribute),
        ("Fusion fails without named materials", validate_fusion_named_failure),
        ("score breakdown typed fields", validate_score_fields),
        ("train/evaluate/compare still run", validate_commands),
        ("regression gates include typed checks", validate_typed_gate),
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
    print("Phase 5G validation complete.")


def validate_metadata() -> None:
    blue_eyes = card("Blue-Eyes White Dragon", level=8)
    if get_card_level(blue_eyes) != 8 or not is_light(blue_eyes):
        raise AssertionError(blue_eyes)


def validate_tuner() -> None:
    stone = card("The White Stone of Ancients", "Tuner Monster", 1)
    if not is_tuner(stone) or not card_matches_requirement(stone, {"tuner": True}):
        raise AssertionError(stone)


def validate_non_tuner() -> None:
    stone = card("The White Stone of Ancients", "Tuner Monster", 1)
    if card_matches_requirement(stone, {"non_tuner": True}):
        raise AssertionError("tuner matched non_tuner")


def validate_level_dragon_light() -> None:
    blue_eyes = card("Blue-Eyes White Dragon", level=8)
    requirement = {"level": 8, "type_contains": "Dragon", "attribute": "LIGHT"}
    if not card_matches_requirement(blue_eyes, requirement):
        raise AssertionError(requirement)


def validate_synchro_success() -> None:
    graph = LineGraph("synchro", "Blue-Eyes", (LineNode("make synchro", "synchro_summon", synchro_requirements=({"tuner": True}, {"level": 8, "non_tuner": True}), extra_deck_card="Blue-Eyes Spirit Dragon", summon_type="synchro"),))
    hand = [card("The White Stone of Ancients", "Tuner Monster", 1), card("Blue-Eyes White Dragon", level=8)]
    spirit = card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)
    result = validate_line(hand, graph, deck=[*hand, spirit], extra_deck=[spirit])
    if not result["valid"]:
        raise AssertionError(result)


def validate_synchro_no_tuner() -> None:
    graph = LineGraph("synchro", "Blue-Eyes", (LineNode("make synchro", "synchro_summon", synchro_requirements=({"tuner": True}, {"level": 8, "non_tuner": True}), extra_deck_card="Blue-Eyes Spirit Dragon", summon_type="synchro"),))
    hand = [card("Blue-Eyes White Dragon", level=8), card("Blue-Eyes Alternative White Dragon", level=8)]
    spirit = card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)
    result = validate_line(hand, graph, deck=[*hand, spirit], extra_deck=[spirit])
    if result["valid"] or "missing_tuner" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_ritual_no_spell() -> None:
    graph = LineGraph("ritual", "Blue-Eyes", (LineNode("ritual", "ritual_summon", ritual_spell="Chaos Form", ritual_level_requirement=8, typed_materials=({"level": 8, "monster": True},), summon_card="Blue-Eyes Chaos MAX Dragon", summon_type="ritual"),))
    result = validate_line([card("Blue-Eyes Chaos MAX Dragon", "Ritual Monster", 8), card("Blue-Eyes White Dragon", level=8)], graph)
    if result["valid"] or "missing_ritual_spell" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_ritual_no_tribute() -> None:
    graph = LineGraph("ritual", "Blue-Eyes", (LineNode("ritual", "ritual_summon", ritual_spell="Chaos Form", ritual_level_requirement=8, typed_materials=({"level": 8, "monster": True},), summon_card="Blue-Eyes Chaos MAX Dragon", summon_type="ritual"),))
    result = validate_line([card("Chaos Form", "Spell Card", 0), card("Blue-Eyes Chaos MAX Dragon", "Ritual Monster", 8)], graph)
    if result["valid"] or "insufficient_levels" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_fusion_named_failure() -> None:
    graph = LineGraph("fusion", "Blue-Eyes", (LineNode("fusion", "fusion_summon", named_materials=({"name": "Blue-Eyes White Dragon"}, {"name": "Blue-Eyes White Dragon"}), extra_deck_card="Blue-Eyes Twin Burst Dragon", summon_type="fusion"),))
    twin = card("Blue-Eyes Twin Burst Dragon", "Fusion Monster", 10)
    result = validate_line([card("Blue-Eyes White Dragon", level=8)], graph, deck=[twin], extra_deck=[twin])
    if result["valid"] or "missing_named_material" not in str(result["failure_reason"]):
        raise AssertionError(result)


def validate_score_fields() -> None:
    deck = [card("The White Stone of Ancients", "Tuner Monster", 1), card("Blue-Eyes White Dragon", level=8), card("Blue-Eyes Spirit Dragon", "Synchro Monster", 9)] * 14
    breakdown = score_deck_breakdown(deck, "Blue-Eyes", "meta")
    required = {"typed_material_valid_rate", "synchro_material_failure_rate", "fusion_material_failure_rate", "ritual_material_failure_rate", "link_material_failure_rate", "named_material_failure_rate"}
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


def validate_typed_gate() -> None:
    result = evaluate_training_batch(
        {"successful_runs": 2, "average_score": 150, "average_real_combo_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "typed_material_valid_rate": 0.2, "synchro_material_failure_rate": 0.5}, "average_package_quality_score": 80, "package_quota_violations": []},
        {"average_score": 150, "average_real_combo_report_values": {"playable_hand_rate": 0.9, "brick_rate": 0.0, "typed_material_valid_rate": 0.8, "synchro_material_failure_rate": 0.0}},
    )
    if result["accepted"]:
        raise AssertionError("Bad typed material regression accepted")


def run_command(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()

