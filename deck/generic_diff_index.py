from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.rejection_classification import harmful_learning_eligible
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import (
    append_provenance_entry,
    is_isolated_memory_root,
    is_validator_generated,
    memory_file,
    normalize_provenance,
    result_provenance,
    should_skip_production_update,
)

GENERIC_DIFF_INDEX_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "generic_diff_index.json"
GENERIC_DIFF_INDEX_FILENAME = "generic_diff_index.json"
GENERIC_DIFF_INDEX_SCRUB_REPORT_FILENAME = "generic_diff_index_scrub_report.json"
MIN_ADVISORY_SUPPORT = 3
MAX_SINGLE_MOVEMENT_SIGNAL = 0.03
KNOWN_PROBE_TERMS = (
    "index probe",
    "card probe",
    "warning probe",
    "package probe",
    "risk probe",
    "isolation probe",
    "provenance probe",
    "production skip probe",
    "helpful add",
    "harmful add",
    "helpful remove",
    "harmful remove",
    "isolated helpful",
    "isolated harmful",
    "illegal harmful probe",
)


def build_cross_archetype_diff_index(benchmark_results: list[dict[str, Any]]) -> dict[str, Any]:
    index = empty_index()
    for result in benchmark_results:
        archetype = str(result.get("archetype", "unknown"))
        archetype_entry = index["archetype_patterns"].setdefault(archetype, empty_archetype_pattern())
        for row in accepted_rows(result):
            record_replay(index, archetype_entry, archetype, row, helpful=True)
        for row in rejected_rows(result):
            record_replay(index, archetype_entry, archetype, row, helpful=False)
        for action in result.get("normal_repair_actions", []) or []:
            bump_simple(index["recurring_repair_actions"], str(action), archetype)
        for action in result.get("tuned_repair_actions", []) or []:
            bump_simple(index["recurring_repair_actions"], str(action), archetype)
    finalize_index(index)
    return index


def generic_diff_index_path() -> Path:
    return memory_file(GENERIC_DIFF_INDEX_FILENAME)


def generic_diff_index_scrub_report_path() -> Path:
    return memory_file(GENERIC_DIFF_INDEX_SCRUB_REPORT_FILENAME)


def scrub_diff_index_memory(provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance, source="manual")
    index = load_generic_diff_index()
    scrubbed = empty_index()
    quarantine = empty_index()
    stats = {"removed_entries": 0, "quarantined_archetypes": 0, "quarantined_provenance_entries": 0}

    scrubbed["helpful_cards"] = scrub_card_group(index.get("helpful_cards", {}), quarantine["helpful_cards"], stats)
    scrubbed["harmful_cards"] = scrub_card_group(index.get("harmful_cards", {}), quarantine["harmful_cards"], stats)
    scrubbed["helpful_package_movements"] = scrub_package_group(index.get("helpful_package_movements", {}), quarantine["helpful_package_movements"], stats)
    scrubbed["harmful_package_movements"] = scrub_package_group(index.get("harmful_package_movements", {}), quarantine["harmful_package_movements"], stats)
    scrubbed["recurring_risk_flags"] = scrub_simple_group(index.get("recurring_risk_flags", {}), quarantine["recurring_risk_flags"], stats)
    scrubbed["recurring_repair_actions"] = scrub_simple_group(index.get("recurring_repair_actions", {}), quarantine["recurring_repair_actions"], stats)

    for archetype, pattern in (index.get("archetype_patterns", {}) or {}).items():
        if suspicious_name(archetype) or entry_validator_generated(pattern):
            quarantine["archetype_patterns"][archetype] = pattern
            stats["quarantined_archetypes"] += 1
            continue
        scrubbed["archetype_patterns"][archetype] = scrub_archetype_pattern(pattern, stats)

    provenance_log = []
    quarantined_log = []
    for entry in index.get("provenance_log", []) or []:
        if is_validator_generated(entry):
            quarantined_log.append(entry)
            stats["quarantined_provenance_entries"] += 1
        else:
            provenance_log.append(entry)
    scrubbed["provenance_log"] = provenance_log[-100:]
    scrubbed["version"] = 1
    scrubbed["updated_at_utc"] = now_utc()
    scrubbed["last_update_provenance"] = provenance
    append_provenance_entry(scrubbed, provenance)

    report = {
        "version": 1,
        "created_at_utc": now_utc(),
        "provenance": provenance,
        "stats": stats,
        "quarantined_provenance_log": quarantined_log,
        "quarantine": quarantine,
    }
    if should_skip_production_update(provenance):
        report["skipped_production_write"] = True
        return report
    atomic_write_json(generic_diff_index_path(), scrubbed)
    atomic_write_json(generic_diff_index_scrub_report_path(), report)
    return report


