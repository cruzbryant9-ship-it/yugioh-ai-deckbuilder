from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path
from typing import Any

import deck.advisory_influence_budget as advisory_budget_module
from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.generic_deck_repair import repair_generic_deck
from deck.generic_repair_diagnostics import diagnose_under_40_repair
from deck.generic_tuner import tune_generic_deck
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root
from generic_archetype_benchmark import run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("phase6n_memory_"):
        checks = [
            ("35-card generic deck repairs to 40 with safe fillers", validate_35_card_repair),
            ("repair respects blocked cards", validate_blocked_cards_removed),
            ("repair respects copy limits", validate_copy_limits),
            ("Runick-like spell/trap-heavy deck completes or reports precise cause", validate_runick_completion),
            ("safe filler does not overfill", validate_no_overfill),
            ("under-40 diagnostics report missing count", validate_diagnostics_missing_count),
            ("advisory bias remains capped", validate_advisory_cap),
            ("kill switch still disables diff-index bias", validate_kill_switch),
            ("generic benchmark reports repair/advisory calibration", validate_benchmark_reporting),
            ("Phase 6M validator still passes", validate_phase6m_still_passes),
            ("Stabilization G validator still passes", validate_stabilization_g_still_passes),
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
        print_sample()
        print("Phase 6N validation complete.")


def validate_35_card_repair() -> None:
    pool = [card("Probe Core", "Spell Card", "Probe core."), card("Probe Core 2", "Spell Card", "Probe core.")] + safe_filler_pool()
    main = [card("Probe Core", "Spell Card", "Probe core.") for _ in range(3)] * 11 + [card("Probe Core 2", "Spell Card", "Probe core.")] * 2
    result = repair_generic_deck(main[:35], [], "Probe", pool, {"analysis": None}, quota(), mode="meta")
    if len(result["main"]) != 40 or not result["legal"] or result.get("safe_filler_used_count", 0) < 1:
        raise AssertionError(result)
    if result.get("completed_by_safe_filler") is not True:
        raise AssertionError(result)


def validate_blocked_cards_removed() -> None:
    pool = synthetic_pool()
    blocked = card("Forbidden Probe", "Spell Card", "Blocked.", ban="Forbidden")
    main = [blocked] + [card("Probe Core", "Spell Card", "Probe core.")] * 34
    result = repair_generic_deck(main, [], "Probe", pool + [blocked], {"analysis": None}, quota(), mode="meta")
    names = [c["name"] for c in result["main"]]
    if "Forbidden Probe" in names or len(result["main"]) != 40:
        raise AssertionError(result)


def validate_copy_limits() -> None:
    pool = synthetic_pool()
    limited = card("Limited Probe", "Spell Card", "Limited.", ban="Limited")
    main = [limited, limited, limited] + [card("Probe Core", "Spell Card", "Probe core.")] * 34
    result = repair_generic_deck(main, [], "Probe", pool + [limited], {"analysis": None}, quota(), mode="meta")
    names = [c["name"] for c in result["main"]]
    if names.count("Limited Probe") > 1 or len(result["main"]) != 40:
        raise AssertionError(result)


def validate_runick_completion() -> None:
    cards = CardDatabase().load_cards()
    deck, report = build_generic_deck("Runick", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    if len(main) != 40:
        diagnostics = report.get("under_40_diagnostics", {})
        if not diagnostics.get("under_40_reason") or not diagnostics.get("recommended_repair_strategy"):
            raise AssertionError(report)
    if report.get("repair_strategy_used") == "safe_generic_filler" and report.get("safe_filler_used_count", 0) < 1:
        raise AssertionError(report)


def validate_no_overfill() -> None:
    pool = synthetic_pool()
    main = [card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(40)]
    result = repair_generic_deck(main, [], "Probe", pool, {"analysis": None}, quota(), mode="meta")
    if len(result["main"]) != 40:
        raise AssertionError(result)


def validate_diagnostics_missing_count() -> None:
    pool = synthetic_pool()
    main = [card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(35)]
    diagnostics = diagnose_under_40_repair(main, "Probe", pool, {}, quota(), "meta")
    if diagnostics.get("missing_count") != 5:
        raise AssertionError(diagnostics)


def validate_advisory_cap() -> None:
    cards = CardDatabase().load_cards()
    report = tune_generic_deck("Branded", cards, mode="meta", runs=2, update_memory=False)
    budget = report.get("advisory_budget_used", {})
    used = sum(abs(float(value or 0)) for value in budget.get("used_by_source", {}).values())
    if round(used, 6) > 0.15:
        raise AssertionError(budget)


def validate_kill_switch() -> None:
    previous = advisory_budget_module.ADVISORY_KILL_SWITCH
    try:
        advisory_budget_module.ADVISORY_KILL_SWITCH = True
        cards = CardDatabase().load_cards()
        report = tune_generic_deck("Branded", cards, mode="meta", runs=2, update_memory=False)
        if report.get("diff_index_bias_used"):
            raise AssertionError(report.get("advisory_budget_used"))
    finally:
        advisory_budget_module.ADVISORY_KILL_SWITCH = previous


def validate_benchmark_reporting() -> None:
    report = run_benchmark(["Runick"], mode="meta", runs=1, provenance=validator_provenance())
    summary = report.get("summary", {})
    for key in ("decks_completed_by_safe_filler", "under_40_diagnostics", "repair_strategy_counts", "advisory_bias_calibration"):
        if key not in summary:
            raise AssertionError(summary)


def validate_phase6m_still_passes() -> None:
    run_command("validate_phase6m.py", timeout=2400)


def validate_stabilization_g_still_passes() -> None:
    run_command("validate_stabilization_g.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_pool() -> list[dict[str, Any]]:
    pool = [card(f"Probe Core {idx}", "Spell Card", 'Add 1 "Probe" card from your Deck to your hand.') for idx in range(1, 16)]
    pool.extend(safe_filler_pool())
    return pool


def safe_filler_pool() -> list[dict[str, Any]]:
    fillers = [
        "Ash Blossom & Joyous Spring",
        "Infinite Impermanence",
        "Effect Veiler",
        "Droll & Lock Bird",
        "D.D. Crow",
        "Nibiru, the Primal Being",
        "Ghost Belle & Haunted Mansion",
        "Ghost Ogre & Snow Rabbit",
        "Called by the Grave",
        "Crossout Designator",
        "Triple Tactics Talent",
        "Triple Tactics Thrust",
        "Upstart Goblin",
        "Pot of Prosperity",
        "Pot of Extravagance",
        "Pot of Desires",
        "Pot of Duality",
        "Small World",
        "Book of Moon",
        "Cosmic Cyclone",
    ]
    monsters = {"Ash Blossom & Joyous Spring", "Effect Veiler", "Droll & Lock Bird", "D.D. Crow", "Nibiru, the Primal Being", "Ghost Belle & Haunted Mansion", "Ghost Ogre & Snow Rabbit"}
    return [card(name, "Spell Card" if name not in monsters else "Effect Monster", "Safe filler.", archetype="Generic") for name in fillers]


def card(name: str, card_type: str, desc: str, ban: str | None = None, archetype: str = "Probe") -> dict[str, Any]:
    payload = {"name": name, "type": card_type, "desc": desc, "archetype": archetype}
    if ban:
        payload["banlist_info"] = {"ban_tcg": ban}
    return payload


def quota() -> dict[str, int]:
    return {"starters_searchers": 10, "extenders": 4, "payoffs": 3, "interruptions": 8, "board_breakers": 2, "max_bricks": 4}


def validator_provenance() -> dict[str, Any]:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)


def print_sample() -> None:
    cards = CardDatabase().load_cards()
    deck, report = build_generic_deck("Runick", cards, mode="meta", use_ratio_memory=False)
    main, _extra = split_deck(deck)
    print("SAMPLE: Runick main count:", len(main))
    print("SAMPLE: Runick repair strategy:", report.get("repair_strategy_used"))
    print("SAMPLE: Runick safe filler count:", report.get("safe_filler_used_count"))
    print("SAMPLE: Runick diagnostics:", report.get("under_40_diagnostics"))


def run_command(*args: str, timeout: int = 180) -> str:
    env = os.environ.copy()
    env.pop("YUGIOH_AI_MEMORY_ROOT", None)
    env.pop("YUGIOH_AI_TEST_MODE", None)
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
