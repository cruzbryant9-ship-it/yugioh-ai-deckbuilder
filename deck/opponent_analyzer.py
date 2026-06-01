from __future__ import annotations

from collections import Counter
from typing import Any

from deck.builder import detect_card_engines
from deck.curated_opponent_library import match_profile_from_decklist, merge_curated_and_inferred_profile
from deck.opponent_profiles import OpponentProfile

HAND_TRAPS = ("ash blossom", "effect veiler", "droll", "nibiru", "infinite impermanence", "ghost belle", "d.d. crow")
BOARD_BREAKERS = ("dark ruler", "evenly matched", "raigeki", "lightning storm", "harpie", "forbidden droplet", "book of eclipse")
KNOWN_ARCHETYPES = ("Snake-Eye", "Tenpai", "Labrynth", "Branded", "Kashtira", "Runick", "Floowandereeze", "Tearlaments", "Yubel", "Purrely", "Rescue-ACE", "Blue-Eyes")


def analyze_opponent_deck(parsed: dict[str, list[str]], card_database: list[dict[str, Any]]) -> OpponentProfile:
    lookup = {str(card.get("name", "")).casefold(): card for card in card_database}
    all_names = parsed.get("all_cards", [])
    cards = [lookup.get(name.casefold(), {"name": name, "desc": "", "type": ""}) for name in all_names]
    main_cards = [lookup.get(name.casefold(), {"name": name, "desc": "", "type": ""}) for name in parsed.get("main", [])]
    archetype = infer_archetype(all_names)
    engines = sorted({engine for card in cards for engine in detect_card_engines(card)})
    texts = [card_text(card) for card in cards]
    main_texts = [card_text(card) for card in main_cards]
    hand_traps = tuple(name for name in all_names if any(term in name.casefold() for term in HAND_TRAPS))
    breakers = tuple(name for name in all_names if any(term in name.casefold() for term in BOARD_BREAKERS))
    starters = tuple(name for name, card in zip(all_names, cards) if is_starter(card))[:12]
    extenders = tuple(name for name, card in zip(all_names, cards) if "special summon" in card_text(card))[:12]
    graveyard_dependency = score_terms(texts, ("graveyard", "gy", "send", "sent to the gy", "from your gy"))
    backrow_density = min(1.0, sum(1 for card in main_cards if "trap" in str(card.get("type", "")).casefold()) / max(len(main_cards), 1) * 3)
    spell_trap_density = min(1.0, sum(1 for card in main_cards if any(term in str(card.get("type", "")).casefold() for term in ("spell", "trap"))) / max(len(main_cards), 1) * 2)
    monster_effect_density = min(1.0, sum(1 for text in main_texts if "effect" in text or "monster" in text) / max(len(main_texts), 1))
    summon_volume = score_terms(texts, ("special summon", "normal summon", "summon"))
    banish_dependency = score_terms(texts, ("banish", "banished"))
    search_dependency = score_terms(texts, ("add 1", "from your deck", "search"))
    nearest = nearest_matchup(graveyard_dependency, backrow_density, spell_trap_density, monster_effect_density, summon_volume, search_dependency, hand_traps, breakers)
    counters = recommended_counters(nearest, graveyard_dependency, backrow_density, search_dependency, hand_traps)
    choke_points = infer_choke_points(archetype, starters, graveyard_dependency, search_dependency)
    inferred = OpponentProfile(
        name=f"{archetype or nearest} profile",
        archetype=archetype or "Unknown",
        known_cards=tuple(all_names),
        likely_engines=tuple(engines),
        key_starters=starters,
        key_extenders=extenders,
        key_interruptions=hand_traps,
        key_board_breakers=breakers,
        graveyard_dependency=graveyard_dependency,
        backrow_density=backrow_density,
        spell_trap_density=spell_trap_density,
        monster_effect_density=monster_effect_density,
        summon_volume=summon_volume,
        banish_dependency=banish_dependency,
        search_dependency=search_dependency,
        going_first_plan=going_first_plan(nearest),
        going_second_plan=going_second_plan(nearest),
        expected_endboard=expected_endboard(archetype, nearest),
        choke_points=choke_points,
        recommended_counters=counters,
        nearest_matchup=nearest,
        profile_source="inferred",
    )
    curated = match_profile_from_decklist(parsed)
    return merge_curated_and_inferred_profile(curated, inferred) if curated else inferred


