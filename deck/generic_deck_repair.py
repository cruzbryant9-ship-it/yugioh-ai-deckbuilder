from __future__ import annotations

from collections import Counter
from typing import Any

from deck.archetype_role_inference import archetype_pool, infer_archetype_roles
from deck.card_metadata import get_card_level, is_extra_deck_monster, is_monster
from deck.generic_filler_selector import select_contextual_fillers
from deck.generic_repair_diagnostics import diagnose_under_40_repair
from SystemAIYugioh.banlist import get_card_limit

MAIN_DECK_TARGET = 40
EXTRA_DECK_LIMIT = 15
MIN_STARTERS_SEARCHERS = 8
MIN_EXTENDERS = 4
MAX_REPAIR_ACTIONS = 120

ROLE_PRIORITY = (
    "starters_searchers",
    "extenders",
    "core",
    "interruptions",
    "board_breakers",
    "recovery",
)

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


def repair_generic_deck(
    main_deck: list[dict[str, Any]],
    extra_deck: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None,
    quota_profile: dict[str, int],
    mode: str = "meta",
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    main = [card for card in main_deck if not is_extra_deck_monster(card)]
    extra = [card for card in extra_deck if is_extra_deck_monster(card)]
    actions: list[str] = []

    main = remove_blocked_and_overlimit(main, actions, "main")
    extra = remove_blocked_and_overlimit(extra, actions, "extra")
    extra = trim_extra_deck(extra, actions)
    main = trim_main_deck(main, quota_profile, actions)
    main = enforce_role_minimum(main, archetype, card_pool, package_data, quota_profile, actions)
    main = fill_main_deck(main, archetype, card_pool, package_data, quota_profile, actions)
    main = trim_main_deck(main, quota_profile, actions)
    pre_safe_filler_count = len(main)
    pre_contextual_filler_main = list(main)
    pre_contextual_filler_package_counts = Counter(classify_repair_role(card) for card in main)
    main, filler_metadata = fill_safe_generic_filler(main, archetype, card_pool, mode, actions, enable_filler_memory_influence=enable_filler_memory_influence)
    extra = fill_extra_deck(extra, archetype, card_pool, actions)

    remaining = remaining_warnings(main, extra, quota_profile)
    legal = deck_is_legal(main, extra)
    converged = repair_converged(main, extra, quota_profile)
    capped_actions, action_cap_reached = capped_action_log(actions)
    success = legal and not hard_warnings(remaining) and converged and not action_cap_reached
    failure_cause = None if success else repair_failure_cause(remaining, legal, converged, action_cap_reached)
    diagnostics = diagnose_under_40_repair(main, archetype, card_pool, package_data, quota_profile, mode)
    safe_fillers_added = max(0, len(main) - pre_safe_filler_count)
    return {
        "main": main,
        "extra": extra,
        "repair_success": success,
        "repair_actions": capped_actions,
        "repair_action_count": len(actions),
        "repair_action_cap": MAX_REPAIR_ACTIONS,
        "repair_action_cap_reached": action_cap_reached,
        "repair_converged": converged,
        "repair_failure_cause": failure_cause,
        "under_40_diagnostics": diagnostics,
        "repair_strategy_used": repair_strategy_used(actions, diagnostics),
        "safe_filler_used_count": safe_fillers_added,
        "completed_by_safe_filler": safe_fillers_added > 0 and len(main) == MAIN_DECK_TARGET,
        "pre_contextual_filler_main_count": pre_safe_filler_count,
        "pre_contextual_filler_package_counts": dict(sorted(pre_contextual_filler_package_counts.items())),
        "pre_contextual_filler_card_names": [str(card.get("name", "")) for card in pre_contextual_filler_main if card.get("name")],
        "_pre_contextual_filler_main": pre_contextual_filler_main,
        "contextual_filler_used": bool(filler_metadata.get("selected_fillers")),
        "selected_fillers": filler_metadata.get("selected_fillers", []),
        "filler_reasons": filler_metadata.get("filler_reasons", []),
        "filler_roles": filler_metadata.get("filler_roles", {"counts": {}, "by_card": {}}),
        "filler_context_scores": filler_metadata.get("context_scores", {}),
        "rejected_filler_reasons": filler_metadata.get("rejected_fillers", []),
        "filler_memory_influence": filler_metadata.get("filler_memory_influence", {}),
        "remaining_warnings": remaining,
        "legal": legal,
    }


def remove_blocked_and_overlimit(deck: list[dict[str, Any]], actions: list[str], zone: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    kept: list[dict[str, Any]] = []
    for card in deck:
        name = str(card.get("name", ""))
        limit = get_card_limit(card)
        if limit <= 0:
            actions.append(f"removed blocked card from {zone}: {name}")
            continue
        if counts[name] >= limit:
            actions.append(f"removed over-limit duplicate from {zone}: {name}")
            continue
        kept.append(card)
        counts[name] += 1
    return kept


def trim_extra_deck(extra: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    if len(extra) <= EXTRA_DECK_LIMIT:
        return extra
    trimmed = extra[:EXTRA_DECK_LIMIT]
    actions.append(f"trimmed Extra Deck from {len(extra)} to {EXTRA_DECK_LIMIT}")
    return trimmed


def trim_main_deck(main: list[dict[str, Any]], quota_profile: dict[str, int], actions: list[str]) -> list[dict[str, Any]]:
    deck = list(main)
    max_bricks = int(quota_profile.get("max_bricks", 4) or 4)
    payoff_cap = int(quota_profile.get("payoffs", 4) or 4) + 2
    while len(deck) > MAIN_DECK_TARGET:
        index = removable_index(deck, max_bricks, payoff_cap)
        removed = deck.pop(index)
        actions.append(f"trimmed main deck card: {removed.get('name', '')}")
    return deck


def removable_index(deck: list[dict[str, Any]], max_bricks: int, payoff_cap: int) -> int:
    role_counts = Counter(classify_repair_role(card) for card in deck)
    for idx, card in enumerate(deck):
        role = classify_repair_role(card)
        if role == "garnet_brick" and role_counts["garnet_brick"] > max_bricks:
            return idx
    for idx, card in enumerate(deck):
        role = classify_repair_role(card)
        if role == "payoffs" and role_counts["payoffs"] > payoff_cap:
            return idx
    for idx, card in enumerate(deck):
        if classify_repair_role(card) in {"core", "board_breakers", "recovery"}:
            return idx
    return len(deck) - 1


def enforce_role_minimum(
    main: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None,
    quota_profile: dict[str, int],
    actions: list[str],
) -> list[dict[str, Any]]:
    deck = list(main)
    desired = {
        "starters_searchers": min(int(quota_profile.get("starters_searchers", 10) or 10), MIN_STARTERS_SEARCHERS),
        "extenders": min(int(quota_profile.get("extenders", 6) or 6), MIN_EXTENDERS),
    }
    for role, minimum in desired.items():
        while count_role(deck, role) < minimum:
            candidate = next_repair_candidate(deck, archetype, card_pool, package_data, (role,), quota_profile)
            if not candidate:
                break
            if len(deck) >= MAIN_DECK_TARGET:
                idx = removable_index(deck, int(quota_profile.get("max_bricks", 4) or 4), int(quota_profile.get("payoffs", 4) or 4) + 2)
                removed = deck.pop(idx)
                actions.append(f"replaced {removed.get('name', '')} for missing {role}")
            if add_card(deck, candidate):
                actions.append(f"added {role} repair card: {candidate.get('name', '')}")
            else:
                break
    return deck


def fill_main_deck(
    main: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None,
    quota_profile: dict[str, int],
    actions: list[str],
) -> list[dict[str, Any]]:
    deck = list(main)
    attempts = MAIN_DECK_TARGET * 20
    while len(deck) < MAIN_DECK_TARGET and attempts > 0:
        attempts -= 1
        needed_roles = preferred_fill_roles(deck, quota_profile)
        candidate = next_repair_candidate(deck, archetype, card_pool, package_data, needed_roles, quota_profile)
        if not candidate:
            break
        if add_card(deck, candidate):
            actions.append(f"filled missing main slot with {classify_repair_role(candidate)}: {candidate.get('name', '')}")
        else:
            break
    return deck


def fill_safe_generic_filler(
    main: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    mode: str,
    actions: list[str],
    enable_filler_memory_influence: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    deck = list(main)
    selector = select_contextual_fillers(
        archetype,
        mode,
        MAIN_DECK_TARGET - len(deck),
        card_pool,
        deck,
        Counter(classify_repair_role(card) for card in deck),
        enable_filler_memory_influence=enable_filler_memory_influence,
    )
    selected_cards = selector.get("_selected_cards", [])
    for candidate in selected_cards:
        if len(deck) >= MAIN_DECK_TARGET:
            break
        if add_card(deck, candidate):
            actions.append(f"filled missing main slot with contextual safe filler: {candidate.get('name', '')}")
    public_metadata = {key: value for key, value in selector.items() if key != "_selected_cards"}
    return deck, public_metadata


def fill_extra_deck(extra: list[dict[str, Any]], archetype: str, card_pool: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    selected = list(extra)
    selected_names = {str(card.get("name", "")) for card in selected}
    candidates = [
        card
        for card in archetype_pool(card_pool, archetype)
        if is_extra_deck_monster(card) and get_card_limit(card) > 0
    ]
    for card in sorted(candidates, key=repair_weight, reverse=True):
        if len(selected) >= EXTRA_DECK_LIMIT:
            break
        name = str(card.get("name", ""))
        if name in selected_names:
            continue
        if add_card(selected, card):
            selected_names.add(name)
            actions.append(f"added Extra Deck repair card: {name}")
    return selected


def preferred_fill_roles(deck: list[dict[str, Any]], quota_profile: dict[str, int]) -> tuple[str, ...]:
    role_counts = Counter(classify_repair_role(card) for card in deck)
    roles = []
    if role_counts["starters_searchers"] < MIN_STARTERS_SEARCHERS:
        roles.append("starters_searchers")
    if role_counts["extenders"] < MIN_EXTENDERS:
        roles.append("extenders")
    for role in ROLE_PRIORITY:
        if role_counts[role] < int(quota_profile.get(role, 99) or 99):
            roles.append(role)
    return tuple(dict.fromkeys(roles or ROLE_PRIORITY))


def next_repair_candidate(
    deck: list[dict[str, Any]],
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None,
    roles: tuple[str, ...],
    quota_profile: dict[str, int],
) -> dict[str, Any] | None:
    candidates = repair_candidates(archetype, card_pool, package_data, roles)
    counts = Counter(str(card.get("name", "")) for card in deck)
    current_bricks = count_role(deck, "garnet_brick")
    max_bricks = int(quota_profile.get("max_bricks", 4) or 4)
    for card in candidates:
        name = str(card.get("name", ""))
        role = classify_repair_role(card)
        if get_card_limit(card) <= 0 or counts[name] >= get_card_limit(card):
            continue
        if role == "garnet_brick" and current_bricks >= max_bricks:
            continue
        return card
    return None


def repair_candidates(
    archetype: str,
    card_pool: list[dict[str, Any]],
    package_data: dict[str, Any] | None,
    roles: tuple[str, ...],
) -> list[dict[str, Any]]:
    analysis = package_data.get("analysis") if isinstance(package_data, dict) else None
    if not isinstance(analysis, dict):
        analysis = infer_archetype_roles(card_pool, archetype)
    lookup = {str(card.get("name", "")): card for card in card_pool if card.get("name")}
    names: list[str] = []
    role_map = {
        "starters_searchers": ("starter", "searcher"),
        "extenders": ("extender",),
        "interruptions": ("interruption",),
        "recovery": ("recovery",),
        "board_breakers": ("board_breaker",),
        "payoffs": ("payoff",),
        "core": ("engine_requirement",),
    }
    for role in roles:
        for analysis_role in role_map.get(role, ()):
            names.extend(analysis.get("roles", {}).get(analysis_role, []))
    candidates = [lookup[name] for name in dict.fromkeys(names) if name in lookup and not is_extra_deck_monster(lookup[name])]
    if any(role in {"interruptions", "board_breakers"} for role in roles):
        candidates.extend(generic_staples(card_pool, roles))
    if "core" in roles:
        candidates.extend(card for card in archetype_pool(card_pool, archetype) if not is_extra_deck_monster(card))
    return sorted(dedup_cards(candidates), key=repair_weight, reverse=True)


def generic_staples(card_pool: list[dict[str, Any]], roles: tuple[str, ...]) -> list[dict[str, Any]]:
    selected = []
    for card in card_pool:
        name = str(card.get("name", "")).casefold()
        if get_card_limit(card) <= 0 or is_extra_deck_monster(card):
            continue
        if not any(term in name for term in GENERIC_STAPLE_TERMS):
            continue
        role = classify_repair_role(card)
        if role in roles:
            selected.append(card)
    return selected


def add_card(deck: list[dict[str, Any]], card: dict[str, Any]) -> bool:
    name = str(card.get("name", ""))
    counts = Counter(str(existing.get("name", "")) for existing in deck)
    if get_card_limit(card) <= 0 or counts[name] >= get_card_limit(card):
        return False
    deck.append(card)
    return True


def remaining_warnings(main: list[dict[str, Any]], extra: list[dict[str, Any]], quota_profile: dict[str, int]) -> list[str]:
    warnings = []
    if len(main) < MAIN_DECK_TARGET:
        warnings.append(f"main deck below 40 cards: {len(main)}")
    if len(main) > MAIN_DECK_TARGET:
        warnings.append(f"main deck above 40 cards: {len(main)}")
    if len(extra) > EXTRA_DECK_LIMIT:
        warnings.append(f"Extra Deck above 15 cards: {len(extra)}")
    role_counts = Counter(classify_repair_role(card) for card in main)
    if role_counts["starters_searchers"] < MIN_STARTERS_SEARCHERS:
        warnings.append(f"starter/searcher minimum missed: {role_counts['starters_searchers']}<{MIN_STARTERS_SEARCHERS}")
    if role_counts["extenders"] < MIN_EXTENDERS:
        warnings.append(f"extender minimum missed: {role_counts['extenders']}<{MIN_EXTENDERS}")
    payoff_cap = int(quota_profile.get("payoffs", 4) or 4) + 2
    if role_counts["payoffs"] > payoff_cap:
        warnings.append(f"payoff overfill: {role_counts['payoffs']}>{payoff_cap}")
    max_bricks = int(quota_profile.get("max_bricks", 4) or 4)
    if role_counts["garnet_brick"] > max_bricks:
        warnings.append(f"brick cap exceeded: {role_counts['garnet_brick']}>{max_bricks}")
    warnings.extend(copy_limit_warnings(main + extra))
    return sorted(set(warnings))


def deck_is_legal(main: list[dict[str, Any]], extra: list[dict[str, Any]]) -> bool:
    return len(main) == MAIN_DECK_TARGET and len(extra) <= EXTRA_DECK_LIMIT and not hard_warnings(remaining_warnings(main, extra, {"max_bricks": 99, "payoffs": 99}))


def repair_converged(main: list[dict[str, Any]], extra: list[dict[str, Any]], quota_profile: dict[str, int]) -> bool:
    probe_actions: list[str] = []
    normalized_main = remove_blocked_and_overlimit(list(main), probe_actions, "main")
    normalized_extra = remove_blocked_and_overlimit(list(extra), probe_actions, "extra")
    normalized_main = trim_main_deck(normalized_main, quota_profile, probe_actions)
    normalized_extra = trim_extra_deck(normalized_extra, probe_actions)
    return deck_signature(main, extra) == deck_signature(normalized_main, normalized_extra)


def deck_signature(main: list[dict[str, Any]], extra: list[dict[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(sorted(str(card.get("name", "")) for card in main)),
        tuple(sorted(str(card.get("name", "")) for card in extra)),
    )


def capped_action_log(actions: list[str]) -> tuple[list[str], bool]:
    if len(actions) <= MAX_REPAIR_ACTIONS:
        return actions, False
    return actions[:MAX_REPAIR_ACTIONS] + [f"repair action cap reached: {len(actions)}>{MAX_REPAIR_ACTIONS}"], True


def repair_failure_cause(warnings: list[str], legal: bool, converged: bool, action_cap_reached: bool) -> str | None:
    if action_cap_reached:
        return "repair_action_cap"
    lowered = " | ".join(warnings).casefold()
    if "blocked card" in lowered:
        return "blocked_card"
    if "copy limit exceeded" in lowered:
        return "copy_limit_failed"
    if "main deck below" in lowered or "main deck above" in lowered:
        return "incomplete_deck"
    if "extra deck above" in lowered:
        return "extra_deck_limit_failed"
    if not converged:
        return "repair_not_converged"
    if not legal:
        return "legality_failed"
    if warnings:
        return "quota_warning"
    return None


def hard_warnings(warnings: list[str]) -> list[str]:
    hard_terms = ("blocked card", "copy limit exceeded", "main deck below", "main deck above", "Extra Deck above")
    return [warning for warning in warnings if any(term in warning for term in hard_terms)]


def copy_limit_warnings(deck: list[dict[str, Any]]) -> list[str]:
    warnings = []
    counts = Counter(str(card.get("name", "")) for card in deck)
    by_name = {str(card.get("name", "")): card for card in deck}
    for name, count in counts.items():
        limit = get_card_limit(by_name[name])
        if limit <= 0:
            warnings.append(f"blocked card selected: {name}")
        elif count > limit:
            warnings.append(f"copy limit exceeded: {name} {count}>{limit}")
    return warnings


def count_role(deck: list[dict[str, Any]], role: str) -> int:
    return sum(1 for card in deck if classify_repair_role(card) == role)


def classify_repair_role(card: dict[str, Any]) -> str:
    text = f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()
    level = safe_int(card.get("level"))
    if not is_monster(card) and ("quick-play" in text or "field spell" in text or "continuous spell" in text or "continuous trap" in text):
        if "add " in text or "from your deck" in text or "draw" in text:
            return "starters_searchers"
        if "special summon" in text or "activate" in text or "target" in text:
            return "core"
    if is_monster(card) and level >= 7 and "special summon" not in text and "ritual" not in text:
        return "garnet_brick"
    if "from your deck" in text or "add 1" in text or "search" in text:
        return "starters_searchers"
    if "special summon" in text:
        return "extenders"
    if "negate" in text or "quick effect" in text or "banish" in text or "destroy" in text:
        return "interruptions"
    if "dark ruler" in text or "evenly matched" in text or "lightning storm" in text or "raigeki" in text or "forbidden droplet" in text:
        return "board_breakers"
    if "from your gy" in text or "from your graveyard" in text or "in your gy" in text:
        return "recovery"
    if is_monster(card) and level >= 7:
        return "payoffs"
    return "core"


def repair_strategy_used(actions: list[str], diagnostics: dict[str, Any]) -> str:
    if any("contextual safe filler" in action for action in actions):
        return "contextual_safe_filler"
    if any("safe filler" in action for action in actions):
        return "safe_generic_filler"
    if diagnostics.get("under_40_reason") == "complete":
        return "archetype_package_repair"
    return str(diagnostics.get("recommended_repair_strategy") or "unresolved")


def repair_weight(card: dict[str, Any]) -> float:
    role = classify_repair_role(card)
    weights = {
        "starters_searchers": 1.0,
        "extenders": 0.88,
        "interruptions": 0.8,
        "recovery": 0.7,
        "board_breakers": 0.65,
        "core": 0.5,
        "payoffs": 0.35,
        "garnet_brick": 0.1,
    }
    text = f"{card.get('name', '')} {card.get('desc', '')}".casefold()
    bonus = 0.1 if "from your deck" in text else 0
    return weights.get(role, 0.4) + bonus


def dedup_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for card in cards:
        name = str(card.get("name", ""))
        if name and name not in seen:
            seen.add(name)
            unique.append(card)
    return unique


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
