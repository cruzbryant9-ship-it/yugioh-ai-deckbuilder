from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.rejection_classification import harmful_learning_eligible
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update

GENERIC_RATIO_MEMORY_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "generic_ratio_memory.json"
GENERIC_RATIO_MEMORY_FILENAME = "generic_ratio_memory.json"
RATIO_MEMORY_WEIGHT_CAP = 0.15


def generic_ratio_memory_path() -> Path:
    return memory_file(GENERIC_RATIO_MEMORY_FILENAME)


def load_generic_ratio_memory(archetype: str, mode: str) -> dict[str, Any]:
    payload = safe_load_json(generic_ratio_memory_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        return {}
    profile = payload.get("profiles", {}).get(archetype.casefold(), {}).get(mode, {})
    return profile if isinstance(profile, dict) else {}


def save_generic_ratio_memory(archetype: str, mode: str, tuning_report: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance or tuning_report.get("provenance") if isinstance(tuning_report, dict) else None)
    if should_skip_production_update(provenance):
        return {}
    payload = safe_load_json(generic_ratio_memory_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "profiles": {}}
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    current = archetype_profiles.setdefault(mode, empty_profile())

    best = tuning_report.get("best_result", {})
    ratio_profile = best.get("ratio_profile", {})
    ratio_key = ratio_profile_key(ratio_profile)
    score = safe_float(best.get("score"))
    previous_best = safe_float(current.get("best_score"))
    if score >= previous_best or not current.get("best_package_ratios"):
        current["best_package_ratios"] = ratio_profile
        current["best_balance"] = {
            key: ratio_profile.get(key)
            for key in ("starters_searchers", "extenders", "payoffs", "interruptions", "board_breakers", "max_bricks")
            if key in ratio_profile
        }
    current["best_score"] = max(previous_best, score)
    current["last_best_score"] = score
    current.setdefault("ratio_score_totals", {})
    current.setdefault("ratio_score_counts", {})
    current["ratio_score_totals"][ratio_key] = safe_float(current["ratio_score_totals"].get(ratio_key)) + score
    current["ratio_score_counts"][ratio_key] = int(current["ratio_score_counts"].get(ratio_key, 0) or 0) + 1
    current["average_score_by_ratio_profile"] = average_scores(current["ratio_score_totals"], current["ratio_score_counts"])
    current.setdefault("confidence_trends", []).append(safe_float(best.get("confidence")))
    current["confidence_trends"] = current["confidence_trends"][-100:]
    current["bad_ratio_patterns"] = [
        result.get("ratio_profile", {})
        for result in tuning_report.get("results", [])
        if safe_float(result.get("score")) < safe_float(tuning_report.get("average_score")) * 0.85
    ][:10]
    current["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    current["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_ratio_memory_path(), payload)
    return current


def record_bad_ratio_pattern(
    archetype: str,
    mode: str,
    ratio_profile: dict[str, Any],
    reason: str,
    score_delta: float,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    if should_skip_production_update(provenance):
        return {}
    payload = safe_load_json(generic_ratio_memory_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "profiles": {}}
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    current = archetype_profiles.setdefault(mode, empty_profile())
    current.setdefault("bad_ratio_patterns", [])
    current["bad_ratio_patterns"].append(
        {
            "ratio_profile": ratio_profile,
            "reason": reason,
            "score_delta": round(float(score_delta), 4),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
        }
    )
    current["bad_ratio_patterns"] = current["bad_ratio_patterns"][-50:]
    current["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    current["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_ratio_memory_path(), payload)
    return current


def record_targeted_recommendation_result(archetype: str, mode: str, retest_report: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance or retest_report.get("provenance") if isinstance(retest_report, dict) else None)
    if should_skip_production_update(provenance):
        return {}
    payload = safe_load_json(generic_ratio_memory_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "profiles": {}}
    profiles = payload.setdefault("profiles", {})
    archetype_profiles = profiles.setdefault(archetype.casefold(), {})
    current = archetype_profiles.setdefault(mode, empty_profile())
    accepted = retest_report.get("accepted_recommendation")
    rejected = list(retest_report.get("rejected_recommendations", []) or [])
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tested_recommendations": int(retest_report.get("tested_recommendations", 0) or 0),
        "accepted": bool(accepted),
        "accepted_recommendation": accepted,
        "rejected_recommendations": rejected,
        "best_score": safe_float(retest_report.get("best_score")),
        "baseline_score": safe_float(retest_report.get("baseline_score")),
        "improvement": safe_float(retest_report.get("improvement")),
        "provenance": provenance,
    }
    current.setdefault("targeted_recommendation_history", []).append(entry)
    current["targeted_recommendation_history"] = current["targeted_recommendation_history"][-100:]
    if accepted:
        current.setdefault("accepted_targeted_recommendations", []).append(accepted)
        current["accepted_targeted_recommendations"] = current["accepted_targeted_recommendations"][-50:]
        update_card_movement_memory(current, accepted.get("card_shift_explanation", {}), helpful=True)
        score = safe_float(accepted.get("score"))
        if score >= safe_float(current.get("best_score")):
            current["best_package_ratios"] = accepted.get("ratio_profile", {})
            current["best_score"] = score
            current["last_best_score"] = score
            current["best_balance"] = {
                key: accepted.get("ratio_profile", {}).get(key)
                for key in ("starters_searchers", "extenders", "payoffs", "interruptions", "board_breakers", "max_bricks")
                if key in accepted.get("ratio_profile", {})
            }
        update_diagnosis_adjustment_success(current, accepted, True)
    for row in rejected:
        current.setdefault("rejected_targeted_recommendations", []).append(row)
        update_diagnosis_adjustment_success(current, row.get("recommendation", {}), False)
        if harmful_learning_eligible(row):
            update_card_movement_memory(current, row.get("card_shift_explanation", {}), helpful=False)
    current["rejected_targeted_recommendations"] = current.get("rejected_targeted_recommendations", [])[-100:]
    history = current.get("targeted_recommendation_history", [])
    if history:
        current["recommendation_success_rate"] = round(sum(1 for item in history if item.get("accepted")) / len(history), 4)
    current["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    current["last_update_provenance"] = provenance
    payload["version"] = 1
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_ratio_memory_path(), payload)
    return current


def update_card_movement_memory(current: dict[str, Any], shift: dict[str, Any], helpful: bool) -> None:
    if not isinstance(shift, dict):
        return
    prefix = "helpful" if helpful else "harmful"
    additions = current.setdefault(f"{prefix}_card_addition_counts", {})
    removals = current.setdefault(f"{prefix}_card_removal_counts", {})
    for name in shift.get("copy_increases", {}) or {}:
        additions[name] = int(additions.get(name, 0) or 0) + 1
    for name in shift.get("copy_decreases", {}) or {}:
        removals[name] = int(removals.get(name, 0) or 0) + 1
    current["helpful_card_movement_counts"] = {
        "additions": current.get("helpful_card_addition_counts", {}),
        "removals": current.get("helpful_card_removal_counts", {}),
    }
    current["harmful_card_movement_counts"] = {
        "additions": current.get("harmful_card_addition_counts", {}),
        "removals": current.get("harmful_card_removal_counts", {}),
    }


def update_diagnosis_adjustment_success(current: dict[str, Any], recommendation: dict[str, Any], accepted: bool) -> None:
    causes = recommendation.get("diagnosis_causes", []) if isinstance(recommendation, dict) else []
    ratio_profile = recommendation.get("ratio_profile", {}) if isinstance(recommendation, dict) else {}
    mapping = current.setdefault("diagnosis_adjustment_success", {})
    for cause in causes:
        entry = mapping.setdefault(cause, {"tested": 0, "accepted": 0, "best_adjustment": {}, "last_ratio_profile": {}})
        entry["tested"] = int(entry.get("tested", 0) or 0) + 1
        entry["last_ratio_profile"] = ratio_profile
        if accepted:
            entry["accepted"] = int(entry.get("accepted", 0) or 0) + 1
            entry["best_adjustment"] = ratio_profile
        entry["success_rate"] = round(entry["accepted"] / max(1, entry["tested"]), 4)


def ratio_profile_from_memory(archetype: str, mode: str) -> dict[str, int]:
    memory = load_generic_ratio_memory(archetype, mode)
    ratios = memory.get("best_package_ratios", {})
    if not isinstance(ratios, dict):
        return {}
    capped: dict[str, int] = {}
    for key, value in ratios.items():
        try:
            capped[key] = int(value)
        except (TypeError, ValueError):
            continue
    return capped


def ratio_profile_key(ratio_profile: dict[str, Any]) -> str:
    return "|".join(f"{key}:{ratio_profile[key]}" for key in sorted(ratio_profile))


def empty_profile() -> dict[str, Any]:
    return {
        "best_package_ratios": {},
        "average_score_by_ratio_profile": {},
        "best_balance": {},
        "bad_ratio_patterns": [],
        "confidence_trends": [],
        "best_score": 0,
        "last_best_score": 0,
        "ratio_score_totals": {},
        "ratio_score_counts": {},
        "targeted_recommendation_history": [],
        "accepted_targeted_recommendations": [],
        "rejected_targeted_recommendations": [],
        "recommendation_success_rate": 0,
        "diagnosis_adjustment_success": {},
        "helpful_card_addition_counts": {},
        "helpful_card_removal_counts": {},
        "harmful_card_addition_counts": {},
        "harmful_card_removal_counts": {},
        "helpful_card_movement_counts": {"additions": {}, "removals": {}},
        "harmful_card_movement_counts": {"additions": {}, "removals": {}},
    }


def average_scores(totals: dict[str, Any], counts: dict[str, Any]) -> dict[str, float]:
    averages = {}
    for key, total in totals.items():
        count = max(1, int(counts.get(key, 1) or 1))
        averages[key] = round(safe_float(total) / count, 4)
    return averages


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
