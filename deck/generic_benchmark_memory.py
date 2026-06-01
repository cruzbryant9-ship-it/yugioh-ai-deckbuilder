from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean, pstdev
from pathlib import Path
from typing import Any

from deck.generic_trend_diagnosis import diagnose_generic_trend
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_context import append_provenance_entry, memory_file, normalize_provenance, should_skip_production_update

GENERIC_BENCHMARK_HISTORY_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "generic_benchmark_history.json"
GENERIC_BENCHMARK_HISTORY_FILENAME = "generic_benchmark_history.json"
HISTORY_LIMIT = 200
SAFE_NEGATIVE_TOLERANCE = -0.25
CONFIDENCE_COLLAPSE_DELTA = -0.15


def generic_benchmark_history_path() -> Path:
    return memory_file(GENERIC_BENCHMARK_HISTORY_FILENAME)


def update_generic_benchmark_history(report: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance or report.get("provenance") if isinstance(report, dict) else None)
    if should_skip_production_update(provenance):
        return {"profiles": {}, "skipped_validator_generated": True}
    payload = safe_load_json(generic_benchmark_history_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "profiles": {}}
    profiles = payload.setdefault("profiles", {})
    mode = str(report.get("config", {}).get("mode", "meta"))
    updated_profiles = {}
    for result in report.get("results", []):
        archetype = str(result.get("archetype", "unknown"))
        archetype_profiles = profiles.setdefault(archetype.casefold(), {})
        profile = archetype_profiles.setdefault(mode, empty_profile())
        append_benchmark_result(profile, result, provenance)
        recompute_profile_stats(profile)
        diagnosis = diagnose_generic_trend(archetype, mode, profile, result)
        profile["latest_diagnosis"] = {
            **diagnosis,
            "last_diagnosed_utc": datetime.now(timezone.utc).isoformat(),
        }
        updated_profiles[archetype] = public_profile_summary(profile)
    payload["version"] = 1
    payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_benchmark_history_path(), payload)
    return summarize_history(updated_profiles)


def load_generic_benchmark_history(archetype: str, mode: str) -> dict[str, Any]:
    payload = safe_load_json(generic_benchmark_history_path(), {"version": 1, "profiles": {}})
    profile = payload.get("profiles", {}).get(archetype.casefold(), {}).get(mode, {}) if isinstance(payload, dict) else {}
    return profile if isinstance(profile, dict) else {}


def record_targeted_retest_history(archetype: str, mode: str, retest_report: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = normalize_provenance(provenance or retest_report.get("provenance") if isinstance(retest_report, dict) else None)
    if should_skip_production_update(provenance):
        return {}
    payload = safe_load_json(generic_benchmark_history_path(), {"version": 1, "profiles": {}})
    if not isinstance(payload, dict):
        payload = {"version": 1, "profiles": {}}
    profile = payload.setdefault("profiles", {}).setdefault(archetype.casefold(), {}).setdefault(mode, empty_profile())
    accepted = retest_report.get("accepted_recommendation")
    profile["latest_targeted_retest"] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tested_recommendations": int(retest_report.get("tested_recommendations", 0) or 0),
        "accepted_recommendation": accepted,
        "rejected_recommendation_count": len(retest_report.get("rejected_recommendations", []) or []),
        "targeted_improvement": safe_float(retest_report.get("improvement")),
        "best_score": safe_float(retest_report.get("best_score")),
        "baseline_score": safe_float(retest_report.get("baseline_score")),
        "provenance": provenance,
    }
    profile.setdefault("targeted_retest_history", []).append(profile["latest_targeted_retest"])
    profile["targeted_retest_history"] = profile["targeted_retest_history"][-100:]
    payload["version"] = 1
    payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["last_update_provenance"] = provenance
    append_provenance_entry(payload, provenance)
    atomic_write_json(generic_benchmark_history_path(), payload)
    return public_profile_summary(profile)


