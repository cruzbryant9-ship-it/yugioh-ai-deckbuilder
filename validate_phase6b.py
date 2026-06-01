from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from deck.builder import build_deck, get_last_build_report
from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("generic builder creates legal non-Blue-Eyes deck", lambda: validate_generic_non_blue_eyes(cards)),
        ("authored Blue-Eyes path still works", lambda: validate_authored_blue_eyes(cards)),
        ("fallback path uses generic builder for unsupported authored archetype", lambda: validate_fallback_path(cards)),
        ("blocked cards do not appear", lambda: validate_blocked_cards(cards)),
        ("copy limits are respected", lambda: validate_copy_limits(cards)),
        ("package counts and confidence are reported", lambda: validate_report_fields(cards)),
        ("Phase 6A validator still passes", validate_phase6a_still_passes),
        ("matchup matrix smoke still works", validate_matrix_smoke),
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
    print("Phase 6B validation complete.")


def validate_generic_non_blue_eyes(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta")
    main, extra = split_deck(deck)
    if len(main) != 40:
        raise AssertionError((len(main), report))
    if len(extra) > 15:
        raise AssertionError(len(extra))
    if report.get("builder_used") != "generic":
        raise AssertionError(report)


def validate_authored_blue_eyes(cards: list[dict[str, Any]]) -> None:
    deck, pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if not deck or not pool:
        raise AssertionError((len(deck), len(pool)))
    if report.get("builder_used") != "authored":
        raise AssertionError(report)


def validate_fallback_path(cards: list[dict[str, Any]]) -> None:
    deck, pool = build_deck(cards, "Branded", mode="meta")
    main, extra = split_deck(deck)
    report = get_last_build_report()
    if report.get("builder_used") != "generic":
        raise AssertionError(report)
    if len(main) != 40 or len(extra) > 15 or not pool:
        raise AssertionError((len(main), len(extra), len(pool), report))


def validate_blocked_cards(cards: list[dict[str, Any]]) -> None:
    deck, _report = build_generic_deck("Branded", cards, mode="meta")
    blocked = [card.get("name", "") for card in deck if get_card_limit(card) <= 0]
    if blocked:
        raise AssertionError(blocked)


def validate_copy_limits(cards: list[dict[str, Any]]) -> None:
    deck, _report = build_generic_deck("Branded", cards, mode="meta")
    counts = Counter(str(card.get("name", "")) for card in deck)
    by_name = {str(card.get("name", "")): card for card in deck}
    illegal = [f"{name} {count}>{get_card_limit(by_name[name])}" for name, count in counts.items() if count > get_card_limit(by_name[name])]
    if illegal:
        raise AssertionError(illegal)


def validate_report_fields(cards: list[dict[str, Any]]) -> None:
    _deck, report = build_generic_deck("Branded", cards, mode="innovation")
    for key in ("generic_confidence_score", "package_counts", "quota_warnings", "side_candidates", "combo_skeleton_count"):
        if key not in report:
            raise AssertionError(report)
    confidence = float(report["generic_confidence_score"])
    if not 0 <= confidence <= 1:
        raise AssertionError(confidence)


def validate_phase6a_still_passes() -> None:
    run_command("validate_phase6a.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample(cards: list[dict[str, Any]]) -> None:
    deck, report = build_generic_deck("Branded", cards, mode="meta")
    main, extra = split_deck(deck)
    print("SAMPLE: Generic Branded main count:", len(main))
    print("SAMPLE: Generic Branded extra count:", len(extra))
    print("SAMPLE: Generic confidence:", report["generic_confidence_score"])
    print("SAMPLE: Package counts:", report["package_counts"])
    print("SAMPLE: First 10 main cards:", [card["name"] for card in main[:10]])


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
