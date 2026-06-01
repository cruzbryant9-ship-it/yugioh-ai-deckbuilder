from __future__ import annotations

from typing import Any


def get_card_name(card: Any) -> str:
    if isinstance(card, dict):
        return str(card.get("name", ""))
    return str(card)


def get_card_level(card: Any) -> int:
    if not isinstance(card, dict):
        return 0
    try:
        return int(card.get("level") or 0)
    except (TypeError, ValueError):
        return 0


def get_card_rank(card: Any) -> int:
    return get_card_level(card)


def get_link_rating(card: Any) -> int:
    if not isinstance(card, dict):
        return 0
    for key in ("linkval", "link_rating", "link"):
        try:
            value = int(card.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return 0


def get_card_type(card: Any) -> str:
    if not isinstance(card, dict):
        return ""
    return str(card.get("type", ""))


def is_monster(card: Any) -> bool:
    return "monster" in get_card_type(card).lower()


def is_spell(card: Any) -> bool:
    return "spell" in get_card_type(card).lower()


def is_trap(card: Any) -> bool:
    return "trap" in get_card_type(card).lower()


def is_tuner(card: Any) -> bool:
    return "tuner" in get_card_type(card).lower()


def is_dragon(card: Any) -> bool:
    if not isinstance(card, dict):
        return False
    return "dragon" in str(card.get("race", "")).lower() or "dragon" in get_card_type(card).lower()


def is_light(card: Any) -> bool:
    return isinstance(card, dict) and str(card.get("attribute", "")).casefold() == "light"


def is_dark(card: Any) -> bool:
    return isinstance(card, dict) and str(card.get("attribute", "")).casefold() == "dark"


def is_blue_eyes(card: Any) -> bool:
    name = get_card_name(card).casefold()
    archetype = str(card.get("archetype", "")).casefold() if isinstance(card, dict) else ""
    return "blue-eyes" in name or "blue-eyes" in archetype


def is_extra_deck_monster(card: Any) -> bool:
    card_type = get_card_type(card).lower()
    return any(kind in card_type for kind in ("fusion", "synchro", "xyz", "link"))


def is_fusion(card: Any) -> bool:
    return "fusion" in get_card_type(card).lower()


def is_synchro(card: Any) -> bool:
    return "synchro" in get_card_type(card).lower()


def is_xyz(card: Any) -> bool:
    return "xyz" in get_card_type(card).lower()


def is_link(card: Any) -> bool:
    return "link" in get_card_type(card).lower()


def card_matches_requirement(card: Any, requirement: dict[str, Any] | str) -> bool:
    if isinstance(requirement, str):
        return get_card_name(card) == requirement
    if not isinstance(requirement, dict):
        return False
    if requirement.get("any") is True:
        return True

    if "name" in requirement and get_card_name(card) != str(requirement["name"]):
        return False
    if "archetype" in requirement:
        archetype = str(card.get("archetype", "") if isinstance(card, dict) else "")
        if str(requirement["archetype"]).casefold() not in archetype.casefold():
            return False
    if "type_contains" in requirement:
        haystack = f"{get_card_type(card)} {card.get('race', '') if isinstance(card, dict) else ''}"
        if str(requirement["type_contains"]).casefold() not in haystack.casefold():
            return False
    if "attribute" in requirement:
        attribute = str(card.get("attribute", "") if isinstance(card, dict) else "")
        if attribute.casefold() != str(requirement["attribute"]).casefold():
            return False
    if "level" in requirement and get_card_level(card) != int(requirement["level"]):
        return False
    if requirement.get("tuner") is True and not is_tuner(card):
        return False
    if requirement.get("non_tuner") is True and is_tuner(card):
        return False
    if requirement.get("monster") is True and not is_monster(card):
        return False
    if requirement.get("dragon") is True and not is_dragon(card):
        return False
    if requirement.get("blue_eyes") is True and not is_blue_eyes(card):
        return False
    return True
