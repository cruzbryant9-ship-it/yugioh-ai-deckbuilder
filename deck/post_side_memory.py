from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update

POST_SIDE_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "post_side_stats.json"
POST_SIDE_STATS_FILENAME = "post_side_stats.json"
MEMORY_WEIGHT_CAP = 3.0


def post_side_stats_path() -> Path:
    return memory_file(POST_SIDE_STATS_FILENAME)


def load_post_side_memory(archetype: str, mode: str, matchup: str, going: str) -> dict[str, Any]:
    payload = load_payload()
    profile = (
        payload.get("profiles", {})
        .get(archetype.casefold(), {})
        .get(mode, {})
        .get(matchup, {})
        .get(going, {})
    )
    return profile if isinstance(profile, dict) else {}


def update_post_side_memory(
    archetype: str,
    mode: str,
    matchup: str,
    going: str,
    results: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return {}
    payload = load_payload()
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    mode_profiles = archetype_profiles.setdefault(mode, {})
    matchup_profiles = mode_profiles.setdefault(matchup, {})
    profile = matchup_profiles.setdefault(going, empty_profile())

    for result in results:
        if not result.get("post_side_valid"):
            for card in result.get("side_cards_used", []):
                profile["rejected_side_cards"][card] = profile["rejected_side_cards"].get(card, 0) + 1
            continue
        delta = safe_float(result.get("post_side_delta"))
        side_in = [str(card) for card in result.get("side_cards_used", [])]
        side_out = [str(card) for card in result.get("cards_sided_out", [])]
        for card in side_in:
            profile["side_in_card_counts"][card] = profile["side_in_card_counts"].get(card, 0) + 1
            add_delta(profile.setdefault("side_in_delta_totals", {}), profile.setdefault("side_in_delta_counts", {}), card, delta)
        for card in side_out:
            profile["side_out_card_counts"][card] = profile["side_out_card_counts"].get(card, 0) + 1
            add_delta(profile.setdefault("side_out_delta_totals", {}), profile.setdefault("side_out_delta_counts", {}), card, delta)
        pattern = " | ".join(side_in)
        out_pattern = " | ".join(side_out)
        full_pattern = f"IN: {pattern} || OUT: {out_pattern}"
        add_pattern(profile.setdefault("best_side_in_patterns", {}), pattern, delta)
        add_pattern(profile.setdefault("best_side_out_patterns", {}), out_pattern, delta)
        add_pattern(profile.setdefault("best_full_side_plans", {}), full_pattern, delta)
        if delta < 0:
            for card in side_in + side_out:
                profile["cards_frequently_present_in_bad_side_plans"][card] = profile["cards_frequently_present_in_bad_side_plans"].get(card, 0) + 1
        profile.setdefault("valid_candidate_rate_history", []).append(safe_float(result.get("valid_candidate_rate")))
        profile.setdefault("post_side_score_history", []).append(safe_float(result.get("post_side_score")))
        profile.setdefault("post_side_delta_history", []).append(delta)

    normalize_profile(profile)
    profile["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    profile["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(post_side_stats_path(), payload)
    return profile


def memory_card_adjustment(memory: dict[str, Any], card_name: str, role: str, card: dict[str, Any] | None = None) -> float:
    if card is not None and get_card_limit(card) <= 0:
        return 0.0
    if not memory:
        return 0.0
    averages = memory.get("average_post_side_delta_by_card", {})
    role_values = averages.get(role, {}) if isinstance(averages, dict) else {}
    value = safe_float(role_values.get(card_name)) if isinstance(role_values, dict) else 0.0
    bad_counts = memory.get("cards_frequently_present_in_bad_side_plans", {})
    bad_penalty = min(1.0, safe_float(bad_counts.get(card_name)) * 0.15) if isinstance(bad_counts, dict) else 0.0
    return max(-MEMORY_WEIGHT_CAP, min(MEMORY_WEIGHT_CAP, value * 0.4 - bad_penalty))


def memory_summary(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_side_in_cards": top_items(memory.get("side_in_card_counts", {})),
        "top_side_out_cards": top_items(memory.get("side_out_card_counts", {})),
        "best_post_side_pattern": top_pattern(memory.get("best_full_side_plans", {})),
        "average_post_side_delta": average(memory.get("post_side_delta_history", [])),
    }


def empty_profile() -> dict[str, Any]:
    return {
        "side_in_card_counts": {},
        "side_out_card_counts": {},
        "side_in_delta_totals": {},
        "side_in_delta_counts": {},
        "side_out_delta_totals": {},
        "side_out_delta_counts": {},
        "average_post_side_delta_by_card": {"side_in": {}, "side_out": {}},
        "best_side_in_patterns": {},
        "best_side_out_patterns": {},
        "best_full_side_plans": {},
        "valid_candidate_rate_history": [],
        "post_side_score_history": [],
        "post_side_delta_history": [],
        "rejected_side_cards": {},
        "cards_frequently_present_in_bad_side_plans": {},
    }


def load_payload() -> dict[str, Any]:
    payload = safe_load_json(post_side_stats_path(), {"version": 1, "profiles": {}})
    return payload if isinstance(payload, dict) else {"version": 1, "profiles": {}}


def add_delta(totals: dict[str, float], counts: dict[str, int], card: str, delta: float) -> None:
    totals[card] = safe_float(totals.get(card)) + delta
    counts[card] = int(counts.get(card, 0) or 0) + 1


def add_pattern(patterns: dict[str, dict[str, float]], pattern: str, delta: float) -> None:
    if not pattern:
        return
    entry = patterns.setdefault(pattern, {"count": 0, "delta_total": 0.0, "best_delta": -999.0})
    entry["count"] = int(entry.get("count", 0) or 0) + 1
    entry["delta_total"] = safe_float(entry.get("delta_total")) + delta
    entry["best_delta"] = max(safe_float(entry.get("best_delta")), delta)


def normalize_profile(profile: dict[str, Any]) -> None:
    side_in = profile.setdefault("average_post_side_delta_by_card", {}).setdefault("side_in", {})
    side_out = profile.setdefault("average_post_side_delta_by_card", {}).setdefault("side_out", {})
    for card, total in profile.get("side_in_delta_totals", {}).items():
        count = max(1, int(profile.get("side_in_delta_counts", {}).get(card, 1) or 1))
        side_in[card] = round(safe_float(total) / count, 4)
    for card, total in profile.get("side_out_delta_totals", {}).items():
        count = max(1, int(profile.get("side_out_delta_counts", {}).get(card, 1) or 1))
        side_out[card] = round(safe_float(total) / count, 4)
    for key in ("valid_candidate_rate_history", "post_side_score_history", "post_side_delta_history"):
        profile[key] = list(profile.get(key, []))[-200:]


def top_items(values: Any, limit: int = 10) -> list[tuple[str, int]]:
    if not isinstance(values, dict):
        return []
    return Counter({str(key): int(value or 0) for key, value in values.items()}).most_common(limit)


def top_pattern(values: Any) -> str | None:
    if not isinstance(values, dict) or not values:
        return None
    return max(values, key=lambda key: (safe_float(values[key].get("best_delta")), int(values[key].get("count", 0) or 0)))


def average(values: Any) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return round(sum(safe_float(value) for value in values) / len(values), 4)


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