def append_benchmark_result(profile: dict[str, Any], result: dict[str, Any], provenance: dict[str, Any] | None = None) -> None:
    accepted = accepted_for_positive_trend(result)
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "normal_score": safe_float(result.get("normal_score")),
        "tuned_score": safe_float(result.get("tuned_score")),
        "improvement": safe_float(result.get("improvement")),
        "tuned_legal": bool(result.get("tuned_legal")),
        "repair_success_rate": safe_float(result.get("repair_success_rate")),
        "average_repair_actions": safe_float(result.get("average_repair_actions")),
        "decks_still_rejected": 0 if result.get("tuned_legal") else 1,
        "memory_action": str(result.get("memory_action", "unknown")),
        "confidence_delta": safe_float(result.get("confidence_delta")),
        "best_ratio_profile": result.get("best_ratio_profile", {}),
        "normal_package_counts": result.get("normal_package_counts", {}),
        "tuned_package_counts": result.get("tuned_package_counts", {}),
        "normal_quota_warnings": list(result.get("normal_quota_warnings", []) or []),
        "tuned_quota_warnings": list(result.get("tuned_quota_warnings", []) or []),
        "common_repair_warnings": list(result.get("common_repair_warnings", []) or []),
        "accepted_for_positive_trend": accepted,
        "provenance": normalize_provenance(provenance or result.get("provenance") if isinstance(result, dict) else None),
    }
    profile.setdefault("history", []).append(entry)
    profile["history"] = profile["history"][-HISTORY_LIMIT:]
    if accepted:
        add_pattern(profile.setdefault("best_ratio_patterns", {}), result.get("best_ratio_profile", {}), entry["improvement"])
    else:
        profile.setdefault("bad_ratio_patterns", []).append(
            {
                "ratio_profile": result.get("best_ratio_profile", {}),
                "reason": bad_reason(result),
                "improvement": entry["improvement"],
                "timestamp_utc": entry["timestamp_utc"],
            }
        )
        profile["bad_ratio_patterns"] = profile["bad_ratio_patterns"][-50:]


def accepted_for_positive_trend(result: dict[str, Any]) -> bool:
    if not result.get("tuned_legal"):
        return False
    if result.get("tuned_blocked_card_violations"):
        return False
    if safe_float(result.get("confidence_delta")) < CONFIDENCE_COLLAPSE_DELTA:
        return False
    if safe_float(result.get("improvement")) < SAFE_NEGATIVE_TOLERANCE:
        return False
    return True


def bad_reason(result: dict[str, Any]) -> str:
    if not result.get("tuned_legal"):
        return "illegal_or_unrepaired_deck"
    if result.get("tuned_blocked_card_violations"):
        return "blocked_card_violation"
    if safe_float(result.get("confidence_delta")) < CONFIDENCE_COLLAPSE_DELTA:
        return "confidence_collapsed"
    if safe_float(result.get("improvement")) < SAFE_NEGATIVE_TOLERANCE:
        return "negative_improvement"
    return "not_accepted"


def recompute_profile_stats(profile: dict[str, Any]) -> None:
    history = profile.get("history", [])
    if not history:
        return
    improvements = [safe_float(entry.get("improvement")) for entry in history]
    normal_scores = [safe_float(entry.get("normal_score")) for entry in history]
    tuned_scores = [safe_float(entry.get("tuned_score")) for entry in history]
    repair_rates = [safe_float(entry.get("repair_success_rate")) for entry in history]
    repair_actions = [safe_float(entry.get("average_repair_actions")) for entry in history]
    profile["total_benchmark_runs"] = len(history)
    profile["average_normal_score"] = round(mean(normal_scores), 4)
    profile["average_tuned_score"] = round(mean(tuned_scores), 4)
    profile["average_improvement"] = round(mean(improvements), 4)
    profile["best_improvement"] = round(max(improvements), 4)
    profile["worst_improvement"] = round(min(improvements), 4)
    profile["tuning_hurt_count"] = sum(1 for value in improvements if value < 0)
    profile["repair_success_rate_history"] = repair_rates[-50:]
    profile["average_repair_actions"] = round(mean(repair_actions), 4)
    profile["rejected_deck_count"] = sum(int(entry.get("decks_still_rejected", 0) or 0) for entry in history)
    profile["memory_update_count"] = sum(1 for entry in history if entry.get("memory_action") == "updated")
    profile["trend_direction"] = trend_direction(improvements)
    profile["updated_at_utc"] = datetime.now(timezone.utc).isoformat()


def trend_direction(improvements: list[float]) -> str:
    if len(improvements) < 3:
        return "stable"
    recent = improvements[-5:]
    previous = improvements[-10:-5] or improvements[:-5]
    if len(recent) >= 3 and pstdev(recent) > 2.0:
        return "noisy"
    if not previous:
        return "stable"
    delta = mean(recent) - mean(previous)
    if delta > 0.25:
        return "improving"
    if delta < -0.25:
        return "declining"
    return "stable"


