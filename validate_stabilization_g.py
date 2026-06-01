from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.advisory_influence_budget import apply_advisory_nudges
from deck.generic_deck_repair import repair_generic_deck
from deck.generic_diff_index import (
    GENERIC_DIFF_INDEX_PATH,
    build_cross_archetype_diff_index,
    generic_diff_index_path,
    load_generic_diff_index,
    update_cross_archetype_diff_index,
)
from deck.rejection_classification import classify_rejection_causes, harmful_learning_eligible
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root

ROOT = Path(__file__).resolve().parent
PHASE6L_OUTPUT: str | None = None


def main() -> None:
    checks = [
        ("validator writes go to isolated memory only", validate_isolated_memory_writes),
        ("production diff index unchanged by validation probes", validate_phase6l_keeps_production_memory_clean),
        ("provenance metadata is added", validate_provenance_metadata),
        ("validator-generated records are ignored by production learning", validate_validator_records_ignored_in_production),
        ("rejection causes are classified", validate_rejection_cause_classification),
        ("legality rejection does not become harmful card memory", validate_legality_rejection_not_harmful),
        ("repair is idempotent", validate_repair_idempotence),
        ("advisory budget caps combined influence", validate_advisory_budget),
        ("Phase 6L validator still passes", validate_phase6l_still_passes),
        ("stabilization F validator still passes", validate_stabilization_f_still_passes),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
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
    print("Stabilization G validation complete.")


def validate_isolated_memory_writes() -> None:
    before = read_bytes(GENERIC_DIFF_INDEX_PATH)
    with temporary_isolated_memory_root("stabilization_g_memory_") as root:
        update_cross_archetype_diff_index([synthetic_result("Isolation Probe")], provenance=validator_provenance())
        isolated_path = generic_diff_index_path()
        if root not in isolated_path.parents or not isolated_path.exists():
            raise AssertionError((root, isolated_path))
    after = read_bytes(GENERIC_DIFF_INDEX_PATH)
    if before != after:
        raise AssertionError("production generic_diff_index.json changed during isolated write")


def validate_phase6l_keeps_production_memory_clean() -> None:
    before = read_bytes(GENERIC_DIFF_INDEX_PATH)
    run_phase6l_once()
    after = read_bytes(GENERIC_DIFF_INDEX_PATH)
    if before != after:
        raise AssertionError("validate_phase6l.py changed production generic_diff_index.json")


def validate_provenance_metadata() -> None:
    with temporary_isolated_memory_root("stabilization_g_provenance_"):
        update_cross_archetype_diff_index([synthetic_result("Provenance Probe")], provenance=validator_provenance())
        index = load_generic_diff_index()
        provenance = index.get("last_update_provenance", {})
        if provenance.get("source") != "validator" or provenance.get("validator_generated") is not True:
            raise AssertionError(provenance)
        if not index.get("provenance_log"):
            raise AssertionError(index)


def validate_validator_records_ignored_in_production() -> None:
    before = read_bytes(GENERIC_DIFF_INDEX_PATH)
    update_cross_archetype_diff_index([synthetic_result("Production Skip Probe")], provenance=validator_provenance())
    after = read_bytes(GENERIC_DIFF_INDEX_PATH)
    if before != after:
        raise AssertionError("validator-generated production update was not skipped")


def validate_rejection_cause_classification() -> None:
    score_row = {
        "improvement": -1.2,
        "runs": 1,
        "legal_run_count": 1,
        "confidence": 0.6,
        "repair_success": True,
        "rejection_reason": "no_safe_improvement",
    }
    legal_row = {
        "improvement": -4.0,
        "runs": 2,
        "legal_run_count": 1,
        "confidence": 0.6,
        "repair_success": False,
        "repair_used": True,
        "rejection_reason": "illegal_or_unrepaired_deck",
        "quota_warnings": ["main deck below 40 cards: 38"],
    }
    if "score_negative" not in classify_rejection_causes(score_row) or not harmful_learning_eligible(score_row):
        raise AssertionError(classify_rejection_causes(score_row))
    causes = classify_rejection_causes(legal_row)
    if "legality_failed" not in causes or harmful_learning_eligible(legal_row):
        raise AssertionError(causes)


def validate_legality_rejection_not_harmful() -> None:
    index = build_cross_archetype_diff_index(
        [
            {
                "archetype": "Legality Probe",
                "targeted_retest": {
                    "rejected_recommendations": [
                        {
                            "improvement": -9.0,
                            "runs": 1,
                            "legal_run_count": 0,
                            "confidence": 0.7,
                            "repair_success": False,
                            "repair_used": True,
                            "rejection_reason": "illegal_or_unrepaired_deck",
                            "quota_warnings": ["main deck below 40 cards: 35"],
                            "card_shift_explanation": {"copy_increases": {"Illegal Harmful Probe": 1}},
                            "package_replay_report": {
                                "copy_increases": {"Illegal Harmful Probe": 1},
                                "package_gains_losses": {"payoffs": 2},
                                "score_delta": -9.0,
                            },
                        }
                    ]
                },
            }
        ]
    )
    harmful = index["harmful_cards"]["additions"].get("Illegal Harmful Probe")
    if harmful:
        raise AssertionError(index["harmful_cards"])


def validate_repair_idempotence() -> None:
    pool = probe_card_pool()
    main = []
    for card in pool[:13]:
        main.extend([card, card, card])
    first = repair_generic_deck(main, [], "Probe", pool, {"analysis": None}, {"starters_searchers": 10, "extenders": 4, "payoffs": 3, "max_bricks": 4})
    second = repair_generic_deck(first["main"], first["extra"], "Probe", pool, {"analysis": None}, {"starters_searchers": 10, "extenders": 4, "payoffs": 3, "max_bricks": 4})
    if card_names(first["main"]) != card_names(second["main"]) or card_names(first["extra"]) != card_names(second["extra"]):
        raise AssertionError((first["repair_actions"], second["repair_actions"]))
    if first.get("repair_action_cap_reached") or second.get("repair_action_cap_reached"):
        raise AssertionError((first, second))


def validate_advisory_budget() -> None:
    result = apply_advisory_nudges({"diagnosis": 0.12, "future_diff_index": 0.12}, total_cap=0.15)
    applied = result["applied"]
    if round(sum(abs(value) for value in applied.values()), 6) > 0.15:
        raise AssertionError(result)
    disabled = apply_advisory_nudges({"diagnosis": 0.1}, enabled=False)
    if any(disabled["applied"].values()):
        raise AssertionError(disabled)


def validate_phase6l_still_passes() -> None:
    output = run_phase6l_once()
    if "Phase 6L validation complete" not in output:
        raise AssertionError(output[-2500:])


def validate_stabilization_f_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_result(archetype: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "provenance": validator_provenance(),
        "targeted_retest": {
            "accepted_recommendation": {
                "improvement": 1.0,
                "card_shift_explanation": {"copy_increases": {"Isolated Helpful": 1}},
                "package_replay_report": {
                    "copy_increases": {"Isolated Helpful": 1},
                    "package_gains_losses": {"starters_searchers": 1},
                    "score_delta": 1.0,
                },
            },
            "rejected_recommendations": [
                {
                    "improvement": -1.0,
                    "runs": 1,
                    "legal_run_count": 1,
                    "confidence": 0.6,
                    "repair_success": True,
                    "rejection_reason": "no_safe_improvement",
                    "card_shift_explanation": {"copy_increases": {"Isolated Harmful": 1}},
                    "package_replay_report": {
                        "copy_increases": {"Isolated Harmful": 1},
                        "package_gains_losses": {"interruptions": -1},
                        "score_delta": -1.0,
                    },
                }
            ],
        },
    }


def probe_card_pool() -> list[dict[str, Any]]:
    cards = []
    for index in range(1, 21):
        cards.append(
            {
                "name": f"Probe Starter {index}",
                "archetype": "Probe",
                "type": "Effect Monster",
                "race": "Warrior",
                "attribute": "LIGHT",
                "level": 4,
                "desc": 'Add 1 "Probe" card from your Deck to your hand.',
            }
        )
    for index in range(1, 6):
        cards.append(
            {
                "name": f"Probe Extra {index}",
                "archetype": "Probe",
                "type": "Fusion Monster",
                "race": "Warrior",
                "attribute": "LIGHT",
                "level": 8,
                "desc": "Probe Extra Deck payoff.",
            }
        )
    return cards


def validator_provenance() -> dict[str, Any]:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True, confidence_score=1.0, improvement=0.0)


def card_names(cards: list[dict[str, Any]]) -> list[str]:
    return sorted(str(card.get("name", "")) for card in cards)


def read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


def run_phase6l_once() -> str:
    global PHASE6L_OUTPUT
    if PHASE6L_OUTPUT is None:
        PHASE6L_OUTPUT = run_command("validate_phase6l.py", timeout=1800)
    return PHASE6L_OUTPUT


if __name__ == "__main__":
    main()
