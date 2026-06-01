from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.opponent_profiles import OpponentProfile
from SystemAIYugioh.json_utils import safe_load_json

CURATED_PROFILES_PATH = Path("SystemAIYugioh") / "data" / "opponent_profiles" / "curated_profiles.json"


def load_curated_profiles(path: Path | str = CURATED_PROFILES_PATH) -> list[dict[str, Any]]:
    profile_path = Path(path)
    if not profile_path.exists():
        return []
    data = safe_load_json(profile_path, {})
    return list(data.get("profiles", []))


def find_curated_profile(name_or_archetype: str | None) -> dict[str, Any] | None:
    if not name_or_archetype:
        return None
    needle = normalize(name_or_archetype)
    for profile in load_curated_profiles():
        names = [profile.get("archetype", ""), *profile.get("aliases", [])]
        if any(needle == normalize(name) or needle in normalize(name) for name in names):
            return profile
    return None


def match_profile_from_decklist(parsed_decklist: dict[str, list[str]]) -> dict[str, Any] | None:
    card_names = parsed_decklist.get("all_cards", []) or parsed_decklist.get("main", [])
    joined = " ".join(card_names)
    best_profile = None
    best_score = 0.0
    for profile in load_curated_profiles():
        score = profile_match_score(profile, card_names, joined)
        if score > best_score:
            best_profile = profile
            best_score = score
    return best_profile if best_score >= 3.0 else None


def curated_to_opponent_profile(curated: dict[str, Any]) -> OpponentProfile:
    return OpponentProfile(
        name=f"{curated.get('archetype', 'Curated')} curated profile",
        archetype=str(curated.get("archetype", "Unknown")),
        known_cards=tuple(curated.get("core_cards", [])),
        likely_engines=tuple(curated.get("core_cards", [])[:5]),
        key_starters=tuple(curated.get("starters", [])),
        key_extenders=tuple(curated.get("extenders", [])),
        key_interruptions=tuple(curated.get("interruptions", [])),
        key_board_breakers=tuple(curated.get("board_breakers", [])),
        graveyard_dependency=float(curated.get("graveyard_dependency", 0)),
        backrow_density=float(curated.get("backrow_density", 0)),
        spell_trap_density=float(curated.get("spell_trap_density", curated.get("backrow_density", 0))),
        monster_effect_density=float(curated.get("monster_effect_density", 0.8 if curated.get("summon_volume", 0) else 0.4)),
        summon_volume=float(curated.get("summon_volume", 0)),
        banish_dependency=float(curated.get("banish_dependency", 0)),
        search_dependency=float(curated.get("search_dependency", 0)),
        going_first_plan=tuple(curated.get("going_first_plan", [])),
        going_second_plan=tuple(curated.get("going_second_plan", [])),
        expected_endboard=tuple(curated.get("expected_endboard", [])),
        choke_points=tuple(curated.get("choke_points", [])),
        recommended_counters=tuple(curated.get("best_counters", [])),
        nearest_matchup=str(curated.get("matchup_category", "unknown_meta")),
        profile_source="curated",
        matched_curated_profile=str(curated.get("archetype", "")) or None,
        curated_notes=str(curated.get("notes", "")),
        deck_style=str(curated.get("deck_style", "")),
        best_counters=tuple(curated.get("best_counters", [])),
        weak_counters=tuple(curated.get("weak_counters", [])),
        side_in_recommendations=tuple(curated.get("side_in_recommendations", [])),
        side_out_priorities=tuple(curated.get("side_out_priorities", [])),
    )


def merge_curated_and_inferred_profile(curated: dict[str, Any] | None, inferred: OpponentProfile | None) -> OpponentProfile:
    if not curated and inferred:
        return inferred
    if curated and not inferred:
        return curated_to_opponent_profile(curated)
    if not curated or not inferred:
        return curated_to_opponent_profile({})

    curated_profile = curated_to_opponent_profile(curated)
    return OpponentProfile(
        name=f"{curated_profile.archetype} hybrid profile",
        archetype=curated_profile.archetype,
        known_cards=unique_tuple((*inferred.known_cards, *curated_profile.known_cards)),
        likely_engines=unique_tuple((*inferred.likely_engines, *curated_profile.likely_engines)),
        key_starters=unique_tuple((*curated_profile.key_starters, *inferred.key_starters)),
        key_extenders=unique_tuple((*curated_profile.key_extenders, *inferred.key_extenders)),
        key_interruptions=unique_tuple((*curated_profile.key_interruptions, *inferred.key_interruptions)),
        key_board_breakers=unique_tuple((*curated_profile.key_board_breakers, *inferred.key_board_breakers)),
        graveyard_dependency=weighted(curated_profile.graveyard_dependency, inferred.graveyard_dependency),
        backrow_density=weighted(curated_profile.backrow_density, inferred.backrow_density),
        spell_trap_density=weighted(curated_profile.spell_trap_density, inferred.spell_trap_density),
        monster_effect_density=weighted(curated_profile.monster_effect_density, inferred.monster_effect_density),
        summon_volume=weighted(curated_profile.summon_volume, inferred.summon_volume),
        banish_dependency=weighted(curated_profile.banish_dependency, inferred.banish_dependency),
        search_dependency=weighted(curated_profile.search_dependency, inferred.search_dependency),
        going_first_plan=curated_profile.going_first_plan or inferred.going_first_plan,
        going_second_plan=curated_profile.going_second_plan or inferred.going_second_plan,
        expected_endboard=unique_tuple((*curated_profile.expected_endboard, *inferred.expected_endboard)),
        choke_points=unique_tuple((*curated_profile.choke_points, *inferred.choke_points)),
        recommended_counters=unique_tuple((*curated_profile.recommended_counters, *inferred.recommended_counters)),
        nearest_matchup=curated_profile.nearest_matchup or inferred.nearest_matchup,
        profile_source="hybrid",
        matched_curated_profile=curated_profile.archetype,
        curated_notes=curated_profile.curated_notes,
        deck_style=curated_profile.deck_style,
        best_counters=curated_profile.best_counters,
        weak_counters=curated_profile.weak_counters,
        side_in_recommendations=curated_profile.side_in_recommendations,
        side_out_priorities=curated_profile.side_out_priorities,
    )


def profile_match_score(profile: dict[str, Any], card_names: list[str], joined: str) -> float:
    normalized_joined = normalize(joined)
    score = 0.0
    for alias in [profile.get("archetype", ""), *profile.get("aliases", [])]:
        alias_norm = normalize(alias)
        if alias_norm and alias_norm in normalized_joined:
            score += 2.0
    card_set = {normalize(name) for name in card_names}
    for field, weight in (("core_cards", 1.2), ("starters", 1.0), ("extenders", 0.8), ("interruptions", 0.4)):
        for card in profile.get(field, []):
            card_norm = normalize(card)
            if card_norm in card_set or any(card_norm and card_norm in normalize(name) for name in card_names):
                score += weight
    return score


def normalize(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def unique_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def weighted(curated_value: float, inferred_value: float) -> float:
    return round(max(0.0, min(1.0, curated_value * 0.7 + inferred_value * 0.3)), 4)
