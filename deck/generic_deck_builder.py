from __future__ import annotations

from collections import Counter
from typing import Any

from deck.archetype_relationship_graph import score_archetype_compatibility
from deck.archetype_role_inference import archetype_pool, infer_archetype_roles
from deck.card_metadata import is_extra_deck_monster
from deck.generic_combo_skeleton import infer_combo_skeletons
from deck.generic_deck_repair import repair_generic_deck
from deck.generic_package_extractor import extract_generic_packages
from deck.generic_ratio_memory import ratio_profile_from_memory
from SystemAIYugioh.banlist import get_card_limit


GENERIC_QUOTAS = {
    "meta": {
        "starters_searchers": 11,
        "extenders": 6,
        "payoffs": 3,
        "recovery": 2,
        "interruptions": 8,
        "board_breakers": 2,
        "max_bricks": 4,
    },
    "innovation": {
        "starters_searchers": 9,
        "extenders": 8,
        "payoffs": 5,
        "recovery": 3,
        "interruptions": 5,
        "board_breakers": 3,
        "max_bricks": 5,
    },
}

GENERIC_STAPLE_TERMS = (
    "ash blossom",
    "effect veiler",
    "droll & lock bird",
    "d.d. crow",
    "nibiru",
    "infinite impermanence",
    "ghost belle",
    "ghost ogre",
    "dark ruler no more",
    "evenly matched",
    "lightning storm",
    "raigeki",
    "harpie's feather duster",
    "forbidden droplet",
)