def infer_archetype(names: list[str]) -> str:
    joined = " ".join(names).casefold()
    hits = Counter()
    for archetype in KNOWN_ARCHETYPES:
        terms = [part for part in archetype.casefold().replace("-", " ").split() if part]
        if archetype.casefold() in joined or any(term in joined for term in terms):
            hits[archetype] += sum(joined.count(term) for term in terms)
    return hits.most_common(1)[0][0] if hits else ""


def nearest_matchup(graveyard: float, backrow: float, spell_trap: float, monster_effect: float, summons: float, search: float, hand_traps: tuple[str, ...], breakers: tuple[str, ...]) -> str:
    if backrow >= 0.65:
        return "backrow"
    if graveyard >= 0.65:
        return "graveyard"
    if len(hand_traps) >= 8:
        return "handtrap_heavy"
    if len(breakers) >= 6:
        return "board_breaker_heavy"
    if spell_trap >= 0.75 and backrow < 0.5:
        return "spell_heavy"
    if summons >= 0.65 or search >= 0.65 or monster_effect >= 0.75:
        return "combo"
    return "unknown_meta"


def recommended_counters(nearest: str, graveyard: float, backrow: float, search: float, hand_traps: tuple[str, ...]) -> tuple[str, ...]:
    counters = []
    if search >= 0.5:
        counters.extend(["Ash Blossom", "Droll & Lock Bird"])
    if graveyard >= 0.5:
        counters.extend(["D.D. Crow", "Ghost Belle & Haunted Mansion", "Called by the Grave"])
    if backrow >= 0.5:
        counters.extend(["Harpie's Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched"])
    if nearest == "combo":
        counters.extend(["Nibiru", "Infinite Impermanence", "Effect Veiler", "Dark Ruler No More"])
    if hand_traps:
        counters.extend(["Called by the Grave", "Crossout Designator", "Triple Tactics Talent"])
    return tuple(dict.fromkeys(counters))


def infer_choke_points(archetype: str, starters: tuple[str, ...], graveyard: float, search: float) -> tuple[str, ...]:
    points = list(starters[:5])
    if search >= 0.5:
        points.append("deck search effects")
    if graveyard >= 0.5:
        points.append("graveyard setup")
    if archetype:
        points.append(f"{archetype} starter resolution")
    return tuple(dict.fromkeys(points))


def going_first_plan(nearest: str) -> tuple[str, ...]:
    if nearest in {"combo", "graveyard"}:
        return ("hand traps", "graveyard interruption", "turn-ending traps")
    if nearest in {"backrow", "stun"}:
        return ("spell/trap answers", "protection")
    return ("balanced interaction",)


def going_second_plan(nearest: str) -> tuple[str, ...]:
    if nearest in {"backrow", "stun"}:
        return ("backrow removal", "mass removal")
    if nearest == "combo":
        return ("board breakers", "hand traps")
    if nearest == "graveyard":
        return ("graveyard hate", "board breakers")
    return ("flexible breakers",)


def expected_endboard(archetype: str, nearest: str) -> tuple[str, ...]:
    if archetype:
        return (f"{archetype} core board",)
    if nearest == "combo":
        return ("multiple monster effects", "negation board")
    if nearest == "backrow":
        return ("set backrow", "trap interruptions")
    return ("unknown endboard",)


def is_starter(card: dict[str, Any]) -> bool:
    text = card_text(card)
    return "add 1" in text or "from your deck" in text or "normal summon" in text or "search" in text


def score_terms(texts: list[str], terms: tuple[str, ...]) -> float:
    if not texts:
        return 0.0
    hits = sum(1 for text in texts if any(term in text for term in terms))
    return round(min(1.0, hits / max(len(texts), 1) * 2), 4)


def card_text(card: dict[str, Any]) -> str:
    return f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()
