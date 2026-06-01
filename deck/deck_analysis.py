from __future__ import annotations

from collections import Counter
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from deck.deck_utils import split_deck


def critique_deck(deck: list[dict[str, Any]], archetype: str) -> list[str]:
    issues = []
    main_deck, extra_deck = split_deck(deck)
    counts = Counter(card["name"] for card in deck)
    if len(deck) < 40:
        issues.append("deck below 40 cards")
    if len(main_deck) < 30:
        issues.append("main deck has too few non-extra-deck cards")
    if len(extra_deck) > 15:
        issues.append("extra deck exceeds 15 cards")
    for card in deck:
        if counts[card["name"]] > get_card_limit(card):
            issues.append(f"copy limit exceeded: {card['name']}")
    archetype_hits = sum(1 for card in deck if card.get("archetype") and archetype.lower() in card.get("archetype", "").lower())
    if archetype_hits < max(1, len(deck) // 2):
        issues.append("low archetype density")
    texts = " ".join(str(card.get("desc", "")).lower() for card in deck)
    if "draw" not in texts and "add" not in texts:
        issues.append("low search or draw access")
    if "special summon" not in texts:
        issues.append("low special summon access")
    if "negate" not in texts:
        issues.append("limited disruption")
    return sorted(set(issues))


def combo_report(deck: list[dict[str, Any]]) -> dict[str, int]:
    texts = [str(card.get("desc", "")).lower() for card in deck]
    return {
        "search_cards": sum(1 for text in texts if "add" in text or "search" in text),
        "draw_cards": sum(1 for text in texts if "draw" in text),
        "special_summon_cards": sum(1 for text in texts if "special summon" in text),
        "disruption_cards": sum(1 for text in texts if "negate" in text or "destroy" in text or "banish" in text),
        "graveyard_cards": sum(1 for text in texts if "graveyard" in text or "gy" in text),
    }
