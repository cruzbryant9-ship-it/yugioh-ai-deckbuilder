from __future__ import annotations

from collections import Counter
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from deck.matchup_profiles import MatchupProfile


def score_side_deck(
    side_deck: list[dict[str, Any]],
    main_deck: list[dict[str, Any]],
    matchup_profile: MatchupProfile,
    going: str = "both",
) -> dict[str, float]:
    names = [str(card.get("name", "")) for card in side_deck]
    text = " ".join(card_text(card) for card in side_deck)
    high_value_hits = sum(1 for name in names if any(term.casefold() in name.casefold() for term in matchup_profile.high_value_side_cards))
    matchup_coverage = min(35.0, high_value_hits * 5.0 + keyword_coverage(text, matchup_profile) * 2.0)
    going_first = min(20.0, priority_hits(text, names, matchup_profile.going_first_priorities) * 4.0)
    going_second = min(20.0, priority_hits(text, names, matchup_profile.going_second_priorities) * 4.0)
    anti_graveyard = min(15.0, sum(term in text for term in ("graveyard", "gy", "banish")) * 5.0 + name_hits(names, ("D.D. Crow", "Ghost Belle", "Bystial", "Called by")) * 3.0)
    anti_backrow = min(15.0, sum(term in text for term in ("spell/trap", "spell or trap", "destroy all spells")) * 5.0 + name_hits(names, ("Harpie's Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched")) * 3.0)
    anti_combo = min(15.0, name_hits(names, ("Ash Blossom", "Droll", "Nibiru", "Infinite Impermanence", "Effect Veiler")) * 3.0)
    anti_control = min(15.0, name_hits(names, ("Harpie's Feather Duster", "Lightning Storm", "Evenly Matched", "Cosmic Cyclone")) * 3.0)
    overlap_penalty = overlap_with_main(side_deck, main_deck) * 1.5
    legality = 10.0 if legal_side(side_deck, main_deck) else 0.0
    if going == "first":
        going_second *= 0.4
    elif going == "second":
        going_first *= 0.4
    final = matchup_coverage + going_first + going_second + anti_graveyard + anti_backrow + anti_combo + anti_control + legality - overlap_penalty
    return {
        "side_deck_score": round(max(0.0, final), 2),
        "matchup_coverage_score": round(matchup_coverage, 2),
        "going_first_side_score": round(going_first, 2),
        "going_second_side_score": round(going_second, 2),
        "anti_graveyard_coverage": round(anti_graveyard, 2),
        "anti_backrow_coverage": round(anti_backrow, 2),
        "anti_combo_coverage": round(anti_combo, 2),
        "anti_control_coverage": round(anti_control, 2),
        "overlap_penalty": round(overlap_penalty, 2),
        "legality_score": round(legality, 2),
    }


def card_text(card: dict[str, Any]) -> str:
    return f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()


def name_hits(names: list[str], terms: tuple[str, ...]) -> int:
    return sum(1 for name in names if any(term.casefold() in name.casefold() for term in terms))


def priority_hits(text: str, names: list[str], priorities: tuple[str, ...]) -> int:
    hits = 0
    for priority in priorities:
        key = priority.casefold()
        if "hand trap" in key:
            hits += name_hits(names, ("Ash Blossom", "Droll", "Nibiru", "Effect Veiler", "Infinite Impermanence"))
        elif "backrow" in key or "spell/trap" in key:
            hits += name_hits(names, ("Harpie's Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched"))
        elif "graveyard" in key or "banish" in key:
            hits += name_hits(names, ("D.D. Crow", "Ghost Belle", "Bystial", "Called by"))
        elif "board breaker" in key:
            hits += name_hits(names, ("Dark Ruler", "Evenly Matched", "Book of Eclipse", "Raigeki"))
        elif "trap" in key:
            hits += name_hits(names, ("Solemn", "Skill Drain", "The Ultimate Creature"))
        elif key in text:
            hits += 1
    return hits


def keyword_coverage(text: str, matchup_profile: MatchupProfile) -> int:
    score = 0
    if matchup_profile.graveyard_dependency >= 0.6 and any(term in text for term in ("graveyard", "gy", "banish")):
        score += 1
    if matchup_profile.backrow_density >= 0.6 and any(term in text for term in ("spell/trap", "spell or trap", "destroy all spells")):
        score += 1
    if matchup_profile.monster_effect_density >= 0.6 and any(term in text for term in ("negate", "cannot activate", "effect")):
        score += 1
    return score


def overlap_with_main(side_deck: list[dict[str, Any]], main_deck: list[dict[str, Any]]) -> int:
    main_counts = Counter(str(card.get("name", "")) for card in main_deck)
    return sum(1 for card in side_deck if main_counts[str(card.get("name", ""))] > 0)


def legal_side(side_deck: list[dict[str, Any]], main_deck: list[dict[str, Any]]) -> bool:
    counts = Counter(str(card.get("name", "")) for card in [*main_deck, *side_deck])
    for card in [*main_deck, *side_deck]:
        if counts[str(card.get("name", ""))] > get_card_limit(card):
            return False
    return all(get_card_limit(card) > 0 for card in side_deck)
