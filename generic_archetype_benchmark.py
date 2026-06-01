from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck import advisory_influence_budget as advisory_budget_module
from deck.builder import score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_benchmark_memory import record_targeted_retest_history, update_generic_benchmark_history
from deck.generic_deck_builder import build_generic_deck
from deck.generic_deck_diff_report import build_rich_deck_diff_report
from deck.generic_diff_index import (
    build_diff_index_warnings,
    load_generic_diff_index,
    scrub_diff_index_memory,
    top_diff_index_summary,
    update_cross_archetype_diff_index,
)
from deck.generic_filler_memory import load_generic_filler_memory, update_generic_filler_memory
from deck.generic_ratio_recommender import recommend_ratio_adjustments
from deck.generic_ratio_memory import record_bad_ratio_pattern, save_generic_ratio_memory
from deck.generic_targeted_retest import run_targeted_retest
from deck.generic_tuner import tune_generic_deck
from deck.rejection_classification import harmful_learning_eligible
from filler_signal_gate_report import build_filler_signal_gate_report, save_gate_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.memory_context import normalize_provenance

BENCHMARK_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "generic_benchmarks"
DECK_DIFF_DIR = BENCHMARK_DIR / "deck_diffs"
MIN_SAFE_CONFIDENCE_DELTA = -0.15
MAX_SAFE_NEGATIVE_DELTA = -5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark generic deck building and tuning across archetypes.")
    parser.add_argument("--archetypes", nargs="+", required=True)
    parser.add_argument("--mode", default="meta", choices=("meta", "innovation"))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--show-replay", action="store_true", help="Print compact before/after package replay snippets.")
    parser.add_argument("--enable-filler-memory-influence", action="store_true", help="Experimentally apply tiny activation-ready filler-memory ordering bias.")
    return parser.parse_args()


def run_benchmark(
    archetypes: list[str],
    mode: str = "meta",
    runs: int = 10,
    show_replay: bool = False,
    provenance: dict[str, Any] | None = None,
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    previous_filler_memory_flag = advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE
    advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = bool(enable_filler_memory_influence)
    try:
        return _run_benchmark_core(archetypes, mode, runs, show_replay, provenance, enable_filler_memory_influence)
    finally:
        advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE = previous_filler_memory_flag


def _run_benchmark_core(
    archetypes: list[str],
    mode: str = "meta",
    runs: int = 10,
    show_replay: bool = False,
    provenance: dict[str, Any] | None = None,
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance, source="benchmark", smoke=runs <= 1)
    scrub_report = scrub_diff_index_memory(provenance=normalize_provenance(provenance, source="benchmark_scrub"))
    cards = CardDatabase().load_cards()
    results = [benchmark_archetype(archetype, cards, mode, runs, provenance, enable_filler_memory_influence=enable_filler_memory_influence) for archetype in archetypes]
    summary = summarize_benchmark(results)
    report = {
        "report_type": "generic_archetype_benchmark",
        "report_version": "phase6m-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "archetypes": archetypes,
            "mode": mode,
            "runs": runs,
            "show_replay": show_replay,
            "filler_memory_influence_enabled": bool(enable_filler_memory_influence),
        },
        "provenance": provenance,
        "scrub_report_summary": scrub_report_summary(scrub_report),
        "summary": summary,
        "results": results,
    }
    history = update_generic_benchmark_history(report, provenance=provenance)
    report["benchmark_history"] = history
    attach_history_diagnoses(report)
    run_targeted_retests(report, cards)
    attach_filler_memory_updates(report, provenance)
    attach_filler_signal_gate_report(report)
    historical_diff_index = load_generic_diff_index()
    attach_diff_index_warnings(report, historical_diff_index)
    diff_index = update_cross_archetype_diff_index(report.get("results", []), provenance=provenance)
    report["diff_index_summary"] = top_diff_index_summary(diff_index)
    report["summary"]["diagnosis_severity_counts"] = dict(
        Counter((result.get("trend_diagnosis") or {}).get("severity", "unknown") for result in report.get("results", []))
    )
    report["summary"]["diagnosis_influenced_tuning_count"] = sum(1 for result in report.get("results", []) if result.get("diagnosis_influenced_tuning"))
    report["summary"]["targeted_retest_count"] = sum(1 for result in report.get("results", []) if result.get("targeted_retest", {}).get("targeted_retest_used"))
    report["summary"]["accepted_targeted_retests"] = sum(1 for result in report.get("results", []) if result.get("targeted_retest", {}).get("accepted_recommendation"))
    report["summary"]["targeted_retest_improvements"] = {
        result["archetype"]: result.get("targeted_retest", {}).get("improvement", 0)
        for result in report.get("results", [])
        if result.get("targeted_retest")
    }
    report["summary"]["card_shift_summary"] = summarize_card_shifts(report)
    report["summary"]["package_replay_summary"] = summarize_package_replays(report)
    report["summary"]["diff_index_summary"] = report["diff_index_summary"]
    report["summary"]["filler_impact_classification_summary"] = summarize_filler_impacts(report.get("results", []))
    report["summary"]["filler_memory_concentration_warnings"] = report.get("filler_memory_concentration_warnings", [])
    report["summary"]["filler_memory_cross_archetype_index_size"] = report.get("filler_memory_cross_archetype_index_size", 0)
    report["summary"]["filler_signal_eligibility_summary"] = report.get("filler_signal_gate_report", {}).get("summary", {})
    report["summary"]["scrub_report_summary"] = report["scrub_report_summary"]
    report["summary"]["diff_index_bias_used_count"] = sum(1 for result in report.get("results", []) if result.get("diff_index_bias_used"))
    report["summary"]["advisory_signals_applied_count"] = sum(len(result.get("advisory_signals_applied", []) or []) for result in report.get("results", []))
    report["summary"]["suppressed_low_support_signal_count"] = sum(len(result.get("suppressed_low_support_signals", []) or []) for result in report.get("results", []))
    report["summary"]["contested_signal_count"] = sum(len(result.get("contested_signals", []) or []) for result in report.get("results", []))
    report["summary"]["historical_average_improvement"] = history.get("historical_average_improvement", 0)
    report["summary"]["recent_average_improvement"] = history.get("recent_average_improvement", 0)
    report["summary"]["average_repair_reliability"] = history.get("average_repair_reliability", 0)
    report["summary"]["recommended_follow_up_archetypes"] = history.get("recommended_follow_up_archetypes", [])
    report["summary"]["filler_memory_influence_enabled"] = bool(enable_filler_memory_influence)
    report["summary"]["filler_memory_influence"] = summarize_benchmark_filler_memory_influence(results)
    return report


