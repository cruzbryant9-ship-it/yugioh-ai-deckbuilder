from __future__ import annotations

from collections import Counter
from typing import Any


ROLE_ALIASES = {
    "starter": "starters_searchers",
    "searcher": "starters_searchers",
    "starters": "starters_searchers",
    "searchers": "starters_searchers",
    "starter_searcher": "starters_searchers",
    "starters_searchers": "starters_searchers",
    "extender": "extenders",
    "extenders": "extenders",
    "payoff": "payoffs",
    "payoffs": "payoffs",
    "interruption": "interruptions",
    "interruptions": "interruptions",
    "handtrap": "interruptions",
    "handtraps": "interruptions",
    "board_breaker": "board_breakers",
    "board_breakers": "board_breakers",
    "garnet": "bricks",
    "brick": "bricks",
    "bricks": "bricks",
    "garnet_brick": "bricks",
    "recovery": "recovery",
    "core": "core",
}

ORDERED_ROLES = ("starters_searchers", "extenders", "payoffs", "interruptions", "board_breakers", "bricks", "recovery", "core", "unknown")


def explain_card_shifts(
    baseline_deck: list[Any],
    candidate_deck: list[Any],
    role_map: dict[str, str] | None,
    package_data: dict[str, Any] | None,
    score_delta: float,
) -> dict[str, Any]:
    baseline_counts = Counter(card_name(card) for card in baseline_deck if card_name(card))
    candidate_counts = Counter(card_name(card) for card in candidate_deck if card_name(card))
    all_names = sorted(set(baseline_counts) | set(candidate_counts))
    lookup = build_role_lookup(role_map or {}, package_data or {})

    cards_added = [name for name in all_names if baseline_counts[name] == 0 and candidate_counts[name] > 0]
    cards_removed = [name for name in all_names if baseline_counts[name] > 0 and candidate_counts[name] == 0]
    copy_increases = {name: candidate_counts[name] - baseline_counts[name] for name in all_names if candidate_counts[name] > baseline_counts[name]}
    copy_decreases = {name: baseline_counts[name] - candidate_counts[name] for name in all_names if baseline_counts[name] > candidate_counts[name]}
    role_delta = compute_role_delta(copy_increases, copy_decreases, lookup)
    package_delta = {role: role_delta[role]["net"] for role in ORDERED_ROLES if role_delta[role]["net"]}
    risk_flags = build_risk_flags(role_delta, copy_increases, copy_decreases)

    return {
        "cards_added": cards_added,
        "cards_removed": cards_removed,
        "copy_increases": copy_increases,
        "copy_decreases": copy_decreases,
        "role_delta": role_delta,
        "package_delta": package_delta,
        "explanation": build_explanation(score_delta, role_delta, copy_increases, copy_decreases, risk_flags),
        "risk_flags": risk_flags,
    }


def build_role_lookup(role_map: dict[str, str], package_data: dict[str, Any]) -> dict[str, str]:
    lookup = {str(name): normalize_role(role) for name, role in role_map.items()}
    analysis = package_data.get("analysis", {}) if isinstance(package_data, dict) else {}
    roles = analysis.get("roles", {}) if isinstance(analysis, dict) else {}
    if isinstance(roles, dict):
        for role, names in roles.items():
            for name in names or []:
                lookup.setdefault(str(name), normalize_role(str(role)))
    for package in package_data.get("packages", []) if isinstance(package_data, dict) else []:
        package_type = normalize_role(str(package.get("package_type", "unknown")))
        for name in package.get("card_names", []) or []:
            lookup.setdefault(str(name), package_type)
    return lookup


def compute_role_delta(copy_increases: dict[str, int], copy_decreases: dict[str, int], role_lookup: dict[str, str]) -> dict[str, dict[str, int]]:
    delta = {role: {"gained": 0, "lost": 0, "net": 0} for role in ORDERED_ROLES}
    for name, count in copy_increases.items():
        role = role_lookup.get(name, "unknown")
        delta.setdefault(role, {"gained": 0, "lost": 0, "net": 0})
        delta[role]["gained"] += int(count)
        delta[role]["net"] += int(count)
    for name, count in copy_decreases.items():
        role = role_lookup.get(name, "unknown")
        delta.setdefault(role, {"gained": 0, "lost": 0, "net": 0})
        delta[role]["lost"] += int(count)
        delta[role]["net"] -= int(count)
    return delta


def build_risk_flags(role_delta: dict[str, dict[str, int]], copy_increases: dict[str, int], copy_decreases: dict[str, int]) -> list[str]:
    flags = []
    if role_delta["starters_searchers"]["net"] < 0:
        flags.append("starter_searcher_loss")
    if role_delta["extenders"]["net"] < 0:
        flags.append("extender_loss")
    if role_delta["interruptions"]["net"] < 0:
        flags.append("interruption_loss")
    if role_delta["bricks"]["net"] > 0:
        flags.append("brick_pressure_increased")
    if role_delta["payoffs"]["net"] > 1:
        flags.append("payoff_overfill_risk")
    if role_delta["board_breakers"]["net"] > 2:
        flags.append("board_breaker_overfill_risk")
    moved_cards = len(copy_increases) + len(copy_decreases)
    moved_copies = sum(copy_increases.values()) + sum(copy_decreases.values())
    if moved_cards >= 8 or moved_copies >= 12:
        flags.append("package_instability")
    return flags


def build_explanation(
    score_delta: float,
    role_delta: dict[str, dict[str, int]],
    copy_increases: dict[str, int],
    copy_decreases: dict[str, int],
    risk_flags: list[str],
) -> str:
    added_roles = [f"+{values['net']} {role}" for role, values in role_delta.items() if values["net"] > 0 and role != "unknown"]
    lost_roles = [f"{values['net']} {role}" for role, values in role_delta.items() if values["net"] < 0 and role != "unknown"]
    top_added = ", ".join(list(copy_increases)[:3]) or "no major additions"
    top_removed = ", ".join(list(copy_decreases)[:3]) or "no major removals"
    direction = "improved" if score_delta > 0 else "declined" if score_delta < 0 else "stayed flat"
    reason = f"Candidate {direction} by {round(float(score_delta or 0), 4)}. Added {top_added}; removed {top_removed}."
    if added_roles:
        reason += f" Role gains: {', '.join(added_roles[:4])}."
    if lost_roles:
        reason += f" Role losses: {', '.join(lost_roles[:4])}."
    if risk_flags:
        reason += f" Risks: {', '.join(risk_flags[:4])}."
    return reason


def normalize_role(role: str) -> str:
    return ROLE_ALIASES.get(str(role).casefold(), str(role).casefold() or "unknown")


def card_name(card: Any) -> str:
    if isinstance(card, dict):
        return str(card.get("name", ""))
    return str(card or "")
