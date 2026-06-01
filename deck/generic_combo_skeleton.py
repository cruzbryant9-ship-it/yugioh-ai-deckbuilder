from __future__ import annotations

from typing import Any

from deck.archetype_role_inference import infer_archetype_roles


def infer_combo_skeletons(cards: list[dict[str, Any]], archetype: str, limit: int = 12) -> dict[str, Any]:
    analysis = infer_archetype_roles(cards, archetype)
    roles = analysis["roles"]
    starters = roles.get("starter", [])[:limit]
    searchers = roles.get("searcher", [])[:limit]
    extenders = roles.get("extender", [])[:limit]
    payoffs = roles.get("payoff", [])[:limit]
    skeletons = []
    for starter in starters:
        search = choose_related(starter, searchers, fallback=starter, exclude={starter})
        extender = choose_related(starter, extenders, fallback=None, exclude={starter, search} if search else {starter})
        payoff = choose_related(starter, payoffs, fallback=payoffs[0] if payoffs else None, exclude={starter, search, extender})
        if not payoff:
            continue
        skeletons.append(
            {
                "archetype": archetype,
                "line_name": f"{starter} -> {payoff}",
                "starter": starter,
                "search": search,
                "extender": extender,
                "payoff": payoff,
                "skeleton": [card for card in (starter, search, extender, payoff) if card],
                "confidence": skeleton_confidence(starter, search, extender, payoff, analysis),
                "inference_type": "generic_structural",
            }
        )
    return {
        "archetype": archetype,
        "skeleton_count": len(skeletons),
        "skeletons": sorted(skeletons, key=lambda item: item["confidence"], reverse=True)[:limit],
        "role_counts": analysis["role_counts"],
    }


def choose_related(seed: str, candidates: list[str], fallback: str | None, exclude: set[str | None] | None = None) -> str | None:
    excluded = {item for item in (exclude or set()) if item}
    candidates = [candidate for candidate in candidates if candidate not in excluded]
    if not candidates:
        return fallback
    seed_terms = terms(seed)
    ranked = sorted(candidates, key=lambda candidate: len(seed_terms & terms(candidate)), reverse=True)
    return ranked[0] if ranked else fallback


def terms(name: str) -> set[str]:
    return {part for part in name.casefold().replace("-", " ").replace(",", " ").split() if len(part) > 2}


def skeleton_confidence(starter: str, search: str | None, extender: str | None, payoff: str | None, analysis: dict[str, Any]) -> float:
    score = 0.35
    if starter:
        score += 0.18
    if search and search != starter:
        score += 0.14
    if extender:
        score += 0.14
    if payoff:
        score += 0.16
    role_counts = analysis.get("role_counts", {})
    if role_counts.get("starter", 0) and role_counts.get("payoff", 0):
        score += 0.08
    return round(min(0.95, score), 3)