def benchmark_archetype(
    archetype: str,
    cards: list[dict[str, Any]],
    mode: str,
    runs: int,
    provenance: dict[str, Any] | None = None,
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    normal_deck, normal_report = build_generic_deck(archetype, cards, mode=mode, use_ratio_memory=False)
    normal_score = score_deck_breakdown(normal_deck, archetype, mode)["final_score"]
    normal_main, normal_extra = split_deck(normal_deck)
    normal_blocked = blocked_card_violations(normal_deck)
    normal_legal = len(normal_main) == 40 and len(normal_extra) <= 15 and not normal_blocked

    tuned_report = tune_generic_deck(
        archetype,
        cards,
        mode=mode,
        runs=runs,
        update_memory=False,
        enable_filler_memory_influence=enable_filler_memory_influence,
    )
    tuned_deck = tuned_report.get("best_deck", [])
    tuned_main, tuned_extra = split_deck(tuned_deck)
    tuned_score = float(tuned_report.get("best_score", 0) or 0)
    tuned_blocked = blocked_card_violations(tuned_deck)
    tuned_best = tuned_report.get("best_result", {})
    tuned_legal = bool(tuned_best.get("legal")) and len(tuned_main) == 40 and len(tuned_extra) <= 15 and not tuned_blocked
    improvement = round(tuned_score - float(normal_score or 0), 2)
    confidence_delta = round(float(tuned_best.get("confidence", 0) or 0) - float(normal_report.get("generic_confidence_score", 0) or 0), 4)
    memory_action = update_memory_safely(archetype, mode, tuned_report, improvement, confidence_delta, tuned_legal, provenance)

    return {
        "archetype": archetype,
        "normal_score": round(float(normal_score or 0), 2),
        "tuned_score": round(tuned_score, 2),
        "improvement": improvement,
        "normal_confidence": normal_report.get("generic_confidence_score", 0),
        "tuned_confidence": tuned_best.get("confidence", 0),
        "confidence_delta": confidence_delta,
        "normal_package_counts": normal_report.get("package_counts", {}),
        "tuned_package_counts": tuned_best.get("package_counts", {}),
        "normal_deck_sections": deck_sections(normal_main, normal_extra),
        "tuned_deck_sections": deck_sections(tuned_main, tuned_extra),
        "normal_deck_names": card_names(normal_deck),
        "tuned_deck_names": card_names(tuned_deck),
        "normal_repair_actions": normal_report.get("repair_actions", []),
        "tuned_repair_actions": tuned_best.get("repair_actions", []),
        "normal_quota_warnings": normal_report.get("quota_warnings", []),
        "tuned_quota_warnings": tuned_best.get("quota_warnings", []),
        "normal_legal": normal_legal,
        "tuned_legal": tuned_legal,
        "normal_blocked_card_violations": normal_blocked,
        "tuned_blocked_card_violations": tuned_blocked,
        "skeleton_coverage": tuned_report.get("combo_skeleton_coverage", 0),
        "variant_count": tuned_report.get("variant_count", 0),
        "legal_variant_count": tuned_report.get("legal_variant_count", 0),
        "best_ratio_profile": tuned_best.get("ratio_profile", {}),
        "repair_success_rate": tuned_report.get("repair_success_rate", 0),
        "decks_saved_by_repair": tuned_report.get("decks_saved_by_repair", 0),
        "decks_completed_by_safe_filler": tuned_report.get("decks_completed_by_safe_filler", 0),
        "contextual_filler_usage_count": tuned_report.get("contextual_filler_usage_count", 0),
        "selected_filler_counts": tuned_report.get("selected_filler_counts", {}),
        "filler_role_distribution": tuned_report.get("filler_role_distribution", {}),
        "filler_impact_summary": tuned_report.get("filler_impact_summary", {}),
        "filler_impact_reports": tuned_report.get("filler_impact_reports", []),
        "best_selected_fillers": tuned_best.get("selected_fillers", []),
        "best_filler_impact": tuned_best.get("filler_impact", {}),
        "best_filler_reasons": tuned_best.get("filler_reasons", []),
        "best_filler_context_scores": tuned_best.get("filler_context_scores", {}),
        "best_rejected_filler_reasons": tuned_best.get("rejected_filler_reasons", []),
        "fallback_used_count": tuned_report.get("fallback_used_count", 0),
        "average_repair_actions": average_repair_actions(tuned_report.get("results", [])),
        "common_repair_warnings": tuned_report.get("common_repair_warnings", []),
        "under_40_diagnostics": tuned_report.get("under_40_diagnostics", []),
        "repair_strategy_counts": tuned_report.get("repair_strategy_counts", {}),
        "memory_action": memory_action,
        "diagnosis_influenced_tuning": tuned_report.get("diagnosis_influenced_tuning", False),
        "diagnosis_bias": tuned_report.get("diagnosis_bias", {}),
        "diagnosis_used": tuned_report.get("diagnosis", {}),
        "diff_index_bias_used": tuned_report.get("diff_index_bias_used", False),
        "advisory_budget_used": tuned_report.get("advisory_budget_used", {}),
        "advisory_signals_applied": tuned_report.get("advisory_signals_applied", []),
        "suppressed_low_support_signals": tuned_report.get("suppressed_low_support_signals", []),
        "contested_signals": tuned_report.get("contested_signals", []),
        "advisory_bias_calibration": tuned_report.get("advisory_bias_calibration", {}),
        "filler_memory_influence_enabled": tuned_report.get("filler_memory_influence_enabled", False),
        "filler_memory_influence_summary": tuned_report.get("filler_memory_influence_summary", {}),
        "provenance": provenance or {},
    }


def attach_history_diagnoses(report: dict[str, Any]) -> None:
    profiles = report.get("benchmark_history", {}).get("profiles", {})
    if not isinstance(profiles, dict):
        return
    for result in report.get("results", []):
        archetype = result.get("archetype")
        profile = profiles.get(archetype, {}) if archetype else {}
        result["trend_diagnosis"] = profile.get("latest_diagnosis", {}) if isinstance(profile, dict) else {}


def run_targeted_retests(report: dict[str, Any], cards: list[dict[str, Any]]) -> None:
    mode = str(report.get("config", {}).get("mode", "meta"))
    runs = max(1, min(3, int(report.get("config", {}).get("runs", 3) or 3)))
    profiles = report.setdefault("benchmark_history", {}).setdefault("profiles", {})
    for result in report.get("results", []):
        diagnosis = result.get("trend_diagnosis", {})
        if not should_target_retest(diagnosis, profiles.get(result.get("archetype"), {})):
            result["ratio_recommendations"] = []
            result["targeted_retest"] = {"targeted_retest_used": False, "tested_recommendations": 0}
            continue
        recommendations = recommend_ratio_adjustments(
            str(result.get("archetype", "unknown")),
            mode,
            diagnosis,
            result.get("best_ratio_profile", {}),
        )
        provenance = normalize_provenance(report.get("provenance"), source="benchmark", smoke=runs <= 1)
        retest = run_targeted_retest(str(result.get("archetype", "unknown")), cards, mode, recommendations, runs_per_recommendation=runs, provenance=provenance)
        result["ratio_recommendations"] = recommendations.get("recommendations", [])
        result["targeted_retest"] = retest
        profiles[str(result.get("archetype", "unknown"))] = record_targeted_retest_history(str(result.get("archetype", "unknown")), mode, retest, provenance=provenance)


def attach_diff_index_warnings(report: dict[str, Any], historical_index: dict[str, Any]) -> None:
    for result in report.get("results", []):
        result["diff_index_warnings"] = build_diff_index_warnings(result, historical_index)


def attach_filler_memory_updates(report: dict[str, Any], provenance: dict[str, Any]) -> None:
    mode = str(report.get("config", {}).get("mode", "meta"))
    for result in report.get("results", []):
        impacts = result.get("filler_impact_reports", []) or []
        if not impacts:
            result["filler_memory_update"] = "none"
            continue
        profile = update_generic_filler_memory(str(result.get("archetype", "unknown")), mode, impacts, provenance=provenance)
        result["filler_memory_update"] = "updated" if profile else "skipped"
        result["filler_reliability_by_archetype"] = summarize_filler_profile(profile)
        result["filler_memory_eligibility_status"] = {
            name: data.get("eligibility", {})
            for name, data in (profile.get("fillers", {}) if isinstance(profile, dict) else {}).items()
        }
        result["completion_biased_cards"] = [
            name
            for name, data in (profile.get("fillers", {}) if isinstance(profile, dict) else {}).items()
            if data.get("completion_bias_flag")
        ]
    memory = load_generic_filler_memory()
    report["filler_memory_concentration_warnings"] = memory.get("concentration_warnings", []) if isinstance(memory, dict) else []
    report["filler_memory_cross_archetype_index_size"] = len(memory.get("cross_archetype_index", {}) if isinstance(memory, dict) else {})


def attach_filler_signal_gate_report(report: dict[str, Any]) -> None:
    gate_report = build_filler_signal_gate_report()
    summary = gate_report.get("summary", {}) if isinstance(gate_report, dict) else {}
    report["filler_signal_gate_report"] = gate_report
    report["cards_closest_to_filler_signal_eligibility"] = summary.get("cards_closest_to_eligibility", [])
    report["filler_signals_blocked_by_concentration"] = summary.get("cards_blocked_by_concentration", [])
    report["filler_signals_blocked_by_attribution"] = summary.get("cards_blocked_by_attribution", [])
    report["filler_signals_blocked_by_support"] = summary.get("cards_blocked_by_support", [])


def should_target_retest(diagnosis: dict[str, Any], profile: dict[str, Any]) -> bool:
    if not isinstance(diagnosis, dict):
        return False
    severity = diagnosis.get("severity")
    return severity in {"medium", "high"} or profile.get("trend_direction") in {"declining", "noisy"}


def summarize_card_shifts(report: dict[str, Any]) -> dict[str, Any]:
    helpful_additions: Counter[str] = Counter()
    helpful_removals: Counter[str] = Counter()
    harmful_additions: Counter[str] = Counter()
    harmful_removals: Counter[str] = Counter()
    package_movement: Counter[str] = Counter()
    accepted_count = 0
    rejected_count = 0
    for result in report.get("results", []):
        retest = result.get("targeted_retest", {})
        accepted = retest.get("accepted_recommendation") or {}
        accepted_shift = accepted.get("card_shift_explanation", {}) if isinstance(accepted, dict) else {}
        if accepted_shift:
            accepted_count += 1
            count_shift_cards(helpful_additions, helpful_removals, accepted_shift)
            count_package_movement(package_movement, accepted_shift)
        for rejected in retest.get("rejected_recommendations", []) or []:
            if not harmful_learning_eligible(rejected):
                continue
            rejected_shift = rejected.get("card_shift_explanation", {})
            if rejected_shift:
                rejected_count += 1
                count_shift_cards(harmful_additions, harmful_removals, rejected_shift)
                count_package_movement(package_movement, rejected_shift)
    return {
        "accepted_shift_count": accepted_count,
        "rejected_shift_count": rejected_count,
        "most_common_helpful_additions": helpful_additions.most_common(10),
        "most_common_helpful_removals": helpful_removals.most_common(10),
        "most_common_harmful_additions": harmful_additions.most_common(10),
        "most_common_harmful_removals": harmful_removals.most_common(10),
        "package_movement_summary": package_movement.most_common(20),
    }


def summarize_package_replays(report: dict[str, Any]) -> dict[str, Any]:
    accepted = 0
    rejected = 0
    package_deltas: Counter[str] = Counter()
    risk_flags: Counter[str] = Counter()
    for result in report.get("results", []):
        accepted_replay = (result.get("targeted_retest", {}).get("accepted_recommendation") or {}).get("package_replay_report", {})
        if accepted_replay:
            accepted += 1
            count_replay_summary(package_deltas, risk_flags, accepted_replay)
        for row in result.get("targeted_retest", {}).get("rejected_recommendations", []) or []:
            replay = row.get("package_replay_report", {})
            if replay:
                rejected += 1
                count_replay_summary(package_deltas, risk_flags, replay)
    return {
        "accepted_replay_count": accepted,
        "rejected_replay_count": rejected,
        "package_delta_counts": package_deltas.most_common(20),
        "risk_flag_counts": risk_flags.most_common(20),
    }


def count_replay_summary(package_deltas: Counter[str], risk_flags: Counter[str], replay: dict[str, Any]) -> None:
    for package, delta in (replay.get("package_gains_losses", {}) or {}).items():
        package_deltas[f"{package}:{int(delta):+d}"] += 1
    for flag in replay.get("risk_flags", []) or []:
        risk_flags[str(flag)] += 1


def count_shift_cards(additions: Counter[str], removals: Counter[str], shift: dict[str, Any]) -> None:
    for name, count in (shift.get("copy_increases", {}) or {}).items():
        additions[name] += int(count or 0)
    for name, count in (shift.get("copy_decreases", {}) or {}).items():
        removals[name] += int(count or 0)


def count_package_movement(counter: Counter[str], shift: dict[str, Any]) -> None:
    for package, delta in (shift.get("package_delta", {}) or {}).items():
        try:
            amount = int(delta)
        except (TypeError, ValueError):
            amount = 0
        if amount:
            counter[f"{package}:{'+' if amount > 0 else ''}{amount}"] += 1


def update_memory_safely(
    archetype: str,
    mode: str,
    tuned_report: dict[str, Any],
    improvement: float,
    confidence_delta: float,
    tuned_legal: bool,
    provenance: dict[str, Any] | None = None,
) -> str:
    best_ratio = tuned_report.get("best_result", {}).get("ratio_profile", {})
    if tuned_legal and improvement > 0 and confidence_delta >= MIN_SAFE_CONFIDENCE_DELTA:
        save_generic_ratio_memory(archetype, mode, tuned_report, provenance=provenance)
        return "updated"
    if improvement < 0 or confidence_delta < MIN_SAFE_CONFIDENCE_DELTA:
        reason = "tuning_hurt_score" if improvement < 0 else "confidence_collapsed"
        record_bad_ratio_pattern(archetype, mode, best_ratio, reason, improvement, provenance=provenance)
        return "recorded_bad_pattern"
    if not tuned_legal:
        record_bad_ratio_pattern(archetype, mode, best_ratio, "illegal_tuned_deck", improvement, provenance=provenance)
        return "recorded_bad_pattern"
    if improvement <= MAX_SAFE_NEGATIVE_DELTA:
        record_bad_ratio_pattern(archetype, mode, best_ratio, "strong_negative_delta", improvement, provenance=provenance)
        return "recorded_bad_pattern"
    return "unchanged"


def summarize_benchmark(results: list[dict[str, Any]]) -> dict[str, Any]:
    improvements = [float(result.get("improvement", 0) or 0) for result in results]
    improved = [result for result in results if float(result.get("improvement", 0) or 0) > 0]
    hurt = [result for result in results if float(result.get("improvement", 0) or 0) < 0]
    warning_counter = Counter(warning for result in results for warning in result.get("tuned_quota_warnings", []))
    repair_warning_counter = Counter(warning for result in results for warning, count in result.get("common_repair_warnings", []) for _ in range(int(count or 0)))
    ratio_counter = Counter(ratio_key(result.get("best_ratio_profile", {})) for result in improved)
    weaknesses = Counter()
    for result in results:
        counts = result.get("tuned_package_counts", {})
        if int(counts.get("starters_searchers", 0) or 0) < 8:
            weaknesses["low starter/searcher count"] += 1
        if int(counts.get("extenders", 0) or 0) < 4:
            weaknesses["low extender count"] += 1
        if int(counts.get("interruptions", 0) or 0) < 6:
            weaknesses["low interruption count"] += 1
    best = max(results, key=lambda item: float(item.get("improvement", 0) or 0), default={})
    worst = min(results, key=lambda item: float(item.get("improvement", 0) or 0), default={})
    return {
        "archetype_count": len(results),
        "average_improvement": round(mean(improvements), 2) if improvements else 0,
        "best_improved_archetype": best.get("archetype"),
        "best_improvement": best.get("improvement", 0),
        "worst_improved_archetype": worst.get("archetype"),
        "worst_improvement": worst.get("improvement", 0),
        "tuning_hurt_archetypes": [result["archetype"] for result in hurt],
        "improved_archetypes": [result["archetype"] for result in improved],
        "most_reliable_ratio_patterns": ratio_counter.most_common(5),
        "common_package_weaknesses": weaknesses.most_common(10),
        "common_quota_warnings": warning_counter.most_common(10),
        "repair_success_rate": round(mean(float(result.get("repair_success_rate", 0) or 0) for result in results), 4) if results else 0,
        "average_repair_actions": round(mean(float(result.get("average_repair_actions", 0) or 0) for result in results), 2) if results else 0,
        "decks_saved_by_repair": sum(int(result.get("decks_saved_by_repair", 0) or 0) for result in results),
        "decks_completed_by_safe_filler": sum(int(result.get("decks_completed_by_safe_filler", 0) or 0) for result in results),
        "contextual_filler_usage_count": sum(int(result.get("contextual_filler_usage_count", 0) or 0) for result in results),
        "selected_filler_counts": dict(sum_counters(result.get("selected_filler_counts", {}) for result in results)),
        "filler_role_distribution": dict(sum_counters(result.get("filler_role_distribution", {}) for result in results)),
        "archetypes_relying_on_contextual_filler": [
            result.get("archetype")
            for result in results
            if int(result.get("contextual_filler_usage_count", 0) or 0) >= max(1, int(result.get("variant_count", 0) or 0) // 2)
        ],
        "filler_impact_summary": summarize_filler_impact(results),
        "decks_still_rejected": sum(1 for result in results if not result.get("tuned_legal")),
        "common_repair_warnings": repair_warning_counter.most_common(10),
        "under_40_diagnostics": [diag for result in results for diag in result.get("under_40_diagnostics", [])],
        "repair_strategy_counts": dict(sum_counters(result.get("repair_strategy_counts", {}) for result in results)),
        "advisory_bias_calibration": summarize_advisory_calibration(results),
        "memory_updates": Counter(result.get("memory_action", "unknown") for result in results),
    }


def sum_counters(groups: Any) -> Counter[str]:
    counter: Counter[str] = Counter()
    for group in groups:
        if isinstance(group, dict):
            for key, value in group.items():
                counter[str(key)] += int(value or 0)
    return counter


def summarize_advisory_calibration(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "diagnosis_bias_used_count": sum(1 for result in results if result.get("advisory_bias_calibration", {}).get("diagnosis_bias_used")),
        "diff_index_bias_used_count": sum(1 for result in results if result.get("advisory_bias_calibration", {}).get("diff_index_bias_used")),
        "bias_changed_exploration_order_count": sum(1 for result in results if result.get("advisory_bias_calibration", {}).get("bias_changed_exploration_order")),
        "signals_suppressed": sum(int(result.get("advisory_bias_calibration", {}).get("signals_suppressed", 0) or 0) for result in results),
        "signals_ignored_due_to_low_support": sum(int(result.get("advisory_bias_calibration", {}).get("signals_ignored_due_to_low_support", 0) or 0) for result in results),
        "signals_ignored_due_to_contested_history": sum(int(result.get("advisory_bias_calibration", {}).get("signals_ignored_due_to_contested_history", 0) or 0) for result in results),
    }


def summarize_filler_impact(results: list[dict[str, Any]]) -> dict[str, Any]:
    with_filler = []
    without_filler = []
    for result in results:
        impact = result.get("filler_impact_summary", {}) if isinstance(result.get("filler_impact_summary", {}), dict) else {}
        if impact.get("average_score_with_contextual_filler"):
            with_filler.append(float(impact.get("average_score_with_contextual_filler", 0) or 0))
        if impact.get("average_score_without_contextual_filler"):
            without_filler.append(float(impact.get("average_score_without_contextual_filler", 0) or 0))
    return {
        "average_score_with_contextual_filler": round(mean(with_filler), 2) if with_filler else 0,
        "average_score_without_contextual_filler": round(mean(without_filler), 2) if without_filler else 0,
        "impact_classification_counts": dict(
            sum_counters(
                (result.get("filler_impact_summary", {}).get("classification_counts", {}) for result in results)
            )
        ),
        "performance_positive_fillers": sorted(
            set(name for result in results for name in result.get("filler_impact_summary", {}).get("performance_positive_fillers", []) or [])
        ),
        "completion_only_fillers": sorted(
            set(name for result in results for name in result.get("filler_impact_summary", {}).get("completion_only_fillers", []) or [])
        ),
        "negative_fillers": sorted(
            set(name for result in results for name in result.get("filler_impact_summary", {}).get("negative_fillers", []) or [])
        ),
    }


def summarize_filler_impacts(results: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    positive: Counter[str] = Counter()
    completion: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    shared = 0
    single = 0
    indeterminate = 0
    completion_biased = Counter()
    support_failures = Counter()
    for result in results:
        for report in result.get("filler_impact_reports", []) or []:
            if report.get("attribution_shared"):
                shared += 1
            elif report.get("filler_cards"):
                single += 1
            classifications = report.get("impact_classification", {}) or {}
            for card, classification in classifications.items():
                counter[str(classification)] += 1
                if classification == "indeterminate":
                    indeterminate += 1
                if classification == "performance_positive":
                    positive[card] += 1
                elif classification == "completion_only":
                    completion[card] += 1
                elif classification in {"performance_negative", "risky"}:
                    negative[card] += 1
        for card in result.get("completion_biased_cards", []) or []:
            completion_biased[card] += 1
        for status in (result.get("filler_memory_eligibility_status", {}) or {}).values():
            for failure in status.get("failures", []) or []:
                support_failures[failure] += 1
    return {
        "classification_counts": dict(counter),
        "performance_positive_fillers": positive.most_common(10),
        "completion_only_fillers": completion.most_common(10),
        "negative_fillers": negative.most_common(10),
        "shared_attribution_events": shared,
        "single_card_attribution_events": single,
        "indeterminate_attribution_events": indeterminate,
        "completion_biased_cards": completion_biased.most_common(10),
        "support_threshold_failures": support_failures.most_common(10),
    }


def summarize_benchmark_filler_memory_influence(results: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = set()
    blocked = set()
    rejected = set()
    applied: Counter[str] = Counter()
    changed = 0
    enabled_count = 0
    before_after = []
    for result in results:
        summary = result.get("filler_memory_influence_summary", {}) if isinstance(result.get("filler_memory_influence_summary"), dict) else {}
        if result.get("filler_memory_influence_enabled"):
            enabled_count += 1
        allowed.update(summary.get("fillers_allowed_for_influence", []) or [])
        blocked.update(summary.get("fillers_blocked_from_influence", []) or [])
        rejected.update(summary.get("rejected_due_to_not_activation_ready", []) or [])
        for name, value in (summary.get("filler_memory_bias_applied", {}) or {}).items():
            applied[str(name)] += float(value or 0)
        changed += int(summary.get("influence_changed_order_count", 0) or 0)
        before_after.extend(summary.get("selection_before_after", []) or [])
    return {
        "enabled_archetype_count": enabled_count,
        "fillers_allowed_for_influence": sorted(allowed),
        "fillers_blocked_from_influence": sorted(blocked),
        "rejected_due_to_not_activation_ready": sorted(rejected),
        "filler_memory_bias_applied": {name: round(value, 6) for name, value in sorted(applied.items())},
        "influence_changed_order_count": changed,
        "selection_before_after": before_after[:20],
    }


def summarize_filler_profile(profile: dict[str, Any]) -> dict[str, Any]:
    fillers = profile.get("fillers", {}) if isinstance(profile, dict) else {}
    if not fillers:
        return {}
    return {
        name: {
            "times_used": data.get("times_used", 0),
            "positive": data.get("performance_positive_count", 0),
        "completion_only": data.get("completion_only_count", 0),
        "negative": data.get("performance_negative_count", 0),
        "indeterminate": data.get("indeterminate_count", 0),
        "attribution_confidence": data.get("average_attribution_confidence", 0),
        "completion_bias_flag": data.get("completion_bias_flag", False),
        "eligibility": data.get("eligibility", {}),
        "average_score_delta": data.get("average_score_delta", 0),
    }
        for name, data in sorted(fillers.items())[:10]
    }


def scrub_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    stats = report.get("stats", {}) if isinstance(report, dict) else {}
    quarantine = report.get("quarantine", {}) if isinstance(report, dict) else {}
    return {
        "removed_entries": int(stats.get("removed_entries", 0) or 0),
        "quarantined_archetypes": int(stats.get("quarantined_archetypes", 0) or 0),
        "quarantined_provenance_entries": int(stats.get("quarantined_provenance_entries", 0) or 0),
        "quarantined_card_entries": count_quarantined_card_entries(quarantine),
    }


def count_quarantined_card_entries(quarantine: dict[str, Any]) -> int:
    total = 0
    for card_group in ("helpful_cards", "harmful_cards"):
        group = quarantine.get(card_group, {}) if isinstance(quarantine, dict) else {}
        total += len((group.get("additions", {}) or {})) + len((group.get("removals", {}) or {}))
    return total


def ratio_key(profile: dict[str, Any]) -> str:
    if not profile:
        return "none"
    return "|".join(f"{key}:{profile[key]}" for key in sorted(profile))


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype_slug = "_".join(report["config"]["archetypes"]).lower().replace(" ", "_")
    json_path = BENCHMARK_DIR / f"{timestamp}_{archetype_slug}_{report['config']['mode']}_generic_benchmark.json"
    markdown_path = BENCHMARK_DIR / "latest_generic_benchmark_report.md"
    save_deck_diff_artifacts(report)
    save_gate_report(report.get("filler_signal_gate_report", {}) or build_filler_signal_gate_report())
    atomic_write_json(json_path, report)
    atomic_write_text(markdown_path, render_markdown(report, json_path))
    return json_path, markdown_path


def save_deck_diff_artifacts(report: dict[str, Any]) -> None:
    DECK_DIFF_DIR.mkdir(parents=True, exist_ok=True)
    for result in report.get("results", []):
        archetype = str(result.get("archetype", "unknown"))
        slug = slugify(archetype)
        baseline = {
            "score": result.get("normal_score", 0),
            "confidence": result.get("normal_confidence", 0),
            "package_counts": result.get("normal_package_counts", {}),
            "deck_sections": result.get("normal_deck_sections", {}),
            "deck_names": result.get("normal_deck_names", []),
            "repair_actions": result.get("normal_repair_actions", []),
        }
        tuned = {
            "score": result.get("tuned_score", 0),
            "confidence": result.get("tuned_confidence", 0),
            "package_counts": result.get("tuned_package_counts", {}),
            "deck_sections": result.get("tuned_deck_sections", {}),
            "deck_names": result.get("tuned_deck_names", []),
            "repair_actions": result.get("tuned_repair_actions", []),
        }
        diff = build_rich_deck_diff_report(archetype, baseline, tuned, result.get("targeted_retest", {}))
        markdown_path = DECK_DIFF_DIR / f"latest_{slug}_deck_diff.md"
        html_path = DECK_DIFF_DIR / f"latest_{slug}_deck_diff.html"
        atomic_write_text(markdown_path, diff["markdown"])
        atomic_write_text(html_path, diff["html"])
        result["deck_diff_artifacts"] = {
            "markdown": str(markdown_path),
            "html": str(html_path),
        }
        result["deck_diff_summary"] = {
            "score_delta": diff["score_summary"]["score_delta"],
            "confidence_delta": diff["score_summary"]["confidence_delta"],
            "risk_flags": diff["risk_flags"],
            "human_review_notes": diff["human_review_notes"],
        }


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Generic Archetype Benchmark",
        "",
        f"- Mode: {report['config']['mode']}",
        f"- Runs per archetype: {report['config']['runs']}",
        f"- Filler-memory influence enabled: {summary.get('filler_memory_influence_enabled', False)}",
        f"- JSON report: `{json_path}`",
        f"- Average improvement: {summary.get('average_improvement', 0)}",
        f"- Repair success rate: {summary.get('repair_success_rate', 0)}",
        f"- Decks saved by repair: {summary.get('decks_saved_by_repair', 0)}",
        f"- Decks completed by safe filler: {summary.get('decks_completed_by_safe_filler', 0)}",
        f"- Contextual filler uses: {summary.get('contextual_filler_usage_count', 0)}",
        f"- Decks still rejected: {summary.get('decks_still_rejected', 0)}",
        f"- Targeted retests: {summary.get('targeted_retest_count', 0)}",
        f"- Accepted targeted retests: {summary.get('accepted_targeted_retests', 0)}",
        f"- Diff-index bias used count: {summary.get('diff_index_bias_used_count', 0)}",
        f"- Advisory signals applied: {summary.get('advisory_signals_applied_count', 0)}",
        f"- Suppressed low-support signals: {summary.get('suppressed_low_support_signal_count', 0)}",
        f"- Contested signals: {summary.get('contested_signal_count', 0)}",
        f"- Scrub removed entries: {summary.get('scrub_report_summary', {}).get('removed_entries', 0)}",
        f"- Historical average improvement: {summary.get('historical_average_improvement', 0)}",
        f"- Recent average improvement: {summary.get('recent_average_improvement', 0)}",
        f"- Average repair reliability: {summary.get('average_repair_reliability', 0)}",
        f"- Best improved archetype: {summary.get('best_improved_archetype')} ({summary.get('best_improvement', 0)})",
        f"- Worst improved archetype: {summary.get('worst_improved_archetype')} ({summary.get('worst_improvement', 0)})",
        "",
        "## Deck Diff Artifacts",
        "",
    ]
    for result in report.get("results", []):
        artifacts = result.get("deck_diff_artifacts", {})
        if artifacts:
            lines.append(f"- {result.get('archetype')}: `{artifacts.get('markdown')}` | `{artifacts.get('html')}`")
    if not any(result.get("deck_diff_artifacts") for result in report.get("results", [])):
        lines.append("- None")
    lines.extend([
        "",
        "## Results",
        "",
    ])
    for result in report.get("results", []):
        lines.append(
            f"- {result['archetype']}: normal {result['normal_score']}, tuned {result['tuned_score']}, "
            f"delta {result['improvement']}, repair {result.get('repair_success_rate', 0)}, memory {result['memory_action']}"
        )
        if result.get("decks_completed_by_safe_filler"):
            lines.append(f"  - Completed by safe filler: {result.get('decks_completed_by_safe_filler')}")
        if result.get("contextual_filler_usage_count"):
            lines.append(
                f"  - Contextual filler used {result.get('contextual_filler_usage_count')} times; "
                f"top fillers: {format_counter_rows(Counter(result.get('selected_filler_counts', {})).most_common(5))}"
            )
        for diag in result.get("under_40_diagnostics", [])[:2]:
            lines.append(
                f"  - Under-40 diagnostic: {diag.get('under_40_reason')} missing {diag.get('missing_count')} "
                f"strategy {diag.get('recommended_repair_strategy')}"
            )
        for warning in result.get("diff_index_warnings", [])[:3]:
            lines.append(f"  - {warning}")
        if result.get("diff_index_bias_used"):
            budget = result.get("advisory_budget_used", {})
            lines.append(f"  - Diff-index advisory bias used; budget: {budget}")
        if result.get("contested_signals"):
            lines.append(f"  - Contested diff-index signals suppressed: {len(result.get('contested_signals', []))}")
    lines.extend(
        [
            "",
            "## Under-40 Repair Diagnostics",
            "",
            f"- Decks completed by safe filler: {summary.get('decks_completed_by_safe_filler', 0)}",
            f"- Decks still rejected: {summary.get('decks_still_rejected', 0)}",
            f"- Repair strategies: {summary.get('repair_strategy_counts', {})}",
        ]
    )
    diagnostics = summary.get("under_40_diagnostics", []) or []
    if diagnostics:
        for diag in diagnostics[:8]:
            lines.append(
                f"- {diag.get('under_40_reason')}: missing {diag.get('missing_count')}, "
                f"fillers {diag.get('available_fillers', {})}, strategy {diag.get('recommended_repair_strategy')}"
            )
    else:
        lines.append("- No unresolved under-40 diagnostics.")
    calibration = summary.get("advisory_bias_calibration", {})
    lines.extend(
        [
            "",
            "## Contextual Filler Selection",
            "",
            f"- Contextual filler uses: {summary.get('contextual_filler_usage_count', 0)}",
        f"- Top selected fillers: {format_counter_rows(Counter(summary.get('selected_filler_counts', {})).most_common(8))}",
        f"- Filler role distribution: {format_counter_rows(Counter(summary.get('filler_role_distribution', {})).most_common(8))}",
        f"- Filler impact: {summary.get('filler_impact_summary', {})}",
        f"- Filler impact classifications: {summary.get('filler_impact_classification_summary', {})}",
        f"- Filler memory cross-archetype signals: {summary.get('filler_memory_cross_archetype_index_size', 0)}",
        f"- Filler memory concentration warnings: {summary.get('filler_memory_concentration_warnings', [])[:5]}",
            f"- Filler signal eligibility: {summary.get('filler_signal_eligibility_summary', {})}",
            f"- Filler-memory influence: {summary.get('filler_memory_influence', {})}",
            f"- Archetypes relying heavily on filler: {', '.join(summary.get('archetypes_relying_on_contextual_filler', []) or ['none'])}",
        ]
    )
    for result in report.get("results", []):
        if result.get("best_selected_fillers"):
            lines.append(f"- {result.get('archetype')} best-run fillers: {', '.join(result.get('best_selected_fillers', [])[:8])}")
            if result.get("best_filler_impact"):
                lines.append(f"  - Impact: {result.get('best_filler_impact', {}).get('impact_classification', {})}")
            if result.get("filler_memory_update"):
                lines.append(f"  - Filler memory: {result.get('filler_memory_update')}")
            if result.get("completion_biased_cards"):
                lines.append(f"  - Completion-biased cards: {', '.join(result.get('completion_biased_cards', [])[:5])}")
            for reason in result.get("best_filler_reasons", [])[:2]:
                lines.append(f"  - {reason}")
    gate_summary = summary.get("filler_signal_eligibility_summary", {}) or {}
    lines.extend(
        [
            "",
            "## Filler Signal Gates",
            "",
            f"- Eligible signals: {gate_summary.get('eligible_count', 0)}",
            f"- Near-eligible signals: {gate_summary.get('near_eligible_count', 0)}",
            f"- Failed signals: {gate_summary.get('failed_count', 0)}",
            f"- Cards closest to eligibility: {', '.join(gate_summary.get('cards_closest_to_eligibility', []) or ['none'])}",
            f"- Blocked by concentration: {', '.join(gate_summary.get('cards_blocked_by_concentration', []) or ['none'])}",
            f"- Blocked by attribution: {', '.join(gate_summary.get('cards_blocked_by_attribution', []) or ['none'])}",
            f"- Blocked by support: {', '.join(gate_summary.get('cards_blocked_by_support', []) or ['none'])}",
        ]
    )
    lines.extend(
        [
            "",
            "## Advisory Bias Calibration",
            "",
            f"- Diagnosis bias used count: {calibration.get('diagnosis_bias_used_count', 0)}",
            f"- Diff-index bias used count: {calibration.get('diff_index_bias_used_count', 0)}",
            f"- Bias changed exploration order count: {calibration.get('bias_changed_exploration_order_count', 0)}",
            f"- Signals suppressed: {calibration.get('signals_suppressed', 0)}",
            f"- Low-support signals ignored: {calibration.get('signals_ignored_due_to_low_support', 0)}",
            f"- Contested signals ignored: {calibration.get('signals_ignored_due_to_contested_history', 0)}",
        ]
    )
    lines.extend(["", "## Tuning Hurt Archetypes", ""])
    hurt = summary.get("tuning_hurt_archetypes", [])
    lines.extend(f"- {archetype}" for archetype in hurt) if hurt else lines.append("- None")
    lines.extend(["", "## Historical Trends", "", "| Archetype | Runs | Avg Improvement | Trend | Repair Reliability | Rejected |", "|---|---:|---:|---|---:|---:|"])
    history = report.get("benchmark_history", {}).get("profiles", {})
    for archetype, profile in sorted(history.items()):
        lines.append(
            f"| {archetype} | {profile.get('total_benchmark_runs', 0)} | {profile.get('average_improvement', 0)} | "
            f"{profile.get('trend_direction', 'stable')} | {profile.get('repair_reliability', 0)} | {profile.get('rejected_deck_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Trend Diagnosis",
            "",
            "| Archetype | Severity | Diagnosis | Suspected Causes | Recommended Adjustments |",
            "|---|---|---|---|---|",
        ]
    )
    for archetype, profile in sorted(history.items()):
        diagnosis = profile.get("latest_diagnosis", {}) if isinstance(profile, dict) else {}
        causes = ", ".join(diagnosis.get("suspected_causes", []) or ["none"])
        adjustments = "; ".join(diagnosis.get("recommended_adjustments", [])[:3] or ["none"])
        lines.append(
            f"| {archetype} | {diagnosis.get('severity', 'unknown')} | {diagnosis.get('diagnosis', 'No diagnosis available.')} | {causes} | {adjustments} |"
        )
    lines.extend(
        [
            "",
            "## Targeted Retests",
            "",
            "| Archetype | Tested | Accepted | Improvement | Accepted Ratio | Rejected |",
            "|---|---:|---|---:|---|---:|",
        ]
    )
    for result in report.get("results", []):
        retest = result.get("targeted_retest", {})
        accepted = retest.get("accepted_recommendation") or {}
        ratio = ratio_key(accepted.get("ratio_profile", {})) if accepted else "none"
        lines.append(
            f"| {result.get('archetype')} | {retest.get('tested_recommendations', 0)} | "
            f"{'yes' if accepted else 'no'} | {retest.get('improvement', 0)} | {ratio} | "
            f"{len(retest.get('rejected_recommendations', []) or [])} |"
        )
    shift_summary = summary.get("card_shift_summary", {})
    replay_summary = summary.get("package_replay_summary", {})
    lines.extend(
        [
            "",
            "## Card Shift Summary",
            "",
            f"- Accepted card-shift explanations: {shift_summary.get('accepted_shift_count', 0)}",
            f"- Rejected card-shift explanations: {shift_summary.get('rejected_shift_count', 0)}",
            f"- Most common harmful additions: {format_counter_rows(shift_summary.get('most_common_harmful_additions', []))}",
            f"- Most common harmful removals: {format_counter_rows(shift_summary.get('most_common_harmful_removals', []))}",
            f"- Most common helpful additions: {format_counter_rows(shift_summary.get('most_common_helpful_additions', []))}",
            f"- Most common helpful removals: {format_counter_rows(shift_summary.get('most_common_helpful_removals', []))}",
            f"- Package movement summary: {format_counter_rows(shift_summary.get('package_movement_summary', []))}",
            f"- Replay package deltas: {format_counter_rows(replay_summary.get('package_delta_counts', []))}",
            f"- Replay risk flags: {format_counter_rows(replay_summary.get('risk_flag_counts', []))}",
            "",
            "## Cross-Archetype Diff Index",
            "",
            f"- Top Helpful Additions: {format_index_rows(summary.get('diff_index_summary', {}).get('top_helpful_additions', []))}",
            f"- Top Harmful Additions: {format_index_rows(summary.get('diff_index_summary', {}).get('top_harmful_additions', []))}",
            f"- Top Helpful Removals: {format_index_rows(summary.get('diff_index_summary', {}).get('top_helpful_removals', []))}",
            f"- Top Harmful Removals: {format_index_rows(summary.get('diff_index_summary', {}).get('top_harmful_removals', []))}",
            f"- Top Helpful Package Movements: {format_index_rows(summary.get('diff_index_summary', {}).get('top_helpful_package_movements', []))}",
            f"- Top Harmful Package Movements: {format_index_rows(summary.get('diff_index_summary', {}).get('top_harmful_package_movements', []))}",
            f"- Common Risk Flags: {format_index_rows(summary.get('diff_index_summary', {}).get('common_risk_flags', []))}",
            f"- Archetypes Needing Review: {', '.join(summary.get('diff_index_summary', {}).get('archetypes_needing_review', []) or ['none'])}",
            "",
            "## Accepted Card Shifts",
            "",
        ]
    )
    accepted_lines = 0
    for result in report.get("results", []):
        accepted = (result.get("targeted_retest", {}).get("accepted_recommendation") or {})
        shift = accepted.get("card_shift_explanation", {}) if isinstance(accepted, dict) else {}
        if shift:
            accepted_lines += 1
            lines.append(f"- {result.get('archetype')}: {shift.get('explanation', 'No explanation available.')}")
    if not accepted_lines:
        lines.append("- None")
    lines.extend(["", "## Rejected Card Shifts", ""])
    rejected_lines = 0
    for result in report.get("results", []):
        for rejected in result.get("targeted_retest", {}).get("rejected_recommendations", []) or []:
            shift = rejected.get("card_shift_explanation", {})
            if shift:
                rejected_lines += 1
                lines.append(f"- {result.get('archetype')}: {shift.get('explanation', 'No explanation available.')}")
                if rejected_lines >= 8:
                    break
        if rejected_lines >= 8:
            break
    if not rejected_lines:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Before/After Package Replay",
            "",
            "### Accepted Replay Sections",
            "",
        ]
    )
    accepted_replays = 0
    for result in report.get("results", []):
        replay = (result.get("targeted_retest", {}).get("accepted_recommendation") or {}).get("package_replay_report", {})
        if replay:
            accepted_replays += 1
            lines.append(replay.get("markdown_section", ""))
            lines.append("")
    if not accepted_replays:
        lines.append("- None")
    lines.extend(["", "### Rejected Replay Sections", ""])
    rejected_replays = 0
    for result in report.get("results", []):
        for rejected in result.get("targeted_retest", {}).get("rejected_recommendations", []) or []:
            replay = rejected.get("package_replay_report", {})
            if replay:
                rejected_replays += 1
                lines.append(replay.get("markdown_section", ""))
                lines.append("")
                if rejected_replays >= 6:
                    break
        if rejected_replays >= 6:
            break
    if not rejected_replays:
        lines.append("- None")
    lines.extend(["", "### Compact Card-Delta Table", "", "| Archetype | Card | Delta | Change |", "|---|---|---:|---|"])
    table_rows = 0
    for result in report.get("results", []):
        for replay in iter_result_replays(result):
            for row in replay.get("compact_card_delta_table", [])[:8]:
                table_rows += 1
                lines.append(f"| {result.get('archetype')} | {row.get('card')} | {int(row.get('delta', 0)):+d} | {row.get('change')} |")
                if table_rows >= 20:
                    break
            if table_rows >= 20:
                break
        if table_rows >= 20:
            break
    if not table_rows:
        lines.append("| None | None | 0 | no change |")
    lines.extend(["", "## Long-Term Leaders", ""])
    best_long = report.get("benchmark_history", {}).get("best_long_term_archetypes", [])
    lines.extend(f"- {name}: {value}" for name, value in best_long) if best_long else lines.append("- None")
    lines.extend(["", "## Follow-Up Archetypes", ""])
    follow_up = report.get("benchmark_history", {}).get("recommended_follow_up_archetypes", [])
    lines.extend(f"- {name}" for name in follow_up) if follow_up else lines.append("- None")
    return "\n".join(lines) + "\n"


