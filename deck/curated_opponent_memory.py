from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.opponent_profiles import OpponentProfile
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update

CURATED_OPPONENT_MEMORY_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "curated_opponent_memory.json"
CURATED_OPPONENT_MEMORY_FILENAME = "curated_opponent_memory.json"
CURATED_MEMORY_WEIGHT_CAP = 2.0


def curated_opponent_name(opponent: str | OpponentProfile | None) -> str | None:
    if isinstance(opponent, OpponentProfile):
        if opponent.matched_curated_profile:
            return opponent.matched_curated_profile
        if opponent.profile_source == "curated":
            return opponent.archetype
        if opponent.profile_source == "hybrid":
            return opponent.archetype
        return None
    value = str(opponent or "").strip()
    if value.endswith(" curated profile"):
        return value.replace(" curated profile", "").strip()
    return None


def curated_opponent_memory_path() -> Path:
    return memory_file(CURATED_OPPONENT_MEMORY_FILENAME)


def load_curated_opponent_memory(archetype: str, mode: str, opponent: str | OpponentProfile | None, going: str) -> dict[str, Any]:
    opponent_name = curated_opponent_name(opponent)
    if not opponent_name:
        return {}
    payload = load_payload()
    profile = (
        payload.get("profiles", {})
        .get(archetype.casefold(), {})
        .get(mode, {})
        .get(opponent_name, {})
        .get(going, {})
    )
    return profile if isinstance(profile, dict) else {}


