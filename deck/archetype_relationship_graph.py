from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from deck.archetype_role_inference import archetype_pool, infer_archetype_roles
from deck.card_metadata import get_card_level, is_extra_deck_monster


def score_archetype_compatibility(cards: list[dict[str, Any]], primary: str, candidate: str) -> dict[str, Any]:
    primary_pool = archetype_pool(cards, primary)
    candidate_pool = archetype_pool(cards, candidate)
    primary_roles = infer_archetype_roles(cards, primary)
    candidate_roles = infer_archetype_roles(cards, candidate)

    attribute_overlap = overlap_score(attributes(primary_pool), attributes(candidate_pool))
    level_overlap = overlap_score(levels(primary_pool), levels(candidate_pool))
    typing_overlap = overlap_score(types(primary_pool), types(candidate_pool))
    graveyard_synergy = text_signal_overlap(primary_pool, candidate_pool, ("gy", "graveyard", "send"))
    discard_synergy = text_signal_overlap(primary_pool, candidate_pool, ("discard",))
    search_overlap = text_signal_overlap(primary_pool, candidate_pool, ("from your deck", "add 1", "search"))
    summon_compatibility = text_signal_overlap(primary_pool, candidate_pool, ("special summon", "normal summon", "summon 1"))
    extra_deck_compatibility = 1.0 if any(is_extra_deck_monster(card) for card in primary_pool + candidate_pool) else 0.35
    collision = engine_collision_risk(primary_roles, candidate_roles)

    final = (
        attribute_overlap * 0.12
        + level_overlap * 0.12
        + typing_overlap * 0.14
        + graveyard_synergy * 0.12
        + discard_synergy * 0.08
        + search_overlap * 0.12
        + summon_compatibility * 0.14
        + extra_deck_compatibility * 0.08
        + (1 - collision) * 0.08
    )
    return {
        "primary": primary,
        "candidate": candidate,
        "attribute_overlap": round(attribute_overlap, 4),
        "level_overlap": round(level_overlap, 4),
        "typing_overlap": round(typing_overlap, 4),
        "graveyard_synergy": round(graveyard_synergy, 4),
        "discard_synergy": round(discard_synergy, 4),
        "search_overlap": round(search_overlap, 4),
        "summon_compatibility": round(summon_compatibility, 4),
        "extra_deck_compatibility": round(extra_deck_compatibility, 4),
        "engine_collision_risk": round(collision, 4),
        "final_compatibility_score": round(final, 4),
    }


def build_archetype_relationship_graph(cards: list[dict[str, Any]], archetypes: list[str]) -> dict[str, Any]:
    edges = []
    for left, right in combinations(sorted(set(archetypes)), 2):
        edges.append(score_archetype_compatibility(cards, left, right))
    return {
        "archetypes": sorted(set(archetypes)),
        "edge_count": len(edges),
        "edges": sorted(edges, key=lambda edge: edge["final_compatibility_score"], reverse=True),
    }


def attributes(pool: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(card.get("attribute", "")).casefold() for card in pool if card.get("attribute"))


def levels(pool: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(get_card_level(card)) for card in pool if get_card_level(card))


def types(pool: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(card.get("race", "")).casefold() for card in pool if card.get("race"))


def overlap_score(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = sum(min(left[key], right[key]) for key in set(left) & set(right))
    total = max(sum(left.values()), sum(right.values()), 1)
    return min(1.0, shared / total)


def text_signal_overlap(left: list[dict[str, Any]], right: list[dict[str, Any]], terms: tuple[str, ...]) -> float:
    left_rate = text_signal_rate(left, terms)
    right_rate = text_signal_rate(right, terms)
    return min(left_rate, right_rate) if max(left_rate, right_rate) else 0.0


def text_signal_rate(pool: list[dict[str, Any]], terms: tuple[str, ...]) -> float:
    if not pool:
        return 0.0
    hits = 0
    for card in pool:
        text = f"{card.get('name', '')} {card.get('desc', '')}".casefold()
        if any(term in text for term in terms):
            hits += 1
    return hits / len(pool)


def engine_collision_risk(primary_roles: dict[str, Any], candidate_roles: dict[str, Any]) -> float:
    primary_bricks = primary_roles.get("role_counts", {}).get("garnet_brick", 0)
    candidate_bricks = candidate_roles.get("role_counts", {}).get("garnet_brick", 0)
    primary_starters = max(1, primary_roles.get("role_counts", {}).get("starter", 0))
    candidate_starters = max(1, candidate_roles.get("role_counts", {}).get("starter", 0))
    brick_pressure = min(1.0, (primary_bricks + candidate_bricks) / 12)
    starter_pressure = 1.0 - min(1.0, (primary_starters + candidate_starters) / 18)
    return max(0.0, min(1.0, brick_pressure * 0.65 + starter_pressure * 0.35))