def average_repair_actions(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return round(mean(len(result.get("repair_actions", [])) for result in results), 2)


def format_counter_rows(rows: Any) -> str:
    if not rows:
        return "none"
    return ", ".join(f"{name} ({count})" for name, count in rows[:5])


def format_index_rows(rows: Any) -> str:
    if not rows:
        return "none"
    formatted = []
    for row in rows[:5]:
        if isinstance(row, dict):
            formatted.append(f"{row.get('name')} ({row.get('count', 0)})")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            formatted.append(f"{row[0]} ({row[1]})")
        else:
            formatted.append(str(row))
    return ", ".join(formatted)


def iter_result_replays(result: dict[str, Any]) -> list[dict[str, Any]]:
    replays = []
    accepted = (result.get("targeted_retest", {}).get("accepted_recommendation") or {}).get("package_replay_report", {})
    if accepted:
        replays.append(accepted)
    for rejected in result.get("targeted_retest", {}).get("rejected_recommendations", []) or []:
        replay = rejected.get("package_replay_report", {})
        if replay:
            replays.append(replay)
    return replays


def print_replay_console(report: dict[str, Any]) -> None:
    print("\nPackage Replay Preview")
    for result in report.get("results", []):
        printed = 0
        for replay in iter_result_replays(result):
            printed += 1
            print(f"\n[{result.get('archetype')}] score delta {replay.get('score_delta', 0)}")
            print(f"Main: {replay.get('before_main_count', 0)} -> {replay.get('after_main_count', 0)} | Extra: {replay.get('before_extra_count', 0)} -> {replay.get('after_extra_count', 0)}")
            package_delta = replay.get("package_gains_losses", {})
            print(f"Package delta: {package_delta or 'none'}")
            first_rows = replay.get("compact_card_delta_table", [])[:5]
            print("Card delta:", ", ".join(f"{row.get('card')} {int(row.get('delta', 0)):+d}" for row in first_rows) or "none")
            if printed >= 2:
                break


def deck_sections(main: list[dict[str, Any]], extra: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {"main": card_names(main), "extra": card_names(extra)}


def card_names(cards: list[dict[str, Any]]) -> list[str]:
    return [str(card.get("name", "")) for card in cards if card.get("name")]


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "unknown"


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")
    report = run_benchmark(
        args.archetypes,
        mode=args.mode,
        runs=args.runs,
        show_replay=args.show_replay,
        enable_filler_memory_influence=args.enable_filler_memory_influence,
    )
    json_path, markdown_path = save_reports(report)
    print("\nGeneric Archetype Benchmark Complete")
    print(f"Archetypes tested: {report['summary']['archetype_count']}")
    print(f"Average improvement: {report['summary']['average_improvement']}")
    print(f"Filler-memory influence enabled: {report['summary'].get('filler_memory_influence_enabled', False)}")
    print(f"Filler-memory influence summary: {report['summary'].get('filler_memory_influence', {})}")
    print(f"Repair success rate: {report['summary']['repair_success_rate']}")
    print(f"Decks saved by repair: {report['summary']['decks_saved_by_repair']}")
    print(f"Decks completed by safe filler: {report['summary'].get('decks_completed_by_safe_filler', 0)}")
    print(f"Contextual filler uses: {report['summary'].get('contextual_filler_usage_count', 0)}")
    print(f"Top contextual fillers: {Counter(report['summary'].get('selected_filler_counts', {})).most_common(5)}")
    print(f"Filler impact classifications: {report['summary'].get('filler_impact_classification_summary', {})}")
    print(f"Filler concentration warnings: {report['summary'].get('filler_memory_concentration_warnings', [])[:3]}")
    gate_summary = report["summary"].get("filler_signal_eligibility_summary", {}) or {}
    print(f"Filler signal eligible count: {gate_summary.get('eligible_count', 0)}")
    print(f"Filler signals closest to eligibility: {gate_summary.get('cards_closest_to_eligibility', [])[:5]}")
    print(f"Decks still rejected: {report['summary']['decks_still_rejected']}")
    print(f"Advisory calibration: {report['summary'].get('advisory_bias_calibration', {})}")
    print(f"Targeted retests: {report['summary'].get('targeted_retest_count', 0)}")
    print(f"Accepted targeted retests: {report['summary'].get('accepted_targeted_retests', 0)}")
    print(f"Historical average improvement: {report['summary'].get('historical_average_improvement', 0)}")
    print(f"Recent improvement: {report['summary'].get('recent_average_improvement', 0)}")
    print(f"Repair reliability: {report['summary'].get('average_repair_reliability', 0)}")
    for archetype, profile in sorted(report.get("benchmark_history", {}).get("profiles", {}).items()):
        print(f"- {archetype}: trend {profile.get('trend_direction')}, historical avg {profile.get('average_improvement')}")
        diagnosis = profile.get("latest_diagnosis", {})
        if diagnosis:
            print(f"  diagnosis: {diagnosis.get('severity')} - {diagnosis.get('diagnosis')}")
    for result in report.get("results", []):
        retest = result.get("targeted_retest", {})
        if retest.get("targeted_retest_used"):
            accepted = retest.get("accepted_recommendation")
            print(
                f"- {result['archetype']} targeted retest: tested {retest.get('tested_recommendations', 0)}, "
                f"accepted {'yes' if accepted else 'no'}, delta {retest.get('improvement', 0)}"
            )
    if args.show_replay:
        print_replay_console(report)
    attention = report["summary"].get("recommended_follow_up_archetypes", [])
    print(f"Needs attention: {', '.join(attention) or 'none'}")
    print(f"Best improved archetype: {report['summary']['best_improved_archetype']} ({report['summary']['best_improvement']})")
    print(f"Worst improved archetype: {report['summary']['worst_improved_archetype']} ({report['summary']['worst_improvement']})")
    print(f"Tuning hurt: {', '.join(report['summary']['tuning_hurt_archetypes']) or 'none'}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
