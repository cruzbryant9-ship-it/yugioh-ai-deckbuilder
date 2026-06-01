from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterruptionProfile:
    name: str
    can_respond_to: tuple[str, ...]
    target_types: tuple[str, ...]
    timing_window: str
    effect: str
    risk_score: float
    recovery_difficulty: float


COMMON_INTERRUPTION_PROFILES: tuple[InterruptionProfile, ...] = (
    InterruptionProfile("Ash Blossom", ("search", "send_to_gy", "deck_summon"), ("deck",), "response", "effect_negated", 2.0, 1.6),
    InterruptionProfile("Infinite Impermanence", ("monster_effect", "field_effect"), ("monster",), "response", "effect_negated", 1.7, 1.2),
    InterruptionProfile("Effect Veiler", ("monster_effect", "field_effect"), ("monster",), "response", "effect_negated", 1.5, 1.1),
    InterruptionProfile("Droll & Lock Bird", ("search", "deck_add"), ("deck",), "after_search", "search_lock", 1.8, 1.7),
    InterruptionProfile("D.D. Crow", ("gy_effect", "gy_dependency"), ("graveyard",), "response", "target_banished", 1.4, 1.4),
    InterruptionProfile("Nibiru", ("summon_chain",), ("monster",), "open_state", "board_cleared", 2.2, 2.0),
    InterruptionProfile("Called by the Grave", ("gy_effect", "hand_trap"), ("graveyard",), "response", "effect_negated", 1.2, 1.0),
)


def interruption_profiles() -> list[InterruptionProfile]:
    return list(COMMON_INTERRUPTION_PROFILES)


def profile_by_name(name: str) -> InterruptionProfile | None:
    key = name.casefold()
    return next((profile for profile in COMMON_INTERRUPTION_PROFILES if profile.name.casefold() == key), None)
