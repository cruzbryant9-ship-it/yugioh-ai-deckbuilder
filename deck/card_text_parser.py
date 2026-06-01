from __future__ import annotations

import re
from typing import Any


def parse_card_text(card_or_text: Any) -> dict[str, Any]:
    """Extract simple cost/condition/effect hints from card text.

    This is intentionally heuristic. It recognizes common phrasing well enough
    for graph validation, but it is not a full PSCT parser.
    """
    name = str(card_or_text.get("name", "")) if isinstance(card_or_text, dict) else ""
    text = str(card_or_text.get("desc", card_or_text) if isinstance(card_or_text, dict) else card_or_text)
    lowered = " ".join(text.lower().replace("\n", " ").split())

    costs: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []

    if "reveal" in lowered:
        revealed = _named_after(lowered, r"reveal (?:1|one|a|an) ([^.;,]+)")
        costs.append({"type": "reveal", "requirement": _requirement_from_phrase(revealed)})
    if "discard" in lowered:
        costs.append({"type": "discard", "requirement": {"any": True}})
    if "send" in lowered and ("to the gy" in lowered or "to the graveyard" in lowered):
        source = "deck" if "from your deck" in lowered else "field" if "from your field" in lowered else "hand"
        costs.append({"type": "send_to_gy", "from": source, "requirement": {"any": True}})
    if "banish" in lowered:
        source = "graveyard" if "from your gy" in lowered or "from your graveyard" in lowered else "hand"
        costs.append({"type": "banish", "from": source, "requirement": {"any": True}})

    control_phrase = _named_after(lowered, r"if you control ([^.;,]+)")
    if control_phrase:
        conditions.append({"type": "control", "requirement": _requirement_from_phrase(control_phrase)})
    if "if this card is in your gy" in lowered or "if this card is in your graveyard" in lowered:
        conditions.append({"type": "in_gy", "requirement": {"name": name} if name else {"any": True}})
    if "in your gy" in lowered or "in your graveyard" in lowered:
        conditions.append({"type": "has_in_gy", "requirement": {"any": True}})
    if "from your deck" in lowered and ("add" in lowered or "special summon" in lowered):
        effects.append({"type": "deck_search"})
    if "special summon" in lowered:
        effects.append({"type": "special_summon"})

    once_per_turn = "once per turn" in lowered or "you can only use" in lowered
    return {
        "costs": _dedupe_dicts(costs),
        "conditions": _dedupe_dicts(conditions),
        "effects": _dedupe_dicts(effects),
        "once_per_turn": once_per_turn,
        "once_per_turn_tag": once_per_turn_tag(name, lowered) if once_per_turn else None,
        "activation_restrictions": activation_restrictions(lowered),
    }


def once_per_turn_tag(name: str, text: str) -> str | None:
    if not name and not text:
        return None
    seed = name or text[:30]
    return re.sub(r"[^a-z0-9]+", "_", seed.lower()).strip("_") + "_opt"


def activation_restrictions(text: str) -> list[dict[str, Any]]:
    restrictions = []
    if "you cannot special summon" in text:
        restrictions.append({"type": "special_summon_lock"})
    if "for the rest of this turn" in text:
        restrictions.append({"type": "turn_lock"})
    return restrictions


def _named_after(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _requirement_from_phrase(phrase: str) -> dict[str, Any]:
    phrase = phrase.strip(" .;:,\"'")
    if not phrase or phrase in {"card", "cards"}:
        return {"any": True}
    if "blue-eyes white dragon" in phrase:
        return {"name": "Blue-Eyes White Dragon"}
    if "blue-eyes" in phrase:
        return {"blue_eyes": True}
    if "dragon" in phrase:
        return {"dragon": True}
    if "monster" in phrase:
        return {"monster": True}
    return {"name": " ".join(word.capitalize() for word in phrase.split())}


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for item in items:
        key = repr(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
