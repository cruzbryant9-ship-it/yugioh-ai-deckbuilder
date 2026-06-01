from __future__ import annotations

from collections import Counter
from typing import Any

from deck.archetype_role_inference import archetype_pool
from deck.card_metadata import is_extra_deck_monster, is_spell, is_trap
from SystemAIYugioh.banlist import get_card_limit

MAIN_DECK_TARGET = 40


SAFE_GENERIC_FILLER_NAMES = {
    "Ash Blossom & Joyous Spring",
    "Effect Veiler",
    "Droll & Lock Bird",
    "D.D. Crow",
    "Nibiru, the Primal Being",
    "Infinite Impermanence",
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
    "Terraforming",
    "Book of Moon",
    "Book of Eclipse",
    "Book of Lunar Eclipse",
    "Cosmic Cyclone",
    "Dark Ruler No More",
    "Evenly Matched",
    "Lightning Storm",
    "Raigeki",
    "Harpie's Feather Duster",
    "Forbidden Droplet",
    "Solemn Judgment",
    "Solemn Strike",
    "Solemn Warning",
    "Dimensional Barrier",
    "Anti-Spell Fragrance",
}


def diagnose_under_40_repair(
    main_deck: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None = None,
    quota_profile: dict[str, int] | None = None,
    mode: str = "meta",
) -> dict[str, Any]:
    main = [card for card in main_deck if not is_extra_deck_monster(card)]
    missing_count = max(0, MAIN_DECK_TARGET - len(main))
    counts = Counter(card_name(card) for card in main)
    archetype_cards = archetype_pool(card_pool, archetype)
    archetype_main = [card for card in archetype_cards if not is_extra_deck_monster(card)]
    archetype_extra = [card for card in archetype_cards if is_extra_deck_monster(card)]
    blocked_candidates = []
    copy_limit_blocked = []
    legal_archetype_fillers = []
    for card in archetype_main:
        name = card_name(card)
        limit = get_card_limit(card)
        if limit <= 0:
            blocked_candidates.append(name)
        elif counts[name] >= limit:
            copy_limit_blocked.append(name)
        else:
            legal_archetype_fillers.append(name)
    safe_fillers = safe_generic_filler_candidates(card_pool, main, mode)
    available = {
        "archetype_core": len(set(legal_archetype_fillers)),
        "safe_generic_fillers": len(safe_fillers),
        "extra_deck_only_archetype_cards": len(archetype_extra),
        "spell_trap_archetype_cards": sum(1 for card in archetype_main if is_spell(card) or is_trap(card)),
    }
    spell_trap_heavy = is_spell_trap_heavy(archetype_main)
    reason = classify_under_40_reason(
        missing_count,
        legal_archetype_fillers,
        safe_fillers,
        blocked_candidates,
        copy_limit_blocked,
        archetype_main,
        archetype_extra,
        spell_trap_heavy,
    )
    return {
        "under_40_reason": reason,
        "missing_count": missing_count,
        "available_fillers": available,
        "blocked_candidates": sorted(set(blocked_candidates))[:25],
        "copy_limit_blocked": sorted(set(copy_limit_blocked))[:25],
        "spell_trap_heavy": spell_trap_heavy,
        "recommended_repair_strategy": recommended_strategy(reason, missing_count, available),
    }


def safe_generic_filler_candidates(card_pool: list[dict[str, Any]], current_deck: list[dict[str, Any]], mode: str = "meta") -> list[dict[str, Any]]:
    counts = Counter(card_name(card) for card in current_deck)
    candidates = []
    for card in card_pool:
        name = card_name(card)
        if name not in SAFE_GENERIC_FILLER_NAMES:
            continue
        if is_extra_deck_monster(card) or get_card_limit(card) <= 0:
            continue
        if counts[name] >= get_card_limit(card):
            continue
        candidates.append(card)
    return sorted(dedup_cards(candidates), key=lambda card: safe_filler_weight(card, mode), reverse=True)