def update_cross_archetype_diff_index(benchmark_results: list[dict[str, Any]], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return load_generic_diff_index()
    current = load_generic_diff_index()
    if not current:
        current = empty_index()
    safe_results = [
        result
        for result in benchmark_results
        if not (is_validator_generated(result_provenance(result, provenance)) and not is_isolated_memory_root())
    ]
    batch = build_cross_archetype_diff_index(safe_results)
    merge_movement_group(current["helpful_cards"], batch["helpful_cards"])
    merge_movement_group(current["harmful_cards"], batch["harmful_cards"])
    merge_movement_group(current["helpful_package_movements"], batch["helpful_package_movements"])
    merge_movement_group(current["harmful_package_movements"], batch["harmful_package_movements"])
    merge_simple_group(current["recurring_risk_flags"], batch["recurring_risk_flags"])
    merge_simple_group(current["recurring_repair_actions"], batch["recurring_repair_actions"])
    merge_archetype_patterns(current["archetype_patterns"], batch["archetype_patterns"])
    current["version"] = 1
    current["updated_at_utc"] = now_utc()
    current["last_update_provenance"] = provenance
    append_provenance_entry(current, provenance)
    atomic_write_json(generic_diff_index_path(), current)
    return current


def load_generic_diff_index() -> dict[str, Any]:
    payload = safe_load_json(generic_diff_index_path(), {})
    return payload if isinstance(payload, dict) and payload else empty_index()


def build_diff_index_warnings(result: dict[str, Any], historical_index: dict[str, Any] | None = None) -> list[str]:
    index = historical_index or load_generic_diff_index()
    warnings: list[str] = []
    harmful_additions = index.get("harmful_cards", {}).get("additions", {})
    helpful_removals = index.get("helpful_cards", {}).get("removals", {})
    harmful_packages = index.get("harmful_package_movements", {})
    for replay in all_result_replays(result):
        for name in (replay.get("copy_increases", {}) or {}):
            if name in harmful_additions:
                warnings.append(f"Advisory: candidate adds historically harmful card movement: {name}")
        for name in (replay.get("copy_decreases", {}) or {}):
            if name in helpful_removals:
                warnings.append(f"Advisory: candidate removes historically helpful card movement: {name}")
        for package, delta in (replay.get("package_gains_losses", {}) or {}).items():
            movement = package_key(package, delta)
            if movement in harmful_packages:
                warnings.append(f"Advisory: candidate repeats historically harmful package movement: {movement}")
    return sorted(set(warnings))


def get_diff_index_advisory_signal(archetype: str, candidate_card_movements: dict[str, Any], historical_index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = historical_index or load_generic_diff_index()
    increases = candidate_card_movements.get("copy_increases", {}) or {}
    decreases = candidate_card_movements.get("copy_decreases", {}) or {}
    hints: list[dict[str, Any]] = []
    suppressed_low_support: list[dict[str, Any]] = []
    contested: list[dict[str, Any]] = []

    for card, count in increases.items():
        evaluate_card_signal(
            card,
            int(count or 1),
            "addition",
            index.get("helpful_cards", {}).get("additions", {}),
            index.get("harmful_cards", {}).get("additions", {}),
            hints,
            suppressed_low_support,
            contested,
        )
    for card, count in decreases.items():
        evaluate_card_signal(
            card,
            int(count or 1),
            "removal",
            index.get("helpful_cards", {}).get("removals", {}),
            index.get("harmful_cards", {}).get("removals", {}),
            hints,
            suppressed_low_support,
            contested,
        )
        evaluate_helpful_card_removed_signal(
            card,
            int(count or 1),
            index.get("helpful_cards", {}).get("additions", {}),
            hints,
            suppressed_low_support,
            contested,
        )

    raw_signal = round(sum(safe_float(hint.get("signal")) for hint in hints), 6)
    capped_signal = max(-0.08, min(0.08, raw_signal))
    return {
        "archetype": archetype,
        "raw_signal": raw_signal,
        "capped_signal": capped_signal,
        "hints": hints,
        "suppressed_low_support_signals": suppressed_low_support,
        "contested_signals": contested,
        "signal_count": len(hints),
        "advisory_only": True,
    }


def top_diff_index_summary(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_helpful_additions": top_entries(index.get("helpful_cards", {}).get("additions", {})),
        "top_harmful_additions": top_entries(index.get("harmful_cards", {}).get("additions", {})),
        "top_helpful_removals": top_entries(index.get("helpful_cards", {}).get("removals", {})),
        "top_harmful_removals": top_entries(index.get("harmful_cards", {}).get("removals", {})),
        "top_helpful_package_movements": top_entries(index.get("helpful_package_movements", {})),
        "top_harmful_package_movements": top_entries(index.get("harmful_package_movements", {})),
        "common_risk_flags": top_entries(index.get("recurring_risk_flags", {})),
        "common_repair_actions": top_entries(index.get("recurring_repair_actions", {})),
        "archetypes_needing_review": archetypes_needing_review(index),
    }


def scrub_card_group(group: dict[str, Any], quarantine: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    return {
        "additions": scrub_movement_entries((group or {}).get("additions", {}), quarantine.setdefault("additions", {}), stats),
        "removals": scrub_movement_entries((group or {}).get("removals", {}), quarantine.setdefault("removals", {}), stats),
    }


def scrub_package_group(group: dict[str, Any], quarantine: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    scrubbed = {"gains": {}, "losses": {}}
    scrubbed["gains"] = scrub_movement_entries((group or {}).get("gains", {}), quarantine.setdefault("gains", {}), stats)
    scrubbed["losses"] = scrub_movement_entries((group or {}).get("losses", {}), quarantine.setdefault("losses", {}), stats)
    for key, value in (group or {}).items():
        if key in {"gains", "losses"}:
            continue
        if should_quarantine_entry(key, value):
            quarantine[key] = value
            stats["removed_entries"] += 1
        else:
            scrubbed[key] = value
    return scrubbed


def scrub_movement_entries(group: dict[str, Any], quarantine: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    scrubbed = {}
    for key, value in (group or {}).items():
        if should_quarantine_entry(key, value):
            quarantine[key] = value
            stats["removed_entries"] += 1
            continue
        if isinstance(value, dict):
            cleaned = dict(value)
            cleaned["affected_archetypes"] = [
                archetype
                for archetype in value.get("affected_archetypes", []) or []
                if not suspicious_name(archetype)
            ]
            scrubbed[key] = cleaned
        else:
            scrubbed[key] = value
    return scrubbed


def scrub_simple_group(group: dict[str, Any], quarantine: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    scrubbed = {}
    for key, value in (group or {}).items():
        if should_quarantine_entry(key, value):
            quarantine[key] = value
            stats["removed_entries"] += 1
        else:
            scrubbed[key] = value
    return scrubbed


def scrub_archetype_pattern(pattern: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    cleaned = empty_archetype_pattern()
    for key in cleaned:
        cleaned[key] = scrub_simple_group((pattern or {}).get(key, {}), {}, stats)
    return cleaned


def should_quarantine_entry(key: Any, entry: Any) -> bool:
    if suspicious_name(key) or entry_validator_generated(entry):
        return True
    if isinstance(entry, dict):
        affected = entry.get("affected_archetypes", []) or []
        if any(suspicious_name(archetype) for archetype in affected):
            return True
    return False


def suspicious_name(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(term in text for term in KNOWN_PROBE_TERMS) or text.endswith(" probe")


def entry_validator_generated(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if is_validator_generated(entry):
        return True
    provenance = entry.get("provenance")
    return is_validator_generated(provenance) if isinstance(provenance, dict) else False


def evaluate_card_signal(
    card: Any,
    count: int,
    movement: str,
    helpful_group: dict[str, Any],
    harmful_group: dict[str, Any],
    hints: list[dict[str, Any]],
    suppressed_low_support: list[dict[str, Any]],
    contested: list[dict[str, Any]],
) -> None:
    name = str(card)
    helpful = helpful_group.get(name)
    harmful = harmful_group.get(name)
    helpful_supported = supported_entry(helpful)
    harmful_supported = supported_entry(harmful)
    if helpful and not helpful_supported:
        suppressed_low_support.append({"card": name, "movement": movement, "side": "helpful", "count": safe_int(helpful.get("count")) if isinstance(helpful, dict) else 0})
    if harmful and not harmful_supported:
        suppressed_low_support.append({"card": name, "movement": movement, "side": "harmful", "count": safe_int(harmful.get("count")) if isinstance(harmful, dict) else 0})
    if helpful_supported and harmful_supported:
        contested.append({"card": name, "movement": movement, "helpful_count": safe_int(helpful.get("count")), "harmful_count": safe_int(harmful.get("count"))})
        return
    if helpful_supported:
        hints.append(signal_hint(name, movement, helpful, count, positive=True, reason=f"historically helpful {movement}"))
    if harmful_supported:
        hints.append(signal_hint(name, movement, harmful, count, positive=False, reason=f"historically harmful {movement}"))


def evaluate_helpful_card_removed_signal(
    card: Any,
    count: int,
    helpful_additions: dict[str, Any],
    hints: list[dict[str, Any]],
    suppressed_low_support: list[dict[str, Any]],
    contested: list[dict[str, Any]],
) -> None:
    name = str(card)
    entry = helpful_additions.get(name)
    if not entry:
        return
    if not supported_entry(entry):
        suppressed_low_support.append({"card": name, "movement": "removing_helpful_card", "side": "helpful", "count": safe_int(entry.get("count")) if isinstance(entry, dict) else 0})
        return
    if any(row.get("card") == name for row in contested):
        return
    hints.append(signal_hint(name, "removing_helpful_card", entry, count, positive=False, reason="candidate removes historically helpful card"))


def supported_entry(entry: Any) -> bool:
    return isinstance(entry, dict) and safe_int(entry.get("count")) >= MIN_ADVISORY_SUPPORT and not entry_validator_generated(entry)


def signal_hint(name: str, movement: str, entry: dict[str, Any], count: int, positive: bool, reason: str) -> dict[str, Any]:
    average_delta = abs(safe_float(entry.get("average_score_delta")))
    support = safe_int(entry.get("count"))
    strength = min(MAX_SINGLE_MOVEMENT_SIGNAL, 0.005 + min(0.02, support * 0.001) + min(0.01, average_delta * 0.001))
    signal = strength * max(1, min(3, int(count or 1)))
    return {
        "card": name,
        "movement": movement,
        "reason": reason,
        "support": support,
        "average_score_delta": entry.get("average_score_delta", 0),
        "signal": round(signal if positive else -signal, 6),
        "affected_archetypes": entry.get("affected_archetypes", []),
    }


def record_replay(index: dict[str, Any], archetype_entry: dict[str, Any], archetype: str, row: dict[str, Any], helpful: bool) -> None:
    replay = row.get("package_replay_report", {})
    shift = row.get("card_shift_explanation", {})
    score_delta = safe_float(row.get("improvement", replay.get("score_delta", 0)))
    card_group = index["helpful_cards"] if helpful else index["harmful_cards"]
    package_group = index["helpful_package_movements"] if helpful else index["harmful_package_movements"]
    archetype_key = "helpful" if helpful else "harmful"
    for card, count in (shift.get("copy_increases", {}) or replay.get("copy_increases", {}) or {}).items():
        bump_movement(card_group["additions"], card, archetype, score_delta, int(count or 0))
        bump_simple(archetype_entry[f"{archetype_key}_additions"], card, archetype)
    for card, count in (shift.get("copy_decreases", {}) or replay.get("copy_decreases", {}) or {}).items():
        bump_movement(card_group["removals"], card, archetype, score_delta, int(count or 0))
        bump_simple(archetype_entry[f"{archetype_key}_removals"], card, archetype)
    for package, delta in (replay.get("package_gains_losses", {}) or {}).items():
        key = package_key(package, delta)
        target = package_group["gains"] if safe_int(delta) > 0 else package_group["losses"]
        bump_movement(target, key, archetype, score_delta, abs(safe_int(delta)))
        bump_movement(package_group, key, archetype, score_delta, abs(safe_int(delta)))
        bump_simple(archetype_entry[f"{archetype_key}_packages"], key, archetype)
    for flag in replay.get("risk_flags", []) or []:
        bump_simple(index["recurring_risk_flags"], str(flag), archetype)
        bump_simple(archetype_entry["risk_flags"], str(flag), archetype)


def accepted_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = (result.get("targeted_retest", {}) or {}).get("accepted_recommendation")
    return [accepted] if isinstance(accepted, dict) and accepted else []


def rejected_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (result.get("targeted_retest", {}) or {}).get("rejected_recommendations", [])
    return [row for row in rows if isinstance(row, dict) and harmful_learning_eligible(row)]


def all_result_replays(result: dict[str, Any]) -> list[dict[str, Any]]:
    replays = []
    for row in accepted_rows(result) + rejected_rows(result):
        replay = row.get("package_replay_report", {})
        if replay:
            replays.append(replay)
    return replays


def bump_movement(group: dict[str, Any], key: str, archetype: str, score_delta: float, count: int = 1) -> None:
    if not key:
        return
    entry = group.setdefault(
        str(key),
        {
            "count": 0,
            "score_delta_total": 0.0,
            "average_score_delta": 0.0,
            "affected_archetypes": [],
            "last_seen_utc": None,
        },
    )
    entry["count"] = int(entry.get("count", 0) or 0) + max(1, int(count or 1))
    entry["score_delta_total"] = round(safe_float(entry.get("score_delta_total")) + score_delta, 4)
    entry["average_score_delta"] = round(entry["score_delta_total"] / max(1, entry["count"]), 4)
    archetypes = set(entry.get("affected_archetypes", []) or [])
    archetypes.add(archetype)
    entry["affected_archetypes"] = sorted(archetypes)
    entry["last_seen_utc"] = now_utc()


def bump_simple(group: dict[str, Any], key: str, archetype: str) -> None:
    if not key:
        return
    entry = group.setdefault(str(key), {"count": 0, "affected_archetypes": [], "last_seen_utc": None})
    entry["count"] = int(entry.get("count", 0) or 0) + 1
    archetypes = set(entry.get("affected_archetypes", []) or [])
    archetypes.add(archetype)
    entry["affected_archetypes"] = sorted(archetypes)
    entry["last_seen_utc"] = now_utc()


def merge_movement_group(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and any(isinstance(nested, dict) and "count" in nested for nested in value.values()):
            target.setdefault(key, {})
            merge_movement_group(target[key], value)
        elif isinstance(value, dict) and "count" in value:
            entry = target.setdefault(key, {"count": 0, "score_delta_total": 0.0, "average_score_delta": 0.0, "affected_archetypes": [], "last_seen_utc": None})
            entry["count"] = int(entry.get("count", 0) or 0) + int(value.get("count", 0) or 0)
            entry["score_delta_total"] = round(safe_float(entry.get("score_delta_total")) + safe_float(value.get("score_delta_total")), 4)
            entry["average_score_delta"] = round(entry["score_delta_total"] / max(1, entry["count"]), 4)
            entry["affected_archetypes"] = sorted(set(entry.get("affected_archetypes", []) or []) | set(value.get("affected_archetypes", []) or []))
            entry["last_seen_utc"] = value.get("last_seen_utc") or entry.get("last_seen_utc")


def merge_simple_group(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        entry = target.setdefault(key, {"count": 0, "affected_archetypes": [], "last_seen_utc": None})
        entry["count"] = int(entry.get("count", 0) or 0) + int(value.get("count", 0) or 0)
        entry["affected_archetypes"] = sorted(set(entry.get("affected_archetypes", []) or []) | set(value.get("affected_archetypes", []) or []))
        entry["last_seen_utc"] = value.get("last_seen_utc") or entry.get("last_seen_utc")


def merge_archetype_patterns(target: dict[str, Any], source: dict[str, Any]) -> None:
    for archetype, pattern in source.items():
        current = target.setdefault(archetype, empty_archetype_pattern())
        for key, value in pattern.items():
            merge_simple_group(current.setdefault(key, {}), value)


def finalize_index(index: dict[str, Any]) -> None:
    index["version"] = 1
    index["updated_at_utc"] = now_utc()


def empty_index() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at_utc": None,
        "helpful_cards": {"additions": {}, "removals": {}},
        "harmful_cards": {"additions": {}, "removals": {}},
        "helpful_package_movements": {"gains": {}, "losses": {}},
        "harmful_package_movements": {"gains": {}, "losses": {}},
        "recurring_risk_flags": {},
        "recurring_repair_actions": {},
        "archetype_patterns": {},
    }


def empty_archetype_pattern() -> dict[str, Any]:
    return {
        "helpful_additions": {},
        "harmful_additions": {},
        "helpful_removals": {},
        "harmful_removals": {},
        "helpful_packages": {},
        "harmful_packages": {},
        "risk_flags": {},
    }


def top_entries(group: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows = []
    for name, entry in group.items():
        if not isinstance(entry, dict) or "count" not in entry:
            continue
        rows.append(
            {
                "name": name,
                "count": int(entry.get("count", 0) or 0),
                "average_score_delta": entry.get("average_score_delta", 0),
                "affected_archetypes": entry.get("affected_archetypes", []),
            }
        )
    return sorted(rows, key=lambda row: row["count"], reverse=True)[:limit]


def archetypes_needing_review(index: dict[str, Any]) -> list[str]:
    names = set()
    for group_name in ("harmful_cards", "harmful_package_movements", "recurring_risk_flags"):
        group = index.get(group_name, {})
        collect_archetypes(names, group)
    return sorted(names)


def collect_archetypes(names: set[str], group: dict[str, Any]) -> None:
    for value in group.values():
        if not isinstance(value, dict):
            continue
        if "affected_archetypes" in value:
            names.update(value.get("affected_archetypes", []) or [])
        else:
            collect_archetypes(names, value)


def package_key(package: Any, delta: Any) -> str:
    amount = safe_int(delta)
    return f"{package}:{'+' if amount > 0 else ''}{amount}"


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
