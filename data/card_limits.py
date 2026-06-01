from __future__ import annotations

from pathlib import Path
from typing import Any

from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json

# Keep blocked cards in this single map only. A value of 0 means the card is
# completely unavailable to generated decks and memory statistics.
CUSTOM_CARD_LIMITS: dict[str, int] = {
    "Pot of Greed": 0,
    "Protector with Eyes of Blue": 0,
    "Strength in Unity": 0,
}


def normalize_card_name(card_name: str) -> str:
    return card_name.strip().casefold()


CUSTOM_CARD_LIMITS_NORMALIZED = {
    normalize_card_name(card_name): limit for card_name, limit in CUSTOM_CARD_LIMITS.items()
}


def get_custom_card_limit(card_name: str) -> int | None:
    return CUSTOM_CARD_LIMITS_NORMALIZED.get(normalize_card_name(card_name))


def get_blocked_card_names() -> set[str]:
    return {
        normalize_card_name(card_name)
        for card_name, limit in CUSTOM_CARD_LIMITS.items()
        if limit == 0
    }


def cleanup_meta_stats(meta_stats_path: str | Path = "meta_stats.json") -> int:
    return cleanup_blocked_card_memory(meta_stats_path)


def cleanup_learned_card_stats(
    learned_stats_path: str | Path = "SystemAIYugioh/data/deck_profiles/learned_card_stats.json",
) -> int:
    return cleanup_blocked_card_memory(learned_stats_path)


def cleanup_learning_tuning(
    tuning_path: str | Path = "SystemAIYugioh/data/deck_profiles/learning_tuning.json",
) -> int:
    return cleanup_blocked_card_memory(tuning_path)


def cleanup_learned_engine_stats(
    engine_stats_path: str | Path = "SystemAIYugioh/data/deck_profiles/learned_engine_stats.json",
) -> int:
    return cleanup_blocked_card_memory(engine_stats_path)


def startup_safety_cleanup() -> int:
    removed = cleanup_meta_stats()
    removed += cleanup_learned_card_stats()
    removed += cleanup_learning_tuning()
    removed += cleanup_learned_engine_stats()
    return removed


def cleanup_blocked_card_memory(memory_path: str | Path) -> int:
    path = Path(memory_path)
    if not path.exists():
        return 0

    stats = safe_load_json(path, None)
    if stats is None:
        return 0

    blocked = get_blocked_card_names()
    cleaned, removed = remove_blocked_from_stats(stats, blocked)

    if removed:
        atomic_write_json(path, cleaned)

    return removed


def remove_blocked_from_stats(stats: Any, blocked_names: set[str]) -> tuple[Any, int]:
    if isinstance(stats, dict):
        removed = 0
        cleaned: dict[str, Any] = {}
        for key, value in stats.items():
            if normalize_card_name(str(key)) in blocked_names:
                removed += 1
                continue
            cleaned_value, nested_removed = remove_blocked_from_stats(value, blocked_names)
            removed += nested_removed
            cleaned[key] = cleaned_value
        return cleaned, removed

    if isinstance(stats, list):
        cleaned_list = []
        removed = 0
        for item in stats:
            if isinstance(item, str) and normalize_card_name(item) in blocked_names:
                removed += 1
                continue
            card_name = item.get("name") if isinstance(item, dict) else None
            if card_name and normalize_card_name(str(card_name)) in blocked_names:
                removed += 1
                continue
            cleaned_item, nested_removed = remove_blocked_from_stats(item, blocked_names)
            removed += nested_removed
            cleaned_list.append(cleaned_item)
        return cleaned_list, removed

    return stats, 0