def public_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_benchmark_runs": profile.get("total_benchmark_runs", 0),
        "average_normal_score": profile.get("average_normal_score", 0),
        "average_tuned_score": profile.get("average_tuned_score", 0),
        "average_improvement": profile.get("average_improvement", 0),
        "best_improvement": profile.get("best_improvement", 0),
        "worst_improvement": profile.get("worst_improvement", 0),
        "tuning_hurt_count": profile.get("tuning_hurt_count", 0),
        "repair_reliability": average(profile.get("repair_success_rate_history", [])),
        "average_repair_actions": profile.get("average_repair_actions", 0),
        "rejected_deck_count": profile.get("rejected_deck_count", 0),
        "memory_update_count": profile.get("memory_update_count", 0),
        "trend_direction": profile.get("trend_direction", "stable"),
        "best_ratio_patterns": top_patterns(profile.get("best_ratio_patterns", {})),
        "bad_ratio_pattern_count": len(profile.get("bad_ratio_patterns", [])),
        "latest_diagnosis": profile.get("latest_diagnosis", {}),
        "latest_targeted_retest": profile.get("latest_targeted_retest", {}),
    }


def summarize_history(updated_profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not updated_profiles:
        return {"profiles": {}, "best_long_term_archetypes": [], "worst_long_term_archetypes": [], "noisy_archetypes": [], "recommended_follow_up_archetypes": []}
    profiles = dict(sorted(updated_profiles.items()))
    ranked = sorted(profiles.items(), key=lambda item: safe_float(item[1].get("average_improvement")), reverse=True)
    worst = sorted(profiles.items(), key=lambda item: safe_float(item[1].get("average_improvement")))
    noisy = [name for name, profile in profiles.items() if profile.get("trend_direction") == "noisy"]
    follow_up = [
        name
        for name, profile in profiles.items()
        if profile.get("trend_direction") in {"declining", "noisy"}
        or safe_float(profile.get("average_improvement")) < 0
        or safe_float(profile.get("repair_reliability")) < 0.8
        or int(profile.get("rejected_deck_count", 0) or 0) > 0
        or profile.get("latest_diagnosis", {}).get("severity") in {"medium", "high"}
    ]
    return {
        "profiles": profiles,
        "best_long_term_archetypes": [(name, profile.get("average_improvement", 0)) for name, profile in ranked[:5]],
        "worst_long_term_archetypes": [(name, profile.get("average_improvement", 0)) for name, profile in worst[:5]],
        "noisy_archetypes": noisy,
        "recommended_follow_up_archetypes": follow_up,
        "historical_average_improvement": round(mean(safe_float(profile.get("average_improvement")) for profile in profiles.values()), 4),
        "recent_average_improvement": round(mean(safe_float(profile.get("average_improvement")) for profile in updated_profiles.values()), 4),
        "average_repair_reliability": round(mean(safe_float(profile.get("repair_reliability")) for profile in profiles.values()), 4),
    }


def add_pattern(patterns: dict[str, Any], ratio_profile: dict[str, Any], improvement: float) -> None:
    key = ratio_profile_key(ratio_profile)
    entry = patterns.setdefault(key, {"count": 0, "improvement_total": 0.0, "best_improvement": -999.0, "ratio_profile": ratio_profile})
    entry["count"] = int(entry.get("count", 0) or 0) + 1
    entry["improvement_total"] = safe_float(entry.get("improvement_total")) + improvement
    entry["best_improvement"] = max(safe_float(entry.get("best_improvement")), improvement)


def top_patterns(patterns: Any) -> list[dict[str, Any]]:
    if not isinstance(patterns, dict):
        return []
    rows = []
    for key, value in patterns.items():
        if not isinstance(value, dict):
            continue
        count = max(1, int(value.get("count", 1) or 1))
        rows.append(
            {
                "pattern": key,
                "count": count,
                "average_improvement": round(safe_float(value.get("improvement_total")) / count, 4),
                "best_improvement": round(safe_float(value.get("best_improvement")), 4),
                "ratio_profile": value.get("ratio_profile", {}),
            }
        )
    return sorted(rows, key=lambda row: (row["average_improvement"], row["count"]), reverse=True)[:5]


def ratio_profile_key(profile: dict[str, Any]) -> str:
    if not isinstance(profile, dict) or not profile:
        return "none"
    return "|".join(f"{key}:{profile[key]}" for key in sorted(profile))


def empty_profile() -> dict[str, Any]:
    return {
        "history": [],
        "total_benchmark_runs": 0,
        "average_normal_score": 0,
        "average_tuned_score": 0,
        "average_improvement": 0,
        "best_improvement": 0,
        "worst_improvement": 0,
        "tuning_hurt_count": 0,
        "repair_success_rate_history": [],
        "average_repair_actions": 0,
        "rejected_deck_count": 0,
        "memory_update_count": 0,
        "best_ratio_patterns": {},
        "bad_ratio_patterns": [],
        "trend_direction": "stable",
        "latest_diagnosis": {},
        "latest_targeted_retest": {},
        "targeted_retest_history": [],
    }


def average(values: Any) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return round(mean(safe_float(value) for value in values), 4)


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