def classify_under_40_reason(
    missing_count: int,
    legal_archetype_fillers: list[str],
    safe_fillers: list[dict[str, Any]],
    blocked_candidates: list[str],
    copy_limit_blocked: list[str],
    archetype_main: list[dict[str, Any]],
    archetype_extra: list[dict[str, Any]],
    spell_trap_heavy: bool,
) -> str:
    if missing_count <= 0:
        return "complete"
    if safe_fillers:
        return "missing_safe_filler_not_used"
    if not archetype_main and archetype_extra:
        return "extra_deck_only_archetype_pool"
    if spell_trap_heavy and not legal_archetype_fillers:
        return "spell_trap_heavy_core_exhausted"
    if not legal_archetype_fillers and copy_limit_blocked:
        return "exhausted_legal_copy_counts"
    if not legal_archetype_fillers and blocked_candidates:
        return "too_many_blocked_cards"
    if not safe_fillers:
        return "insufficient_generic_staple_pool"
    return "package_quota_conflict"


def recommended_strategy(reason: str, missing_count: int, available: dict[str, int]) -> str:
    if reason == "complete":
        return "no repair needed"
    if reason == "missing_safe_filler_not_used":
        return f"fill {missing_count} slots from safe generic non-engine filler pool"
    if reason == "spell_trap_heavy_core_exhausted":
        return "treat spell/trap core density as valid, then fill remaining slots with safe non-engine"
    if reason == "extra_deck_only_archetype_pool":
        return "ignore Extra Deck-only archetype cards for main count and use safe non-engine fillers"
    if reason == "exhausted_legal_copy_counts":
        return "stop archetype filling and use generic safe filler while respecting copy limits"
    if reason == "too_many_blocked_cards":
        return "avoid blocked cards and fill from legal generic staples"
    if reason == "insufficient_generic_staple_pool":
        return "reject with precise under-40 reason; safe filler pool is exhausted"
    return "relax package preference order and use safe filler ladder"


def is_spell_trap_heavy(cards: list[dict[str, Any]]) -> bool:
    if not cards:
        return False
    spell_trap_count = sum(1 for card in cards if is_spell(card) or is_trap(card))
    return spell_trap_count / max(1, len(cards)) >= 0.55


def safe_filler_weight(card: dict[str, Any], mode: str = "meta") -> float:
    name = card_name(card)
    meta_bonus = 0.2 if mode == "meta" else 0.0
    weights = {
        "Ash Blossom & Joyous Spring": 1.0 + meta_bonus,
        "Infinite Impermanence": 0.98 + meta_bonus,
        "Effect Veiler": 0.94 + meta_bonus,
        "Droll & Lock Bird": 0.92 + meta_bonus,
        "D.D. Crow": 0.88 + meta_bonus,
        "Nibiru, the Primal Being": 0.86 + meta_bonus,
        "Ghost Belle & Haunted Mansion": 0.84 + meta_bonus,
        "Ghost Ogre & Snow Rabbit": 0.82 + meta_bonus,
        "Called by the Grave": 0.8,
        "Crossout Designator": 0.78,
        "Triple Tactics Talent": 0.76,
        "Triple Tactics Thrust": 0.75,
        "Upstart Goblin": 0.72,
        "Pot of Prosperity": 0.7,
        "Pot of Extravagance": 0.68,
        "Pot of Desires": 0.66,
        "Pot of Duality": 0.64,
        "Small World": 0.62,
        "Terraforming": 0.6,
        "Book of Moon": 0.56,
        "Book of Eclipse": 0.54,
        "Book of Lunar Eclipse": 0.52,
        "Cosmic Cyclone": 0.5,
        "Dark Ruler No More": 0.48,
        "Evenly Matched": 0.46,
        "Lightning Storm": 0.44,
        "Raigeki": 0.42,
        "Harpie's Feather Duster": 0.4,
        "Forbidden Droplet": 0.38,
        "Solemn Judgment": 0.36,
        "Solemn Strike": 0.34,
        "Solemn Warning": 0.32,
        "Dimensional Barrier": 0.3,
        "Anti-Spell Fragrance": 0.28,
    }
    return weights.get(name, 0.1)


def dedup_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for card in cards:
        name = card_name(card)
        if name and name not in seen:
            seen.add(name)
            unique.append(card)
    return unique


def card_name(card: Any) -> str:
    return str(card.get("name", card)) if isinstance(card, dict) else str(card)
