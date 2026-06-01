from __future__ import annotations

import random
from typing import Any

from deck.opponent_profiles import OpponentProfile


def simulate_opponent_openings(
    opponent_decklist: dict[str, list[str]] | list[str],
    opponent_profile: OpponentProfile,
    runs: int = 1000,
) -> dict[str, float]:
    """Estimate opponent opening access without simulating a full duel."""
    main = normalize_main_deck(opponent_decklist)
    if not main:
        return empty_probability_report()
    runs = max(1, int(runs))
    rng = random.Random(stable_seed(main, opponent_profile.archetype, runs))
    counters = {
        "starter": 0,
        "extender": 0,
        "interruption": 0,
        "board_breaker": 0,
        "line": 0,
        "backup": 0,
        "brick": 0,
        "graveyard": 0,
        "search": 0,
    }
    for _ in range(runs):
        hand = rng.sample(main, min(5, len(main)))
        starter = hand_has(hand, opponent_profile.key_starters)
        extender = hand_has(hand, opponent_profile.key_extenders)
        interruption = hand_has(hand, opponent_profile.key_interruptions) or any(is_generic_interruption(card) for card in hand)
        board_breaker = hand_has(hand, opponent_profile.key_board_breakers) or any(is_board_breaker(card) for card in hand)
        search = any(is_search_access(card, opponent_profile) for card in hand)
        graveyard = any(is_graveyard_access(card, opponent_profile) for card in hand)
        line = starter or search
        backup = extender or (line and graveyard)
        brick = not line and not extender and not interruption and not board_breaker
        counters["starter"] += int(starter)
        counters["extender"] += int(extender)
        counters["interruption"] += int(interruption)
        counters["board_breaker"] += int(board_breaker)
        counters["line"] += int(line)
        counters["backup"] += int(backup)
        counters["brick"] += int(brick)
        counters["graveyard"] += int(graveyard)
        counters["search"] += int(search)
    return {
        "opponent_starter_open_rate": round(counters["starter"] / runs, 4),
        "opponent_extender_open_rate": round(counters["extender"] / runs, 4),
        "opponent_interruption_open_rate": round(counters["interruption"] / runs, 4),
        "opponent_board_breaker_open_rate": round(counters["board_breaker"] / runs, 4),
        "opponent_likely_line_access_rate": round(counters["line"] / runs, 4),
        "opponent_backup_line_access_rate": round(counters["backup"] / runs, 4),
        "opponent_brick_rate": round(counters["brick"] / runs, 4),
        "opponent_graveyard_access_rate": round(counters["graveyard"] / runs, 4),
        "opponent_search_access_rate": round(counters["search"] / runs, 4),
    }


def normalize_main_deck(opponent_decklist: dict[str, list[str]] | list[str]) -> list[str]:
    if isinstance(opponent_decklist, dict):
        return [str(card) for card in opponent_decklist.get("main", [])]
    return [str(card) for card in opponent_decklist]


def empty_probability_report() -> dict[str, float]:
    return {
        "opponent_starter_open_rate": 0.0,
        "opponent_extender_open_rate": 0.0,
        "opponent_interruption_open_rate": 0.0,
        "opponent_board_breaker_open_rate": 0.0,
        "opponent_likely_line_access_rate": 0.0,
        "opponent_backup_line_access_rate": 0.0,
        "opponent_brick_rate": 0.0,
        "opponent_graveyard_access_rate": 0.0,
        "opponent_search_access_rate": 0.0,
    }


def hand_has(hand: list[str], targets: tuple[str, ...]) -> bool:
    return any(card_matches(card, target) for card in hand for target in targets)


def card_matches(card: str, target: str) -> bool:
    left = card.casefold()
    right = target.casefold()
    return bool(left and right and (left in right or right in left))


def is_generic_interruption(card: str) -> bool:
    lowered = card.casefold()
    terms = ("ash blossom", "droll", "infinite impermanence", "effect veiler", "nibiru", "d.d. crow", "ghost belle", "bystial")
    return any(term in lowered for term in terms)


def is_board_breaker(card: str) -> bool:
    lowered = card.casefold()
    terms = ("evenly matched", "dark ruler", "raigeki", "lightning storm", "feather duster", "book of eclipse", "kaiju")
    return any(term in lowered for term in terms)


def is_search_access(card: str, profile: OpponentProfile) -> bool:
    lowered = card.casefold()
    if any(card_matches(card, starter) for starter in profile.key_starters):
        return True
    terms = ("search", "add", "bonfire", "wanted", "prosperity", "terraforming", "small world", "tip")
    return any(term in lowered for term in terms)


def is_graveyard_access(card: str, profile: OpponentProfile) -> bool:
    lowered = card.casefold()
    if profile.graveyard_dependency >= 0.6 and any(card_matches(card, extender) for extender in profile.key_extenders):
        return True
    terms = ("grave", "gy", "foolish", "send", "tearlaments", "bystial", "branded fusion", "sinful spoils")
    return any(term in lowered for term in terms)


def stable_seed(main: list[str], archetype: str, runs: int) -> int:
    text = "|".join(main[:60]) + archetype + str(runs)
    return sum((index + 1) * ord(char) for index, char in enumerate(text)) % 1_000_003
