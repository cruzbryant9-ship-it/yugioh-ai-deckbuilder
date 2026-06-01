from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from deck.archetype_role_inference import infer_archetype_roles
from deck.builder import build_deck, get_last_build_report
from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.generic_deck_repair import classify_repair_role, repair_generic_deck
from deck.generic_tuner import tune_generic_deck
from generic_archetype_benchmark import run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("repair fixes a 39-card generic deck to 40", lambda: validate_repair_fills_to_40(cards)),
        ("blocked cards are not used for repair", lambda: validate_no_blocked_repair(cards)),
        ("copy limits are respected after repair", lambda: validate_copy_limits(cards)),
        ("brick overfill is not worsened", lambda: validate_brick_not_worsened(cards)),
        ("generic tuner uses repair before rejecting", lambda: validate_tuner_repair(cards)),
        ("benchmark records repair metrics", validate_benchmark_repair_metrics),
        ("Kashtira-like incomplete tuned deck is repaired or safely rejected", validate_kashtira_repair_or_reject),
        ("Blue-Eyes authored path still works", lambda: validate_blue_eyes_authored(cards)),
        ("Phase 6D validator still passes", validate_phase6d_still_passes),
        ("stabilization validator still passes", validate_stabilization_still_passes),
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
    print_sample(cards)
    print("Phase 6E validation complete.")


def validate_repair_fills_to_40(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    repair = repair_generic_deck(main[:-1], extra, "Branded", cards, {"analysis": infer_archetype_roles(cards, "Branded")}, report["ratio_profile"], mode="meta")
    if len(repair["main"]) != 40 or not repair["legal"]:
        raise AssertionError(repair)


def validate_no_blocked_repair(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    repair = repair_generic_deck(main[:-1], extra, "Branded", cards, {"analysis": infer_archetype_roles(cards, "Branded")}, report["ratio_profile"], mode="meta")
    blocked = [card.get("name", "") for card in repair["main"] + repair["extra"] if get_card_limit(card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_copy_limits(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    repair = repair_generic_deck(main[:-1], extra, "Branded", cards, {"analysis": infer_archetype_roles(cards, "Branded")}, report["ratio_profile"], mode="meta")
    counts = Counter(str(card.get("name", "")) for card in repair["main"] + repair["extra"])
    by_name = {str(card.get("name", "")): card for card in repair["main"] + repair["extra"]}
    illegal = [name for name, count in counts.items() if count > get_card_limit(by_name[name])]
    if illegal:
        raise AssertionError(illegal)


def validate_brick_not_worsened(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    before = sum(1 for card in main[:-1] if classify_repair_role(card) == "garnet_brick")
    repair = repair_generic_deck(main[:-1], extra, "Branded", cards, {"analysis": infer_archetype_roles(cards, "Branded")}, report["ratio_profile"], mode="meta")
    after = sum(1 for card in repair["main"] if classify_repair_role(card) == "garnet_brick")
    if after > max(before, int(report["ratio_profile"].get("max_bricks", 4))):
        raise AssertionError((before, after, repair))


def validate_tuner_repair(cards: list[dict[str, Any]]) -> None:
    report = tune_generic_deck("Kashtira", cards, mode="meta", runs=3, update_memory=False)
    if "repair_success_rate" not in report or "common_repair_warnings" not in report:
        raise AssertionError(report)
    if not all("repair_success" in result for result in report["results"]):
        raise AssertionError(report["results"])


def validate_benchmark_repair_metrics() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    summary = report["summary"]
    for key in ("repair_success_rate", "average_repair_actions", "decks_saved_by_repair", "decks_still_rejected", "common_repair_warnings"):
        if key not in summary:
            raise AssertionError(summary)


def validate_kashtira_repair_or_reject() -> None:
    report = run_benchmark(["Kashtira"], mode="meta", runs=3)
    result = report["results"][0]
    if result["tuned_legal"] and result["memory_action"] not in {"updated", "unchanged"}:
        raise AssertionError(result)
    if not result["tuned_legal"] and result["memory_action"] != "recorded_bad_pattern":
        raise AssertionError(result)


def validate_blue_eyes_authored(cards: list[dict[str, Any]]) -> None:
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if not deck or report.get("builder_used") != "authored":
        raise AssertionError(report)


def validate_phase6d_still_passes() -> None:
    run_command("validate_phase6d.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta", use_ratio_memory=False)
    main, extra = split_deck(deck)
    repair = repair_generic_deck(main[:-1], extra, "Branded", cards, {"analysis": infer_archetype_roles(cards, "Branded")}, report["ratio_profile"], mode="meta")
    benchmark = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    print("SAMPLE: Repaired Branded main count:", len(repair["main"]))
    print("SAMPLE: Repaired Branded legal:", repair["legal"])
    print("SAMPLE: Repair actions:", repair["repair_actions"][:5])
    print("SAMPLE: Benchmark repair metrics:", {key: benchmark["summary"][key] for key in ("repair_success_rate", "decks_saved_by_repair", "decks_still_rejected")})


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
