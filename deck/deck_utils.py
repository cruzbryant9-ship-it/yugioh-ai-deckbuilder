from __future__ import annotations

from typing import Any

from deck.builder import is_extra_deck_card


def split_deck(deck: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return [card for card in deck if not is_extra_deck_card(card)], [card for card in deck if is_extra_deck_card(card)]


def blocked_card_violations(deck: list[dict[str, Any]]) -> list[str]:
    from SystemAIYugioh.banlist import get_card_limit

    return [str(card.get("name", "")) for card in deck if get_card_limit(card) <= 0]
