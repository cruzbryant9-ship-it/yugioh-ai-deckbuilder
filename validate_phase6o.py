from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.generic_deck_repair import repair_generic_deck
from deck.generic_filler_selector import select_contextual_fillers
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root
from generic_archetype_benchmark import run_benchmark, save_reports

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("phase6o_memory_"):
        checks = [
            ("interruption pressure prefers interruption filler", validate_interruption_pressure),
            ("spell/trap-heavy archetype receives compatible filler", validate_spell_trap_texture),
            ("filler respects blocked cards", validate_blocked_fillers),
            ("filler respects copy limits", validate_copy_limits),
            ("filler does not overfill above 40", validate_no_overfill),
            ("Runick still completes to 40", validate_runick_completion),
            ("benchmark report includes contextual filler metadata", validate_benchmark_metadata),
            ("Phase 6N validator still passes", validate_phase6n_still_passes),
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
        print("Phase 6O validation complete.")


def validate_interruption_pressure() -> None:
    current = [card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(35)]
    result = select_contextual_fillers(
        "Probe",
        "meta",
        5,
        safe_filler_pool(),
        current,
        {"starters_searchers": 10, "interruptions": 0, "board_breakers": 2, "recovery": 2},
    )
    selected = set(result.get("selected_fillers", []))
    if not selected & {"Ash Blossom & Joyous Spring", "Infinite Impermanence", "Effect Veiler", "Droll & Lock Bird", "D.D. Crow"}:
        raise AssertionError(result)


def validate_spell_trap_texture() -> None:
    current = [card(f"Runick Probe {idx}", "Spell Card", 'Activate 1 "Runick" effect.') for idx in range(35)]
    result = select_contextual_fillers(
        "Runick",
        "innovation",
        5,
        safe_filler_pool(),
        current,
        {"starters_searchers": 0, "interruptions": 8, "board_breakers": 2, "recovery": 0},
        diagnosis={"suspected_causes": ["starter_density_low"]},
    )
    selected = set(result.get("selected_fillers", []))
    if not selected & {"Triple Tactics Talent", "Triple Tactics Thrust", "Upstart Goblin", "Pot of Prosperity", "Pot of Extravagance", "Pot of Desires", "Pot of Duality", "Small World"}:
        raise AssertionError(result)
    if not result.get("context", {}).get("spell_trap_heavy"):
        raise AssertionError(result)


def validate_blocked_fillers() -> None:
    pool = [card("Ash Blossom & Joyous Spring", "Effect Monster", "Discard this card.", ban="Forbidden")]
    pool.extend([c for c in safe_filler_pool() if c["name"] != "Ash Blossom & Joyous Spring"])
    current = [card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(35)]
    result = select_contextual_fillers("Probe", "meta", 5, pool, current, {"interruptions": 0})
    if "Ash Blossom & Joyous Spring" in result.get("selected_fillers", []):
        raise AssertionError(result)
    rejected = {row.get("name"): row.get("reason") for row in result.get("rejected_fillers", [])}
    if rejected.get("Ash Blossom & Joyous Spring") != "blocked_or_forbidden":
        raise AssertionError(result)


def validate_copy_limits() -> None:
    pool = safe_filler_pool()
    current = [card("Ash Blossom & Joyous Spring", "Effect Monster", "Safe filler.") for _ in range(3)]
    current.extend(card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(32))
    result = select_contextual_fillers("Probe", "meta", 5, pool, current, {"interruptions": 0})
    selected = result.get("selected_fillers", [])
    if "Ash Blossom & Joyous Spring" in selected:
        raise AssertionError(result)


def validate_no_overfill() -> None:
    pool = synthetic_pool()
    main = [card(f"Probe Core {idx}", "Spell Card", "Probe core.") for idx in range(40)]
    result = repair_generic_deck(main, [], "Probe", pool, {"analysis": None}, quota(), mode="meta")
    if len(result["main"]) != 40 or result.get("selected_fillers"):
        raise AssertionError(result)


def validate_runick_completion() -> None:
    cards = CardDatabase().load_cards()
    deck, report = build_generic_deck("Runick", cards, mode="meta", use_ratio_memory=False)
    main, _extra = split_deck(deck)
    if len(main) != 40:
        raise AssertionError(report)
    if report.get("safe_filler_used_count", 0) and "contextual_filler_used" not in report:
        raise AssertionError(report)


def validate_benchmark_metadata() -> None:
    report = run_benchmark(["Runick"], mode="meta", runs=1, provenance=validator_provenance())
    summary = report.get("summary", {})
    for key in ("contextual_filler_usage_count", "selected_filler_counts", "filler_role_distribution", "filler_impact_summary"):
        if key not in summary:
            raise AssertionError(summary)
    json_path, markdown_path = save_reports(report)
    markdown = markdown_path.read_text(encoding="utf-8")
    if "## Contextual Filler Selection" not in markdown:
        raise AssertionError(markdown[-2000:])
    if not json_path.exists():
        raise AssertionError(json_path)


def validate_phase6n_still_passes() -> None:
    import validate_phase6n as phase6n

    phase6n.validate_35_card_repair()
    phase6n.validate_blocked_cards_removed()
    phase6n.validate_copy_limits()
    phase6n.validate_runick_completion()
    phase6n.validate_no_overfill()
    phase6n.validate_diagnostics_missing_count()
    phase6n.validate_advisory_cap()
    phase6n.validate_kill_switch()
    phase6n.validate_benchmark_reporting()


def validate_stabilization_g_still_passes() -> None:
    import validate_stabilization_g as stab_g

    stab_g.validate_isolated_memory_writes()
    stab_g.validate_provenance_metadata()
    stab_g.validate_validator_records_ignored_in_production()
    stab_g.validate_rejection_cause_classification()
    stab_g.validate_legality_rejection_not_harmful()
    stab_g.validate_repair_idempotence()
    stab_g.validate_advisory_budget()


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def synthetic_pool() -> list[dict[str, Any]]:
    pool = [card(f"Probe Core {idx}", "Spell Card", 'Add 1 "Probe" card from your Deck to your hand.') for idx in range(1, 16)]
    pool.extend(safe_filler_pool())
    return pool


def safe_filler_pool() -> list[dict[str, Any]]:
    data = [
        ("Ash Blossom & Joyous Spring", "Effect Monster", "Discard this card; negate a Deck search."),
        ("Infinite Impermanence", "Trap Card", "Target 1 face-up monster; negate its effects."),
        ("Effect Veiler", "Tuner Effect Monster", "Send this card from your hand to the GY; negate a monster effect."),
        ("Droll & Lock Bird", "Effect Monster", "If a card is added from the Deck to the hand, stop further adds."),
        ("D.D. Crow", "Effect Monster", "Discard this card; banish 1 card from your opponent's GY."),
        ("Nibiru, the Primal Being", "Effect Monster", "Tribute monsters after many summons."),
        ("Ghost Belle & Haunted Mansion", "Effect Monster", "Negate an effect that moves a card from the GY."),
        ("Ghost Ogre & Snow Rabbit", "Effect Monster", "Destroy a card that activated its effect."),
        ("Called by the Grave", "Quick-Play Spell Card", "Banish a monster from the GY and negate it."),
        ("Crossout Designator", "Quick-Play Spell Card", "Declare 1 card name; banish it from your Deck."),
        ("Triple Tactics Talent", "Normal Spell Card", "Draw cards or take control after opponent monster effect."),
        ("Triple Tactics Thrust", "Normal Spell Card", "Add 1 Normal Spell/Trap from your Deck."),
        ("Upstart Goblin", "Normal Spell Card", "Draw 1 card."),
        ("Pot of Prosperity", "Normal Spell Card", "Banish Extra Deck cards; excavate and add 1 card."),
        ("Pot of Extravagance", "Normal Spell Card", "Banish Extra Deck cards; draw cards."),
        ("Pot of Desires", "Normal Spell Card", "Banish 10 cards from your Deck; draw 2 cards."),
        ("Pot of Duality", "Normal Spell Card", "Excavate cards and add 1 to your hand."),
        ("Small World", "Normal Spell Card", "Reveal monsters to add 1 monster from your Deck."),
        ("Terraforming", "Normal Spell Card", "Add 1 Field Spell from your Deck."),
        ("Book of Moon", "Quick-Play Spell Card", "Target 1 face-up monster; change it to face-down Defense Position."),
        ("Book of Eclipse", "Quick-Play Spell Card", "Change all face-up monsters to face-down Defense Position."),
        ("Cosmic Cyclone", "Quick-Play Spell Card", "Banish 1 Spell/Trap on the field."),
        ("Dark Ruler No More", "Normal Spell Card", "Negate all face-up monsters your opponent controls."),
        ("Evenly Matched", "Trap Card", "Make your opponent banish cards from their field."),
        ("Lightning Storm", "Normal Spell Card", "Destroy Attack Position monsters or Spell/Trap cards."),
        ("Raigeki", "Normal Spell Card", "Destroy all monsters your opponent controls."),
        ("Harpie's Feather Duster", "Normal Spell Card", "Destroy all Spells and Traps your opponent controls."),
        ("Forbidden Droplet", "Quick-Play Spell Card", "Send cards to the GY; negate opponent monsters."),
        ("Solemn Judgment", "Counter Trap Card", "Negate a Summon or Spell/Trap activation."),
        ("Solemn Strike", "Counter Trap Card", "Negate a monster effect or Special Summon."),
        ("Solemn Warning", "Counter Trap Card", "Negate a Summon or summon effect."),
        ("Dimensional Barrier", "Normal Trap Card", "Declare a monster card type; stop that type."),
        ("Anti-Spell Fragrance", "Continuous Trap Card", "Both players must Set Spells before activating them."),
    ]
    return [card(name, card_type, desc, archetype="Generic") for name, card_type, desc in data]


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
    print("SAMPLE: Contextual filler used:", report.get("contextual_filler_used"))
    print("SAMPLE: Selected fillers:", report.get("selected_fillers", [])[:8])
    print("SAMPLE: Filler reasons:", report.get("filler_reasons", [])[:2])


def run_command(*args: str, timeout: int = 180, retries: int = 1) -> str:
    env = os.environ.copy()
    env.pop("YUGIOH_AI_MEMORY_ROOT", None)
    env.pop("YUGIOH_AI_TEST_MODE", None)
    last_output = ""
    for _attempt in range(max(1, retries + 1)):
        result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        last_output = result.stdout
        if not result.returncode:
            return result.stdout
    raise AssertionError(last_output[-3000:])


if __name__ == "__main__":
    main()
