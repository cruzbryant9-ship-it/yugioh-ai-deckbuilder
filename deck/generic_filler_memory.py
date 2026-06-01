from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update


GENERIC_FILLER_MEMORY_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "generic_filler_memory.json"
GENERIC_FILLER_MEMORY_FILENAME = "generic_filler_memory.json"
MIN_FILLER_MEMORY_USES = 3
MIN_FILLER_ARCHETYPE_BREADTH = 2
COMPLETION_BIAS_THRESHOLD = 0.5
CONCENTRATION_WARNING_THRESHOLD = 0.7


def generic_filler_memory_path() -> Path:
    return memory_file(GENERIC_FILLER_MEMORY_FILENAME)


def load_generic_filler_memory(archetype: str | None = None, mode: str | None = None) -> dict[str, Any]:
    payload = safe_load_json(generic_filler_memory_path(), empty_payload())
    if not isinstance(payload, dict):
        payload = empty_payload()
    payload = migrate_filler_memory(payload)
    if archetype is None or mode is None:
        return payload
    return payload.get("profiles", {}).get(str(archetype).casefold(), {}).get(str(mode), {})


def update_generic_filler_memory(
    archetype: str,
    mode: str,
    impact_reports: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return {}
    payload = safe_load_json(generic_filler_memory_path(), empty_payload())
    if not isinstance(payload, dict):
        payload = empty_payload()
    payload = migrate_filler_memory(payload)
    profiles = payload.setdefault("profiles", {})
    profile = profiles.setdefault(str(archetype).casefold(), {}).setdefault(str(mode), empty_profile())
    for report in impact_reports:
        record_impact(profile, str(archetype), report, provenance)
    profile["updated_at_utc"] = now_utc()
    profile["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["cross_archetype_index"] = build_cross_archetype_index(payload)
    payload["concentration_warnings"] = archetype_concentration_warnings(payload)
    payload["updated_at_utc"] = now_utc()
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_filler_memory_path(), payload)
    return profile


def record_impact(profile: dict[str, Any], archetype: str, report: dict[str, Any], provenance: dict[str, Any]) -> None:
    archetype_key = str(archetype).casefold()
    filler_cards = list(report.get("filler_cards", []) or [])
    classifications = report.get("impact_classification", {}) if isinstance(report.get("impact_classification"), dict) else {}
    score_delta = safe_float(report.get("attributed_score_delta", report.get("score_delta")))
    confidence_delta = safe_float(report.get("attributed_confidence_delta", report.get("confidence_delta")))
    relief = report.get("package_pressure_relieved", {}) if isinstance(report.get("package_pressure_relieved"), dict) else {}
    cards = profile.setdefault("fillers", {})
    for name in filler_cards:
        entry = cards.setdefault(name, empty_card_entry())
        entry.setdefault("archetype_observations", {})
        entry["archetype_observations"][archetype_key] = int(entry["archetype_observations"].get(archetype_key, 0) or 0) + 1
        classification = str(classifications.get(name) or "completion_only")
        entry["times_used"] = int(entry.get("times_used", 0) or 0) + 1
        if classification == "completion_only":
            entry["completion_only_count"] = int(entry.get("completion_only_count", 0) or 0) + 1
        elif classification == "performance_positive":
            entry["performance_positive_count"] = int(entry.get("performance_positive_count", 0) or 0) + 1
        elif classification in {"performance_negative", "risky"}:
            entry["performance_negative_count"] = int(entry.get("performance_negative_count", 0) or 0) + 1
        elif classification == "indeterminate":
            entry["indeterminate_count"] = int(entry.get("indeterminate_count", 0) or 0) + 1
        else:
            entry["performance_neutral_count"] = int(entry.get("performance_neutral_count", 0) or 0) + 1
        if report.get("attribution_shared"):
            entry["shared_attribution_count"] = int(entry.get("shared_attribution_count", 0) or 0) + 1
        else:
            entry["single_card_attribution_count"] = int(entry.get("single_card_attribution_count", 0) or 0) + 1
        update_average(entry, "average_attribution_confidence", safe_float(report.get("attribution_confidence", 1.0)))
        if report.get("legal_observation", True) and not report.get("blocked_card_violations"):
            entry["legal_observation_count"] = int(entry.get("legal_observation_count", 0) or 0) + 1
        else:
            entry["illegal_observation_count"] = int(entry.get("illegal_observation_count", 0) or 0) + 1
        update_average(entry, "average_score_delta", score_delta)
        update_average(entry, "average_confidence_delta", confidence_delta)
        pressure = entry.setdefault("package_pressure_relief", {})
        for package, amount in relief.items():
            pressure[package] = int(pressure.get(package, 0) or 0) + int(amount or 0)
        affected = set(entry.get("affected_archetypes", []) or [])
        affected.add(archetype_key)
        entry["affected_archetypes"] = sorted(affected)
        entry["archetype_breadth"] = len(entry["affected_archetypes"])
        entry["completion_bias_flag"] = completion_bias_flag(entry)
        entry["eligibility"] = filler_signal_status(entry, provenance=provenance)
        entry["last_observation_provenance"] = provenance
        entry["last_seen"] = now_utc()


def update_average(entry: dict[str, Any], key: str, value: float) -> None:
    total_key = f"{key}_total"
    count_key = f"{key}_count"
    entry[total_key] = safe_float(entry.get(total_key)) + value
    entry[count_key] = int(entry.get(count_key, 0) or 0) + 1
    entry[key] = round(entry[total_key] / max(1, entry[count_key]), 4)


def empty_payload() -> dict[str, Any]:
    return {"version": 1, "profiles": {}, "cross_archetype_index": {}, "concentration_warnings": [], "provenance_log": []}


def empty_profile() -> dict[str, Any]:
    return {"fillers": {}, "updated_at_utc": None, "last_update_provenance": {}}


def empty_card_entry() -> dict[str, Any]:
    return {
        "times_used": 0,
        "completion_only_count": 0,
        "performance_positive_count": 0,
        "performance_neutral_count": 0,
        "performance_negative_count": 0,
        "indeterminate_count": 0,
        "shared_attribution_count": 0,
        "single_card_attribution_count": 0,
        "average_attribution_confidence": 0.0,
        "legal_observation_count": 0,
        "illegal_observation_count": 0,
        "completion_bias_flag": False,
        "eligibility": {},
        "archetype_observations": {},
        "archetype_breadth": 0,
        "average_score_delta": 0.0,
        "average_confidence_delta": 0.0,
        "package_pressure_relief": {},
        "affected_archetypes": [],
        "last_seen": None,
    }


def migrate_filler_memory(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("version", 1)
    payload.setdefault("profiles", {})
    payload.setdefault("provenance_log", [])
    for archetype, modes in (payload.get("profiles", {}) or {}).items():
        if not isinstance(modes, dict):
            continue
        for _mode, profile in modes.items():
            if not isinstance(profile, dict):
                continue
            fillers = profile.setdefault("fillers", {})
            for _name, entry in list(fillers.items()):
                if not isinstance(entry, dict):
                    continue
                defaults = empty_card_entry()
                for key, value in defaults.items():
                    entry.setdefault(key, value)
                if not entry.get("archetype_observations"):
                    entry["archetype_observations"] = {str(archetype): int(entry.get("times_used", 0) or 0)}
                entry["archetype_observations"] = normalize_observations(entry.get("archetype_observations", {}))
                if not entry.get("affected_archetypes"):
                    entry["affected_archetypes"] = [str(archetype)]
                entry["affected_archetypes"] = sorted({str(name).casefold() for name in entry.get("affected_archetypes", []) or []})
                entry["archetype_breadth"] = len(entry.get("affected_archetypes", []) or [])
                if not entry.get("legal_observation_count") and int(entry.get("times_used", 0) or 0):
                    entry["legal_observation_count"] = int(entry.get("times_used", 0) or 0)
                entry["completion_bias_flag"] = completion_bias_flag(entry)
                entry["eligibility"] = filler_signal_status(entry, provenance=entry.get("last_observation_provenance", {}), require_cross_archetype=False)
    payload["cross_archetype_index"] = build_cross_archetype_index(payload)
    payload["concentration_warnings"] = archetype_concentration_warnings(payload)
    return payload


def build_cross_archetype_index(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate: dict[str, dict[str, Any]] = {}
    for archetype, modes in (payload.get("profiles", {}) or {}).items():
        if not isinstance(modes, dict):
            continue
        for mode, profile in modes.items():
            for name, entry in (profile.get("fillers", {}) or {}).items():
                target = aggregate.setdefault(name, empty_card_entry())
                target["times_used"] = int(target.get("times_used", 0) or 0) + int(entry.get("times_used", 0) or 0)
                target["completion_only_count"] += int(entry.get("completion_only_count", 0) or 0)
                target["performance_positive_count"] += int(entry.get("performance_positive_count", 0) or 0)
                target["performance_neutral_count"] += int(entry.get("performance_neutral_count", 0) or 0)
                target["performance_negative_count"] += int(entry.get("performance_negative_count", 0) or 0)
                target["indeterminate_count"] += int(entry.get("indeterminate_count", 0) or 0)
                target["shared_attribution_count"] += int(entry.get("shared_attribution_count", 0) or 0)
                target["single_card_attribution_count"] += int(entry.get("single_card_attribution_count", 0) or 0)
                target["legal_observation_count"] += int(entry.get("legal_observation_count", 0) or 0)
                target["illegal_observation_count"] += int(entry.get("illegal_observation_count", 0) or 0)
                observations = target.setdefault("archetype_observations", {})
                archetype_key = str(archetype).casefold()
                observations[archetype_key] = int(observations.get(archetype_key, 0) or 0) + int(entry.get("times_used", 0) or 0)
                target["affected_archetypes"] = sorted(set(target.get("affected_archetypes", []) or []) | {archetype_key})
                target["archetype_breadth"] = len(target["affected_archetypes"])
                update_weighted_average(target, entry, "average_score_delta")
                update_weighted_average(target, entry, "average_confidence_delta")
                update_weighted_average(target, entry, "average_attribution_confidence")
    return {
        name: finalize_cross_entry(entry)
        for name, entry in sorted(aggregate.items())
        if is_filler_signal_eligible(entry, require_cross_archetype=True)
    }


def finalize_cross_entry(entry: dict[str, Any]) -> dict[str, Any]:
    entry["completion_bias_flag"] = completion_bias_flag(entry)
    entry["eligibility"] = filler_signal_status(entry, require_cross_archetype=True)
    return entry


def update_weighted_average(target: dict[str, Any], entry: dict[str, Any], key: str) -> None:
    count = int(entry.get(f"{key}_count", entry.get("times_used", 0)) or 0)
    total = safe_float(entry.get(f"{key}_total", safe_float(entry.get(key)) * count))
    target[f"{key}_total"] = safe_float(target.get(f"{key}_total")) + total
    target[f"{key}_count"] = int(target.get(f"{key}_count", 0) or 0) + count
    target[key] = round(target[f"{key}_total"] / max(1, target[f"{key}_count"]), 4)


def is_filler_signal_eligible(
    entry: dict[str, Any],
    *,
    min_uses: int = MIN_FILLER_MEMORY_USES,
    min_archetype_breadth: int = MIN_FILLER_ARCHETYPE_BREADTH,
    provenance: dict[str, Any] | None = None,
    require_cross_archetype: bool = True,
) -> bool:
    return filler_signal_status(
        entry,
        min_uses=min_uses,
        min_archetype_breadth=min_archetype_breadth,
        provenance=provenance,
        require_cross_archetype=require_cross_archetype,
    ).get("eligible", False)


def filler_signal_status(
    entry: dict[str, Any],
    *,
    min_uses: int = MIN_FILLER_MEMORY_USES,
    min_archetype_breadth: int = MIN_FILLER_ARCHETYPE_BREADTH,
    provenance: dict[str, Any] | None = None,
    require_cross_archetype: bool = True,
) -> dict[str, Any]:
    times_used = int(entry.get("times_used", 0) or 0)
    breadth = int(entry.get("archetype_breadth", len(entry.get("affected_archetypes", []) or [])) or 0)
    legal = int(entry.get("legal_observation_count", 0) or 0)
    completion_biased = completion_bias_flag(entry)
    provenance = provenance if isinstance(provenance, dict) else entry.get("last_observation_provenance", {})
    provenance_valid = not bool((provenance or {}).get("validator_generated"))
    failures = []
    if times_used < min_uses:
        failures.append("min_uses")
    if require_cross_archetype and breadth < min_archetype_breadth:
        failures.append("min_archetype_breadth")
    if legal < times_used:
        failures.append("legal_observations_only")
    if not provenance_valid:
        failures.append("provenance_valid")
    if completion_biased:
        failures.append("completion_bias_flag")
    return {
        "eligible": not failures,
        "failures": failures,
        "times_used": times_used,
        "archetype_breadth": breadth,
        "legal_observation_count": legal,
        "completion_bias_flag": completion_biased,
        "provenance_valid": provenance_valid,
    }


def completion_bias_flag(entry: dict[str, Any]) -> bool:
    times_used = int(entry.get("times_used", 0) or 0)
    if not times_used:
        return False
    return (int(entry.get("completion_only_count", 0) or 0) / times_used) >= COMPLETION_BIAS_THRESHOLD


def archetype_concentration_warnings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, int]] = {}
    for archetype, modes in (payload.get("profiles", {}) or {}).items():
        for _mode, profile in (modes or {}).items():
            for name, entry in (profile.get("fillers", {}) or {}).items():
                bucket = aggregate.setdefault(name, {})
                archetype_key = str(archetype).casefold()
                bucket[archetype_key] = bucket.get(archetype_key, 0) + int(entry.get("times_used", 0) or 0)
    for name, observations in aggregate.items():
        total = sum(observations.values())
        if total <= 0:
            continue
        dominant, count = max(observations.items(), key=lambda item: item[1])
        share = count / total
        if share > CONCENTRATION_WARNING_THRESHOLD:
            warnings.append(
                {
                    "card": name,
                    "dominant_archetype": dominant,
                    "single_archetype_share": round(share, 4),
                    "total_observations": total,
                }
            )
    return warnings


def normalize_observations(observations: dict[str, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for name, amount in (observations or {}).items():
        key = str(name).casefold()
        normalized[key] = int(normalized.get(key, 0) or 0) + int(amount or 0)
    return normalized


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
