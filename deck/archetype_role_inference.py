from __future__ import annotations

from collections import Counter
from typing import Any

from deck.card_metadata import get_card_level, is_extra_deck_monster, is_monster, is_spell, is_trap
from deck.card_text_parser import parse_card_text


ROLE_NAMES = (
    "starter",
    "extender",
    "searcher",
    "payoff",
    "garnet_brick",
    "interruption",
    "board_breaker",
    "recovery",
    "engine_requirement",
)


def infer_archetype_roles(cards: list[dict[str, Any]], archetype: str) -> dict[str, Any]:
    pool = archetype_pool(cards, archetype)
    role_map = {role: [] for role in ROLE_NAMES}
    card_roles: dict[str, dict[str, Any]] = {}
    for card in pool:
        result = infer_card_roles(card, archetype, pool)
        card_roles[str(card.get("name", ""))] = result
        for role in result["roles"]:
            role_map.setdefault(role, []).append(str(card.get("name", "")))
    return {
        "archetype": archetype,
        "card_count": len(pool),
        "role_counts": {role: len(names) for role, names in role_map.items()},
        "roles": {role: sorted(set(names)) for role, names in role_map.items()},
        "cards": card_roles,
        "signals": archetype_signals(pool, archetype),
    }


def infer_card_roles(card: dict[str, Any], archetype: str, pool: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = normalized_text(card)
    parsed = parse_card_text(card)
    roles: set[str] = set()
    reasons: list[str] = []

    if has_search_effect(text, archetype):
        roles.update({"starter", "searcher"})
        reasons.append("searches or adds cards from deck")
    if has_special_summon_effect(text):
        roles.add("extender")
        reasons.append("can special summon or extend bodies/resources")
    if has_graveyard_effect(text):
        roles.add("recovery")
        reasons.append("has graveyard recursion or graveyard-triggered text")
    if is_payoff_card(card, text):
        roles.add("payoff")
        reasons.append("large monster, Extra Deck monster, ritual/fusion/synchro/xyz/link, or endboard text")
    if is_brick_like(card, text):
        roles.add("garnet_brick")
        reasons.append("high-level or ritual piece with limited self-access")
    if is_interruption_text(text):
        roles.add("interruption")
        reasons.append("negates, banishes, destroys, or uses Quick Effect timing")
    if is_board_breaker_text(card, text):
        roles.add("board_breaker")
        reasons.append("removes or suppresses opposing board")
    if parsed.get("costs") or parsed.get("conditions"):
        roles.add("engine_requirement")
        reasons.append("has explicit activation cost or condition")
    if not roles and archetype_match(card, archetype):
        roles.add("engine_requirement")
        reasons.append("belongs to archetype but has no strong generic role signal")

    score = role_confidence(card, text, parsed, roles)
    return {
        "name": str(card.get("name", "")),
        "roles": sorted(roles),
        "confidence": round(score, 3),
        "reasons": reasons,
        "parsed_text": {
            "cost_count": len(parsed.get("costs", [])),
            "condition_count": len(parsed.get("conditions", [])),
            "effect_count": len(parsed.get("effects", [])),
            "once_per_turn": bool(parsed.get("once_per_turn")),
        },
    }


def archetype_pool(cards: list[dict[str, Any]], archetype: str) -> list[dict[str, Any]]:
    needle = archetype.casefold().replace("-", " ")
    pool = []
    for card in cards:
        name = str(card.get("name", "")).casefold().replace("-", " ")
        card_archetype = str(card.get("archetype", "")).casefold().replace("-", " ")
        desc = str(card.get("desc", "")).casefold().replace("-", " ")
        if needle in name or needle in card_archetype or f'"{needle}"' in desc:
            pool.append(card)
    return pool


def archetype_signals(pool: list[dict[str, Any]], archetype: str) -> dict[str, Any]:
    attributes = Counter(str(card.get("attribute", "")) for card in pool if card.get("attribute"))
    races = Counter(str(card.get("race", "")) for card in pool if card.get("race"))
    levels = Counter(get_card_level(card) for card in pool if get_card_level(card))
    return {
        "dominant_attributes": attributes.most_common(3),
        "dominant_types": races.most_common(3),
        "dominant_levels": levels.most_common(5),
        "has_extra_deck_payoffs": any(is_extra_deck_monster(card) for card in pool),
        "archetype": archetype,
    }


def archetype_match(card: dict[str, Any], archetype: str) -> bool:
    value = archetype.casefold().replace("-", " ")
    return value in str(card.get("name", "")).casefold().replace("-", " ") or value in str(card.get("archetype", "")).casefold().replace("-", " ")


def normalized_text(card: dict[str, Any]) -> str:
    return f"{card.get('name', '')} {card.get('type', '')} {card.get('race', '')} {card.get('desc', '')}".casefold()


def has_search_effect(text: str, archetype: str) -> bool:
    return (
        "from your deck to your hand" in text
        or "add 1" in text and "from your deck" in text
        or "add 1" in text and archetype.casefold() in text
        or "search" in text
        or "excavate" in text and "add" in text
    )


def has_special_summon_effect(text: str) -> bool:
    return "special summon" in text or "summon this card" in text or "summon 1" in text


def has_graveyard_effect(text: str) -> bool:
    return "from your gy" in text or "in your gy" in text or "from your graveyard" in text or "in your graveyard" in text


def is_payoff_card(card: dict[str, Any], text: str) -> bool:
    return (
        is_extra_deck_monster(card)
        or "ritual monster" in text
        or get_card_level(card) >= 7 and is_monster(card)
        or "negate" in text
        or "cannot be destroyed" in text
        or "unaffected" in text
    )


def is_brick_like(card: dict[str, Any], text: str) -> bool:
    if not is_monster(card):
        return False
    level = get_card_level(card)
    if level >= 7 and "special summon" not in text and "normal summon" not in text:
        return True
    return "ritual monster" in text and "you can ritual summon" not in text


def is_interruption_text(text: str) -> bool:
    return any(term in text for term in ("negate", "quick effect", "banish", "destroy", "return that card", "shuffle it"))


def is_board_breaker_text(card: dict[str, Any], text: str) -> bool:
    name = str(card.get("name", "")).casefold()
    if any(term in name for term in ("dark ruler", "evenly matched", "lightning storm", "raigeki", "kaiju", "droplet")):
        return True
    return ("your opponent controls" in text or "your opponent's" in text) and any(term in text for term in ("destroy", "banish", "send", "negate", "return"))


def role_confidence(card: dict[str, Any], text: str, parsed: dict[str, Any], roles: set[str]) -> float:
    score = 0.35 + min(0.4, len(roles) * 0.08)
    if parsed.get("once_per_turn"):
        score += 0.05
    if is_spell(card) or is_trap(card):
        score += 0.04
    if "from your deck" in text:
        score += 0.08
    if parsed.get("costs") or parsed.get("conditions"):
        score -= 0.03
    return max(0.1, min(0.95, score))
