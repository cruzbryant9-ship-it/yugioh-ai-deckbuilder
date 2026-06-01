from __future__ import annotations

from dataclasses import dataclass

from deck.matchup_profiles import MatchupProfile, get_matchup_profile


@dataclass(frozen=True)
class OpponentProfile:
    name: str
    archetype: str
    known_cards: tuple[str, ...]
    likely_engines: tuple[str, ...]
    key_starters: tuple[str, ...]
    key_extenders: tuple[str, ...]
    key_interruptions: tuple[str, ...]
    key_board_breakers: tuple[str, ...]
    graveyard_dependency: float
    backrow_density: float
    spell_trap_density: float
    monster_effect_density: float
    summon_volume: float
    banish_dependency: float
    search_dependency: float
    going_first_plan: tuple[str, ...]
    going_second_plan: tuple[str, ...]
    expected_endboard: tuple[str, ...]
    choke_points: tuple[str, ...]
    recommended_counters: tuple[str, ...]
    nearest_matchup: str = "unknown_meta"
    profile_source: str = "inferred"
    matched_curated_profile: str | None = None
    curated_notes: str = ""
    deck_style: str = ""
    best_counters: tuple[str, ...] = ()
    weak_counters: tuple[str, ...] = ()
    side_in_recommendations: tuple[str, ...] = ()
    side_out_priorities: tuple[str, ...] = ()


def opponent_to_matchup_profile(profile: OpponentProfile) -> MatchupProfile:
    base = get_matchup_profile(profile.nearest_matchup)
    high_value = tuple(
        dict.fromkeys(
            (
                *profile.side_in_recommendations,
                *profile.best_counters,
                *profile.recommended_counters,
                *base.high_value_side_cards,
            )
        )
    )
    low_value = tuple(dict.fromkeys((*profile.side_out_priorities, *profile.weak_counters, *base.low_value_cards)))
    risk_factors = tuple(dict.fromkeys((*profile.choke_points, profile.curated_notes, *base.risk_factors)))
    return MatchupProfile(
        name=profile.name,
        expected_interruption_density=max(base.expected_interruption_density, min(1.0, len(profile.key_interruptions) / 10)),
        expected_board_strength=max(base.expected_board_strength, profile.summon_volume),
        graveyard_dependency=profile.graveyard_dependency,
        backrow_density=profile.backrow_density,
        spell_trap_density=profile.spell_trap_density,
        monster_effect_density=profile.monster_effect_density,
        going_first_priorities=profile.going_first_plan or base.going_first_priorities,
        going_second_priorities=profile.going_second_plan or base.going_second_priorities,
        high_value_side_cards=high_value,
        low_value_cards=tuple(item for item in low_value if item),
        risk_factors=risk_factors,
    )
