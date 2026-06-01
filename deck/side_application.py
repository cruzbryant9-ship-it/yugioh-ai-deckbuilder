from __future__ import annotations

from collections import Counter
from typing import Any

from SystemAIYugioh.banlist import get_card_limit


def apply_side_plan(
    main_deck: list[dict[str, Any]],
    side_deck: list[dict[str, Any]],
    side_in: list[dict[str, Any] | str],
    side_out: list[dict[str, Any] | str],
) -> dict[str, Any]:
    warnings: list[str] = []
    side_lookup = _cards_by_name(side_deck)
    main_counts = Counter(_card_name(card) for card in main_deck)
    side_available = Counter(_card_name(card) for card in side_deck)
    side_in_names = [_card_name(card) for card in side_in]
    side_out_names = [_card_name(card) for card in side_out]
    requested_out = Counter(side_out_names)
    for name, count in requested_out.items():
        if count > main_counts[name]:
            warnings.append(f"side-out requested more copies than main deck contains: {name}")
    requested_in = Counter(side_in_names)
    for name, count in requested_in.items():
        if count > side_available[name]:
            warnings.append(f"side-in requested more copies than side deck contains: {name}")

    post_side_main = list(main_deck)
    applied_out: list[str] = []
    for name in side_out_names:
        index = _find_card_index(post_side_main, name)
        if index is None:
            warnings.append(f"side-out card not found in main deck: {name}")
            continue
        removed = post_side_main.pop(index)
        applied_out.append(_card_name(removed))
        main_counts[_card_name(removed)] -= 1

    applied_in: list[str] = []
    for name in side_in_names:
        if len(applied_in) >= len(applied_out):
            warnings.append(f"side-in skipped because no matching side-out slot remains: {name}")
            continue
        card = side_lookup.get(name)
        if not card:
            warnings.append(f"side-in card not found in side deck: {name}")
            continue
        if side_available[name] <= 0:
            warnings.append(f"side-in card copy unavailable in side deck: {name}")
            continue
        limit = get_card_limit(card)
        if limit <= 0:
            warnings.append(f"blocked side-in card rejected: {name}")
            continue
        if main_counts[name] >= limit:
            warnings.append(f"copy limit would be exceeded by side-in card: {name}")
            continue
        post_side_main.append(card)
        main_counts[name] += 1
        side_available[name] -= 1
        applied_in.append(name)

    while len(post_side_main) < len(main_deck) and applied_out:
        name = applied_out.pop()
        replacement = _first_card_by_name(main_deck, name)
        if replacement:
            post_side_main.append(replacement)
            warnings.append(f"restored side-out card to preserve deck size: {name}")

    if len(post_side_main) != len(main_deck):
        warnings.append(f"post-side deck size changed: {len(post_side_main)} != {len(main_deck)}")
    if len(applied_in) != len(applied_out):
        warnings.append(f"side-in and side-out counts differ: {len(applied_in)} != {len(applied_out)}")

    counts = Counter(_card_name(card) for card in post_side_main)
    for card in post_side_main:
        name = _card_name(card)
        limit = get_card_limit(card)
        if limit <= 0:
            warnings.append(f"blocked card in post-side deck: {name}")
        if counts[name] > limit:
            warnings.append(f"copy limit exceeded after siding: {name}")

    return {
        "post_side_main": post_side_main,
        "applied_side_in": applied_in,
        "applied_side_out": applied_out,
        "warnings": sorted(set(warnings)),
        "valid": not warnings and len(post_side_main) == len(main_deck),
    }


def _card_name(card: dict[str, Any] | str) -> str:
    if isinstance(card, dict):
        return str(card.get("name", ""))
    return str(card)


def _cards_by_name(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_card_name(card): card for card in cards}


def _first_card_by_name(cards: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for card in cards:
        if _card_name(card) == name:
            return card
    return None


def _find_card_index(cards: list[dict[str, Any]], name: str) -> int | None:
    for index, card in enumerate(cards):
        if _card_name(card) == name:
            return index
    return None