def update_curated_opponent_memory(
    archetype: str,
    mode: str,
    opponent: str | OpponentProfile,
    going: str,
    results: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return {}
    opponent_name = curated_opponent_name(opponent)
    if not opponent_name:
        return {}

    payload = load_payload()
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    mode_profiles = archetype_profiles.setdefault(mode, {})
    opponent_profiles = mode_profiles.setdefault(opponent_name, {})
    profile = opponent_profiles.setdefault(going, empty_profile())
    ensure_choke_fields(profile)

    for result in results:
        if result.get("blocked_card_violations") or result.get("blocked_card_violations_after_siding"):
            profile["blocked_rejection_count"] = int(profile.get("blocked_rejection_count", 0) or 0) + 1
            continue
        delta = safe_float(result.get("post_side_delta"))
        valid = bool(result.get("post_side_valid", True))
        if not valid:
            profile.setdefault("post_side_validity_history", []).append(0.0)
            continue

        engine = str(result.get("engine_variant") or result.get("matchup_recommended_engine_variant") or "unknown")
        score = safe_float(result.get("post_side_score") or result.get("final_score"))
        side_in = [str(card) for card in result.get("side_cards_used", []) or result.get("best_side_in", [])]
        side_out = [str(card) for card in result.get("cards_sided_out", []) or result.get("best_side_out", [])]

        profile["best_engine_variants"][engine] = int(profile["best_engine_variants"].get(engine, 0) or 0) + 1
        add_delta(profile["engine_score_totals"], profile["engine_score_counts"], engine, score)
        add_delta(profile["engine_delta_totals"], profile["engine_delta_counts"], engine, delta)
        for card in side_in:
            profile["side_in_card_success_counts"][card] = int(profile["side_in_card_success_counts"].get(card, 0) or 0) + 1
            add_delta(profile["side_in_delta_totals"], profile["side_in_delta_counts"], card, delta)
            add_delta(profile["side_card_choke_totals"], profile["side_card_choke_counts"], card, safe_float(result.get("choke_stop_rate")))
        for card in side_out:
            profile["side_out_card_success_counts"][card] = int(profile["side_out_card_success_counts"].get(card, 0) or 0) + 1
            add_delta(profile["side_out_delta_totals"], profile["side_out_delta_counts"], card, delta)

        full_pattern = f"ENGINE: {engine} || IN: {' | '.join(side_in)} || OUT: {' | '.join(side_out)}"
        if delta >= 0:
            add_pattern(profile["best_full_side_plans"], full_pattern, delta)
        else:
            add_pattern(profile["worst_side_plans"], full_pattern, delta)

        append_limited(profile["interruption_vulnerability_trends"], safe_float(result.get("average_interruption_risk")))
        append_limited(profile["resilience_score_trends"], safe_float(result.get("resilience_score")))
        append_limited(profile["matchup_coverage_trends"], safe_float(result.get("matchup_coverage_score")))
        append_limited(profile["post_side_validity_history"], 1.0)
        append_limited(profile["post_side_delta_history"], delta)
        append_limited(profile["choke_stop_rate_history"], safe_float(result.get("choke_stop_rate")))
        append_limited(profile["opponent_recovery_rate_history"], safe_float(result.get("opponent_recovery_rate")))
        append_limited(profile["timing_precision_history"], safe_float(result.get("timing_precision_score")))
        append_limited(profile["pivot_risk_history"], safe_float(result.get("pivot_risk_score")))
        for window in result.get("choke_report", {}).get("best_timing_windows", []) if isinstance(result.get("choke_report"), dict) else []:
            profile["best_interruption_timing"][str(window)] = int(profile["best_interruption_timing"].get(str(window), 0) or 0) + 1
        for window in result.get("choke_report", {}).get("bad_timing_windows", []) if isinstance(result.get("choke_report"), dict) else []:
            profile["poor_timing_history"][str(window)] = int(profile["poor_timing_history"].get(str(window), 0) or 0) + 1
        for card in result.get("choke_report", {}).get("recommended_interruptions", []) if isinstance(result.get("choke_report"), dict) else []:
            profile["cards_requiring_precise_timing"][str(card)] = int(profile["cards_requiring_precise_timing"].get(str(card), 0) or 0) + 1
        for card in result.get("choke_report", {}).get("best_interruptions", [])[:3] if isinstance(result.get("choke_report"), dict) else []:
            profile["broadly_safe_interruption_cards"][str(card)] = int(profile["broadly_safe_interruption_cards"].get(str(card), 0) or 0) + 1
        for poor in result.get("choke_report", {}).get("poor_interruptions", []) if isinstance(result.get("choke_report"), dict) else []:
            profile["poor_interruption_history"][str(poor)] = int(profile["poor_interruption_history"].get(str(poor), 0) or 0) + 1
        package = " | ".join(result.get("choke_report", {}).get("recommended_interruptions", [])[:6]) if isinstance(result.get("choke_report"), dict) else ""
        if package:
            profile["best_interruption_packages"][package] = int(profile["best_interruption_packages"].get(package, 0) or 0) + 1

    normalize_profile(profile)
    profile["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    profile["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(curated_opponent_memory_path(), payload)
    return profile


def curated_memory_card_adjustment(memory: dict[str, Any], card_name: str, role: str, card: dict[str, Any] | None = None) -> float:
    if card is not None and get_card_limit(card) <= 0:
        return 0.0
    if not memory:
        return 0.0
    averages = memory.get("average_post_side_delta_by_card", {})
    role_values = averages.get(role, {}) if isinstance(averages, dict) else {}
    value = safe_float(role_values.get(card_name)) if isinstance(role_values, dict) else 0.0
    return max(-CURATED_MEMORY_WEIGHT_CAP, min(CURATED_MEMORY_WEIGHT_CAP, value * 0.35))


def curated_engine_preference(memory: dict[str, Any]) -> str | None:
    scores = memory.get("average_score_by_engine", {})
    deltas = memory.get("post_side_delta_by_engine", {})
    if not isinstance(scores, dict) or not scores:
        counts = memory.get("best_engine_variants", {})
        return Counter(counts).most_common(1)[0][0] if isinstance(counts, dict) and counts else None
    return max(scores, key=lambda engine: safe_float(scores.get(engine)) + safe_float(deltas.get(engine)) * 0.5)


def curated_memory_summary(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "best_engine": curated_engine_preference(memory),
        "top_side_ins": top_items(memory.get("side_in_card_success_counts", {})),
        "top_side_outs": top_items(memory.get("side_out_card_success_counts", {})),
        "best_full_side_plan": top_pattern(memory.get("best_full_side_plans", {}), best=True),
        "average_post_side_delta": average(memory.get("post_side_delta_history", [])),
        "post_side_valid_rate": average(memory.get("post_side_validity_history", [])),
        "top_choke_side_cards": top_items(memory.get("side_card_choke_effectiveness", {})),
        "best_interruption_packages": top_items(memory.get("best_interruption_packages", {})),
        "best_interruption_timing": top_items(memory.get("best_interruption_timing", {})),
        "poor_timing_history": top_items(memory.get("poor_timing_history", {})),
    }


def empty_profile() -> dict[str, Any]:
    return {
        "best_engine_variants": {},
        "engine_score_totals": {},
        "engine_score_counts": {},
        "engine_delta_totals": {},
        "engine_delta_counts": {},
        "average_score_by_engine": {},
        "post_side_delta_by_engine": {},
        "side_in_card_success_counts": {},
        "side_in_delta_totals": {},
        "side_in_delta_counts": {},
        "side_in_card_average_post_side_delta": {},
        "side_out_card_success_counts": {},
        "side_out_delta_totals": {},
        "side_out_delta_counts": {},
        "side_out_card_average_post_side_delta": {},
        "average_post_side_delta_by_card": {"side_in": {}, "side_out": {}},
        "best_full_side_plans": {},
        "worst_side_plans": {},
        "interruption_vulnerability_trends": [],
        "resilience_score_trends": [],
        "matchup_coverage_trends": [],
        "post_side_validity_history": [],
        "post_side_delta_history": [],
        "choke_stop_rate_history": [],
        "opponent_recovery_rate_history": [],
        "side_card_choke_totals": {},
        "side_card_choke_counts": {},
        "side_card_choke_effectiveness": {},
        "poor_interruption_history": {},
        "best_interruption_packages": {},
        "timing_precision_history": [],
        "pivot_risk_history": [],
        "best_interruption_timing": {},
        "poor_timing_history": {},
        "cards_requiring_precise_timing": {},
        "broadly_safe_interruption_cards": {},
        "blocked_rejection_count": 0,
    }


def ensure_choke_fields(profile: dict[str, Any]) -> None:
    defaults = empty_profile()
    for key, value in defaults.items():
        if key not in profile:
            profile[key] = value.copy() if isinstance(value, dict) else list(value) if isinstance(value, list) else value
    profile.setdefault("average_post_side_delta_by_card", {}).setdefault("side_in", {})
    profile.setdefault("average_post_side_delta_by_card", {}).setdefault("side_out", {})


def load_payload() -> dict[str, Any]:
    payload = safe_load_json(curated_opponent_memory_path(), {"version": 1, "profiles": {}})
    return payload if isinstance(payload, dict) else {"version": 1, "profiles": {}}


def add_delta(totals: dict[str, float], counts: dict[str, int], key: str, value: float) -> None:
    totals[key] = safe_float(totals.get(key)) + value
    counts[key] = int(counts.get(key, 0) or 0) + 1


def add_pattern(patterns: dict[str, dict[str, float]], pattern: str, delta: float) -> None:
    if not pattern:
        return
    entry = patterns.setdefault(pattern, {"count": 0, "delta_total": 0.0, "best_delta": -999.0, "worst_delta": 999.0})
    entry["count"] = int(entry.get("count", 0) or 0) + 1
    entry["delta_total"] = safe_float(entry.get("delta_total")) + delta
    entry["best_delta"] = max(safe_float(entry.get("best_delta")), delta)
    entry["worst_delta"] = min(safe_float(entry.get("worst_delta")), delta)


def normalize_profile(profile: dict[str, Any]) -> None:
    for engine, total in profile.get("engine_score_totals", {}).items():
        count = max(1, int(profile.get("engine_score_counts", {}).get(engine, 1) or 1))
        profile["average_score_by_engine"][engine] = round(safe_float(total) / count, 4)
    for engine, total in profile.get("engine_delta_totals", {}).items():
        count = max(1, int(profile.get("engine_delta_counts", {}).get(engine, 1) or 1))
        profile["post_side_delta_by_engine"][engine] = round(safe_float(total) / count, 4)
    side_in = profile["average_post_side_delta_by_card"]["side_in"]
    side_out = profile["average_post_side_delta_by_card"]["side_out"]
    for card, total in profile.get("side_in_delta_totals", {}).items():
        count = max(1, int(profile.get("side_in_delta_counts", {}).get(card, 1) or 1))
        value = round(safe_float(total) / count, 4)
        side_in[card] = value
        profile["side_in_card_average_post_side_delta"][card] = value
    for card, total in profile.get("side_out_delta_totals", {}).items():
        count = max(1, int(profile.get("side_out_delta_counts", {}).get(card, 1) or 1))
        value = round(safe_float(total) / count, 4)
        side_out[card] = value
        profile["side_out_card_average_post_side_delta"][card] = value
    for card, total in profile.get("side_card_choke_totals", {}).items():
        count = max(1, int(profile.get("side_card_choke_counts", {}).get(card, 1) or 1))
        profile["side_card_choke_effectiveness"][card] = round(safe_float(total) / count, 4)
    for key in ("interruption_vulnerability_trends", "resilience_score_trends", "matchup_coverage_trends", "post_side_validity_history", "post_side_delta_history", "choke_stop_rate_history", "opponent_recovery_rate_history", "timing_precision_history", "pivot_risk_history"):
        profile[key] = list(profile.get(key, []))[-200:]


def append_limited(values: list[float], value: float) -> None:
    values.append(round(value, 4))
    del values[:-200]


def top_items(values: Any, limit: int = 10) -> list[tuple[str, int]]:
    if not isinstance(values, dict):
        return []
    return Counter({str(key): int(value or 0) for key, value in values.items()}).most_common(limit)


def top_pattern(values: Any, best: bool) -> str | None:
    if not isinstance(values, dict) or not values:
        return None
    if best:
        return max(values, key=lambda key: (safe_float(values[key].get("best_delta")), int(values[key].get("count", 0) or 0)))
    return min(values, key=lambda key: (safe_float(values[key].get("worst_delta")), -int(values[key].get("count", 0) or 0)))


def average(values: Any) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return round(sum(safe_float(value) for value in values) / len(values), 4)


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
