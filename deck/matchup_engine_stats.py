from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.curated_opponent_memory import curated_engine_preference, load_curated_opponent_memory
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update

MATCHUP_ENGINE_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "matchup_engine_stats.json"
MATCHUP_ENGINE_STATS_FILENAME = "matchup_engine_stats.json"
MATCHUP_ENGINE_WEIGHT_CAP = 0.08


def matchup_engine_stats_path() -> Path:
    return memory_file(MATCHUP_ENGINE_STATS_FILENAME)


def load_matchup_engine_stats(archetype: str, mode: str) -> dict[str, Any]:
    payload = safe_load_json(matchup_engine_stats_path(), {})
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    archetype_profiles = profiles.get(archetype.casefold())
    if not isinstance(archetype_profiles, dict):
        return {}
    profile = archetype_profiles.get(mode)
    return profile if isinstance(profile, dict) else {}


def save_matchup_engine_stats(archetype: str, mode: str, profile: dict[str, Any], provenance: dict[str, Any] | None = None) -> None:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return
    payload = safe_load_json(matchup_engine_stats_path(), {})
    if not isinstance(payload, dict):
        payload = {}
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    archetype_profiles[mode] = profile
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(matchup_engine_stats_path(), payload)


def recommended_variant(profile: dict[str, Any], matchup: str | None, going: str | None) -> str | None:
    if not profile:
        return None
    matchup_key = str(matchup or "unknown_meta")
    going_key = str(going or "both")
    by_matchup = profile.get("recommended_engine_by_matchup", {})
    if isinstance(by_matchup, dict):
        matchup_entry = by_matchup.get(matchup_key)
        if isinstance(matchup_entry, dict):
            going_choice = matchup_entry.get(going_key) or matchup_entry.get("both")
            if isinstance(going_choice, str):
                return going_choice
        if isinstance(matchup_entry, str):
            return matchup_entry
    overall = profile.get("rankings", {}).get("best_overall_engine") if isinstance(profile.get("rankings"), dict) else None
    return overall if isinstance(overall, str) else None


def recommended_variant_with_curated_memory(
    archetype: str,
    mode: str,
    profile: dict[str, Any],
    matchup: Any,
    going: str | None,
) -> str | None:
    curated_memory = load_curated_opponent_memory(archetype, mode, matchup, str(going or "both"))
    curated_choice = curated_engine_preference(curated_memory)
    return curated_choice or recommended_variant(profile, getattr(matchup, "name", matchup), going)


def matchup_engine_weight(card_engines: set[str], variant: str | None) -> float:
    if not variant or not card_engines:
        return 1.0
    target_terms = {
        "pure": {"Blue-Eyes core"},
        "ritual": {"Blue-Eyes ritual"},
        "chaos": {"Chaos"},
        "bystial": {"Bystial"},
        "horus": {"Horus"},
        "branded": {"Branded"},
        "handtrap_heavy": {"handtrap package"},
        "board_breaker_heavy": {"board breaker package"},
    }.get(variant, set())
    if not target_terms:
        return 1.0
    if card_engines & target_terms:
        return 1.0 + MATCHUP_ENGINE_WEIGHT_CAP
    if variant != "pure" and "Blue-Eyes core" in card_engines:
        return 1.0 + MATCHUP_ENGINE_WEIGHT_CAP / 2
    return 1.0