def build_generic_deck(
    archetype: str,
    card_pool: list[dict[str, Any]],
    mode: str = "meta",
    engine_hint: str | None = None,
    ratio_profile: dict[str, int] | None = None,
    use_ratio_memory: bool = True,
    enable_filler_memory_influence: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    analysis = infer_archetype_roles(card_pool, archetype)
    packages = extract_generic_packages(card_pool, archetype)
    skeletons = infer_combo_skeletons(card_pool, archetype)
    pool = archetype_pool(card_pool, archetype)
    lookup = {str(card.get("name", "")): card for card in card_pool if card.get("name")}
    quotas = resolve_ratio_profile(archetype, mode, ratio_profile, use_ratio_memory)
    main_pool = [card for card in pool if legal_card(card) and not is_extra_deck_monster(card)]
    extra_pool = [card for card in pool if legal_card(card) and is_extra_deck_monster(card)]
    staples = generic_staples(card_pool)

    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    quota_warnings: list[str] = []
    package_counts: Counter[str] = Counter()

    add_role_cards(
        selected,
        counts,
        role_candidates(analysis, lookup, ("starter", "searcher"), main_only=True),
        quotas["starters_searchers"],
        "starters_searchers",
        package_counts,
        archetype,
        engine_hint,
    )
    add_role_cards(selected, counts, role_candidates(analysis, lookup, ("extender",), main_only=True), quotas["extenders"], "extenders", package_counts, archetype, engine_hint)
    add_role_cards(selected, counts, role_candidates(analysis, lookup, ("payoff",), main_only=True), quotas["payoffs"], "payoffs", package_counts, archetype, engine_hint)
    add_role_cards(selected, counts, role_candidates(analysis, lookup, ("recovery",), main_only=True), quotas["recovery"], "recovery", package_counts, archetype, engine_hint)
    add_role_cards(selected, counts, role_candidates(analysis, lookup, ("interruption",), main_only=True) + staples["interruptions"], quotas["interruptions"], "interruptions", package_counts, archetype, engine_hint)
    add_role_cards(selected, counts, role_candidates(analysis, lookup, ("board_breaker",), main_only=True) + staples["board_breakers"], quotas["board_breakers"], "board_breakers", package_counts, archetype, engine_hint)

    fill_main_deck(selected, counts, main_pool, package_counts, archetype, engine_hint, mode, target_size=40, max_bricks=quotas["max_bricks"])
    selected = trim_main_deck(selected, counts, target_size=40)
    extra_deck = choose_extra_deck(extra_pool, analysis, limit=15)

    repair = repair_generic_deck(
        selected,
        extra_deck,
        archetype,
        card_pool,
        {"analysis": analysis, "packages": packages},
        quotas,
        mode=mode,
        enable_filler_memory_influence=enable_filler_memory_influence,
    )
    selected = repair["main"]
    extra_deck = repair["extra"]
    package_counts = recompute_package_counts(selected)
    quota_warnings.extend(repair["remaining_warnings"])

    confidence = generic_confidence_score(analysis, packages, skeletons, selected, extra_deck)
    report = {
        "builder_used": "generic",
        "generic_confidence_score": confidence,
        "main_deck_count": len(selected),
        "extra_deck_count": len(extra_deck),
        "package_counts": dict(sorted(package_counts.items())),
        "quota_warnings": sorted(set(quota_warnings)),
        "combo_skeleton_count": skeletons["skeleton_count"],
        "role_counts": analysis["role_counts"],
        "side_candidates": packages.get("side_package_candidates", [])[:15],
        "engine_hint": engine_hint,
        "package_source": packages.get("source"),
        "ratio_profile": dict(quotas),
        "ratio_memory_used": bool(use_ratio_memory and not ratio_profile and ratio_profile_from_memory(archetype, mode)),
        "repair_used": bool(repair["repair_actions"]),
        "repair_success": bool(repair["repair_success"]),
        "repair_actions": repair["repair_actions"],
        "repair_action_count": repair.get("repair_action_count", len(repair.get("repair_actions", []))),
        "repair_action_cap_reached": repair.get("repair_action_cap_reached", False),
        "repair_converged": repair.get("repair_converged", True),
        "repair_failure_cause": repair.get("repair_failure_cause"),
        "under_40_diagnostics": repair.get("under_40_diagnostics", {}),
        "repair_strategy_used": repair.get("repair_strategy_used"),
        "safe_filler_used_count": repair.get("safe_filler_used_count", 0),
        "completed_by_safe_filler": repair.get("completed_by_safe_filler", False),
        "pre_contextual_filler_main_count": repair.get("pre_contextual_filler_main_count", len(selected)),
        "pre_contextual_filler_package_counts": repair.get("pre_contextual_filler_package_counts", {}),
        "pre_contextual_filler_card_names": repair.get("pre_contextual_filler_card_names", []),
        "_pre_contextual_filler_main": repair.get("_pre_contextual_filler_main", []),
        "contextual_filler_used": repair.get("contextual_filler_used", False),
        "selected_fillers": repair.get("selected_fillers", []),
        "filler_reasons": repair.get("filler_reasons", []),
        "filler_roles": repair.get("filler_roles", {"counts": {}, "by_card": {}}),
        "filler_context_scores": repair.get("filler_context_scores", {}),
        "rejected_filler_reasons": repair.get("rejected_filler_reasons", []),
        "filler_memory_influence": repair.get("filler_memory_influence", {}),
        "remaining_warnings": repair["remaining_warnings"],
    }
    return selected + extra_deck, report


def recompute_package_counts(main_deck: list[dict[str, Any]]) -> Counter[str]:
    return Counter(primary_role(card) for card in main_deck)


def resolve_ratio_profile(
    archetype: str,
    mode: str,
    ratio_profile: dict[str, int] | None = None,
    use_ratio_memory: bool = True,
) -> dict[str, int]:
    quotas = dict(GENERIC_QUOTAS.get(mode, GENERIC_QUOTAS["meta"]))
    memory_profile = ratio_profile_from_memory(archetype, mode) if use_ratio_memory and not ratio_profile else {}
    for source in (memory_profile, ratio_profile or {}):
        for key, value in source.items():
            if key in quotas:
                quotas[key] = bounded_quota(key, value, mode)
    return quotas


def bounded_quota(key: str, value: int, mode: str) -> int:
    base = GENERIC_QUOTAS.get(mode, GENERIC_QUOTAS["meta"]).get(key, value)
    if key == "max_bricks":
        return max(2, min(6, int(value)))
    return max(0, min(16, int(value), max(base + 5, 16)))


def legal_card(card: dict[str, Any]) -> bool:
    return bool(card.get("name")) and get_card_limit(card) > 0


def role_candidates(
    analysis: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
    roles: tuple[str, ...],
    main_only: bool = False,
) -> list[dict[str, Any]]:
    names = []
    for role in roles:
        names.extend(analysis.get("roles", {}).get(role, []))
    candidates = []
    seen = set()
    for name in names:
        card = lookup.get(name)
        if not card or name in seen or not legal_card(card):
            continue
        if main_only and is_extra_deck_monster(card):
            continue
        seen.add(name)
        candidates.append(card)
    return candidates


def generic_staples(card_pool: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    interruptions: list[dict[str, Any]] = []
    board_breakers: list[dict[str, Any]] = []
    for card in card_pool:
        if not legal_card(card) or is_extra_deck_monster(card):
            continue
        name = str(card.get("name", "")).casefold()
        if not any(term in name for term in GENERIC_STAPLE_TERMS):
            continue
        if any(term in name for term in ("dark ruler", "evenly", "lightning storm", "raigeki", "harpie", "droplet")):
            board_breakers.append(card)
        else:
            interruptions.append(card)
    return {"interruptions": sorted(interruptions, key=lambda card: str(card.get("name", ""))), "board_breakers": sorted(board_breakers, key=lambda card: str(card.get("name", "")))}


def add_role_cards(
    selected: list[dict[str, Any]],
    counts: Counter[str],
    candidates: list[dict[str, Any]],
    target: int,
    package_type: str,
    package_counts: Counter[str],
    archetype: str,
    engine_hint: str | None,
) -> None:
    if target <= 0 or not candidates:
        return
    ordered = sorted(candidates, key=lambda card: candidate_weight(card, archetype, engine_hint), reverse=True)
    attempts = max(60, target * 20)
    index = 0
    while package_counts[package_type] < target and attempts > 0:
        attempts -= 1
        card = ordered[index % len(ordered)]
        index += 1
        if add_card(selected, counts, card):
            package_counts[package_type] += 1


def fill_main_deck(
    selected: list[dict[str, Any]],
    counts: Counter[str],
    candidates: list[dict[str, Any]],
    package_counts: Counter[str],
    archetype: str,
    engine_hint: str | None,
    mode: str,
    target_size: int,
    max_bricks: int,
) -> None:
    ordered = sorted(candidates, key=lambda card: candidate_weight(card, archetype, engine_hint), reverse=True)
    attempts = target_size * 100
    index = 0
    while len(selected) < target_size and attempts > 0 and ordered:
        attempts -= 1
        card = ordered[index % len(ordered)]
        index += 1
        role = primary_role(card)
        if role == "garnet_brick" and package_counts["garnet_brick"] >= max_bricks:
            continue
        if add_card(selected, counts, card):
            package_counts[role] += 1


def trim_main_deck(selected: list[dict[str, Any]], counts: Counter[str], target_size: int) -> list[dict[str, Any]]:
    deck = list(selected)
    while len(deck) > target_size:
        index = next((idx for idx, card in enumerate(deck) if primary_role(card) == "garnet_brick"), len(deck) - 1)
        card = deck.pop(index)
        counts[str(card.get("name", ""))] -= 1
    return deck


def choose_extra_deck(extra_pool: list[dict[str, Any]], analysis: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    payoff_names = set(analysis.get("roles", {}).get("payoff", []))
    ordered = sorted(
        extra_pool,
        key=lambda card: (str(card.get("name", "")) in payoff_names, candidate_weight(card, "", None)),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for card in ordered:
        while len(selected) < limit and counts[str(card.get("name", ""))] < get_card_limit(card):
            selected.append(card)
            counts[str(card.get("name", ""))] += 1
            break
        if len(selected) >= limit:
            break
    return selected


def add_card(selected: list[dict[str, Any]], counts: Counter[str], card: dict[str, Any]) -> bool:
    name = str(card.get("name", ""))
    if not legal_card(card) or counts[name] >= get_card_limit(card):
        return False
    selected.append(card)
    counts[name] += 1
    return True


def candidate_weight(card: dict[str, Any], archetype: str, engine_hint: str | None) -> float:
    text = f"{card.get('name', '')} {card.get('archetype', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()
    weight = 1.0
    if archetype and archetype.casefold() in text:
        weight += 0.35
    if engine_hint and engine_hint.casefold() in text:
        weight += 0.15
    if "from your deck" in text or "add 1" in text:
        weight += 0.25
    if "special summon" in text:
        weight += 0.18
    if "quick effect" in text or "negate" in text:
        weight += 0.16
    if primary_role(card) == "garnet_brick":
        weight -= 0.3
    return max(0.1, weight)


def primary_role(card: dict[str, Any]) -> str:
    text = f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()
    level = safe_int(card.get("level"))
    if level >= 7 and "special summon" not in text and "ritual" not in text:
        return "garnet_brick"
    if "from your deck" in text or "add 1" in text or "search" in text:
        return "starters_searchers"
    if "special summon" in text:
        return "extenders"
    if "negate" in text or "quick effect" in text or "banish" in text or "destroy" in text:
        return "interruptions"
    if "from your gy" in text or "from your graveyard" in text or "in your gy" in text:
        return "recovery"
    return "core"


def copy_limit_warnings(deck: list[dict[str, Any]]) -> list[str]:
    warnings = []
    counts = Counter(str(card.get("name", "")) for card in deck)
    by_name = {str(card.get("name", "")): card for card in deck}
    for name, count in counts.items():
        limit = get_card_limit(by_name[name])
        if limit <= 0:
            warnings.append(f"blocked card selected: {name}")
        if count > limit:
            warnings.append(f"copy limit exceeded: {name} {count}>{limit}")
    return warnings


def generic_confidence_score(
    analysis: dict[str, Any],
    packages: dict[str, Any],
    skeletons: dict[str, Any],
    main_deck: list[dict[str, Any]],
    extra_deck: list[dict[str, Any]],
) -> float:
    role_counts = analysis.get("role_counts", {})
    score = 0.0
    score += min(0.22, role_counts.get("starter", 0) / 12 * 0.22)
    score += min(0.18, role_counts.get("extender", 0) / 10 * 0.18)
    score += min(0.16, role_counts.get("payoff", 0) / 8 * 0.16)
    score += min(0.14, len(packages.get("packages", [])) / 6 * 0.14)
    score += min(0.14, skeletons.get("skeleton_count", 0) / 8 * 0.14)
    score += 0.08 if len(main_deck) >= 40 else 0.0
    score += min(0.08, len(extra_deck) / 15 * 0.08)
    return round(min(0.95, max(0.05, score)), 4)


def compatibility_hint(cards: list[dict[str, Any]], archetype: str, engine_hint: str | None) -> dict[str, Any] | None:
    if not engine_hint:
        return None
    try:
        return score_archetype_compatibility(cards, archetype, engine_hint)
    except Exception:
        return None


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
