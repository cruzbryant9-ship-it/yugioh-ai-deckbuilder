from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from deck.advisory_influence_budget import AdvisoryInfluenceBudget
from deck.builder import score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_benchmark_memory import load_generic_benchmark_history
from deck.generic_combo_skeleton import infer_combo_skeletons
from deck.generic_deck_builder import GENERIC_QUOTAS, build_generic_deck
from deck.generic_diff_index import get_diff_index_advisory_signal
from deck.generic_filler_impact import analyze_filler_impact
from deck.generic_ratio_memory import record_bad_ratio_pattern, save_generic_ratio_memory


def tune_generic_deck(
    archetype: str,
    card_pool: list[dict[str, Any]],
    mode: str = "meta",
    runs: int = 20,
    update_memory: bool = True,
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    runs = max(1, int(runs))
    diagnosis = load_tuning_diagnosis(archetype, mode)
    diagnosis_bias = diagnosis_to_ratio_bias(diagnosis)
    ratio_profiles = generate_ratio_profiles(mode, runs, diagnosis)
    advisory_budget = AdvisoryInfluenceBudget()
    diagnosis_nudge = advisory_budget.apply("diagnosis", 0.05 if diagnosis_bias else 0.0)
    baseline_deck, _baseline_report = build_generic_deck(archetype, card_pool, mode=mode, use_ratio_memory=True)
    results = []
    for index, ratio_profile in enumerate(ratio_profiles[:runs], start=1):
        deck, build_report = build_generic_deck(
            archetype,
            card_pool,
            mode=mode,
            ratio_profile=ratio_profile,
            use_ratio_memory=False,
            enable_filler_memory_influence=enable_filler_memory_influence,
        )
        main, extra = split_deck(deck)
        blocked = blocked_card_violations(deck)
        legal = deck_is_legal(main, extra, blocked, build_report)
        fallback_used = False
        failed_ratio_profile: dict[str, int] | None = None
        if not legal:
            failed_ratio_profile = ratio_profile
            fallback_deck, fallback_report = build_generic_deck(
                archetype,
                card_pool,
                mode=mode,
                ratio_profile=safe_fallback_profile(mode),
                use_ratio_memory=False,
                enable_filler_memory_influence=enable_filler_memory_influence,
            )
            fallback_main, fallback_extra = split_deck(fallback_deck)
            fallback_blocked = blocked_card_violations(fallback_deck)
            if deck_is_legal(fallback_main, fallback_extra, fallback_blocked, fallback_report):
                deck = fallback_deck
                build_report = fallback_report
                ratio_profile = fallback_report.get("ratio_profile", safe_fallback_profile(mode))
                main, extra = fallback_main, fallback_extra
                blocked = fallback_blocked
                legal = True
                fallback_used = True
            elif update_memory:
                record_bad_ratio_pattern(archetype, mode, failed_ratio_profile, "repair_failed", 0.0)
        movements = card_movements(baseline_deck, deck)
        advisory_signal = get_diff_index_advisory_signal(archetype, movements)
        diff_index_nudge = advisory_budget.apply("diff_index", advisory_signal.get("capped_signal", 0))
        breakdown = score_deck_breakdown(deck, archetype, mode)
        filler_impact = build_filler_impact(archetype, mode, deck, extra, build_report, breakdown, legal, blocked)
        results.append(
            {
                "run": index,
                "score": breakdown["final_score"],
                "legal": legal,
                "main_count": len(main),
                "extra_count": len(extra),
                "ratio_profile": ratio_profile,
                "package_counts": build_report.get("package_counts", {}),
                "confidence": build_report.get("generic_confidence_score", 0),
                "combo_skeleton_count": build_report.get("combo_skeleton_count", 0),
                "quota_warnings": build_report.get("quota_warnings", []),
                "blocked_card_violations": blocked,
                "repair_used": build_report.get("repair_used", False),
                "repair_success": build_report.get("repair_success", False),
                "repair_actions": build_report.get("repair_actions", []),
                "repair_failure_cause": build_report.get("repair_failure_cause"),
                "repair_strategy_used": build_report.get("repair_strategy_used"),
                "safe_filler_used_count": build_report.get("safe_filler_used_count", 0),
                "completed_by_safe_filler": build_report.get("completed_by_safe_filler", False),
                "contextual_filler_used": build_report.get("contextual_filler_used", False),
                "selected_fillers": build_report.get("selected_fillers", []),
                "filler_reasons": build_report.get("filler_reasons", []),
                "filler_roles": build_report.get("filler_roles", {"counts": {}, "by_card": {}}),
                "filler_context_scores": build_report.get("filler_context_scores", {}),
                "filler_memory_influence": build_report.get("filler_memory_influence", {}),
                "rejected_filler_reasons": build_report.get("rejected_filler_reasons", []),
                "pre_contextual_filler_main_count": build_report.get("pre_contextual_filler_main_count", len(main)),
                "pre_contextual_filler_package_counts": build_report.get("pre_contextual_filler_package_counts", {}),
                "filler_impact": filler_impact,
                "under_40_diagnostics": build_report.get("under_40_diagnostics", {}),
                "remaining_warnings": build_report.get("remaining_warnings", []),
                "fallback_used": fallback_used,
                "failed_ratio_profile": failed_ratio_profile,
                "candidate_card_movements": movements,
                "diff_index_advisory_signal": advisory_signal,
                "diff_index_advisory_nudge": diff_index_nudge,
                "deck": deck,
            }
        )
    legal_results = [result for result in results if result["legal"]]
    candidates = legal_results or results
    best = max(candidates, key=candidate_selection_key)
    best_by_score_only = max(candidates, key=lambda result: (float(result.get("score", 0) or 0), float(result.get("confidence", 0) or 0)))
    bias_changed_order = best is not best_by_score_only and float(best.get("score", 0) or 0) == float(best_by_score_only.get("score", 0) or 0)
    best_deck = best.pop("deck")
    result_rows = [{key: value for key, value in result.items() if key != "deck"} for result in results]
    scores = [float(result.get("score", 0) or 0) for result in result_rows]
    skeletons = infer_combo_skeletons(card_pool, archetype)
    report = {
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "variant_count": len(result_rows),
        "legal_variant_count": len(legal_results),
        "best_score": round(float(best.get("score", 0) or 0), 2),
        "average_score": round(mean(scores), 2) if scores else 0,
        "best_result": best,
        "results": result_rows,
        "best_deck": best_deck,
        "combo_skeleton_coverage": skeletons.get("skeleton_count", 0),
        "repair_success_rate": round(mean(1.0 if result.get("repair_success") else 0.0 for result in result_rows), 4) if result_rows else 0,
        "decks_saved_by_repair": sum(1 for result in result_rows if result.get("repair_used") and result.get("legal")),
        "decks_completed_by_safe_filler": sum(1 for result in result_rows if result.get("completed_by_safe_filler")),
        "contextual_filler_usage_count": sum(1 for result in result_rows if result.get("contextual_filler_used")),
        "selected_filler_counts": dict(Counter(name for result in result_rows for name in result.get("selected_fillers", []) or [])),
        "filler_role_distribution": dict(
            Counter(
                role
                for result in result_rows
                for role, amount in (result.get("filler_roles", {}).get("counts", {}) or {}).items()
                for _ in range(int(amount or 0))
            )
        ),
        "filler_impact_summary": {
            "average_score_with_contextual_filler": average_score_by_filler_usage(result_rows, True),
            "average_score_without_contextual_filler": average_score_by_filler_usage(result_rows, False),
            "classification_counts": filler_impact_classification_counts(result_rows),
            "performance_positive_fillers": sorted(set(name for result in result_rows for name in result.get("filler_impact", {}).get("performance_positive_fillers", []) or [])),
            "completion_only_fillers": sorted(set(name for result in result_rows for name in result.get("filler_impact", {}).get("completion_only_fillers", []) or [])),
            "negative_fillers": sorted(set(name for result in result_rows for name in result.get("filler_impact", {}).get("negative_fillers", []) or [])),
        },
        "filler_impact_reports": [result.get("filler_impact", {}) for result in result_rows if result.get("filler_impact", {}).get("filler_cards")],
        "fallback_used_count": sum(1 for result in result_rows if result.get("fallback_used")),
        "common_repair_warnings": common_repair_warnings(result_rows),
        "under_40_diagnostics": [
            result.get("under_40_diagnostics", {})
            for result in result_rows
            if result.get("under_40_diagnostics", {}).get("missing_count", 0)
        ],
        "repair_strategy_counts": dict(Counter(str(result.get("repair_strategy_used") or "unknown") for result in result_rows)),
        "memory_updated": False,
        "diagnosis_influenced_tuning": bool(diagnosis_bias),
        "diagnosis_bias": diagnosis_bias,
        "diagnosis_advisory_nudge": diagnosis_nudge,
        "diagnosis": diagnosis,
        "diff_index_bias_used": any(abs(float(result.get("diff_index_advisory_nudge", 0) or 0)) > 0 for result in result_rows),
        "advisory_budget_used": advisory_budget.summary(),
        "advisory_signals_applied": [
            {
                "run": result.get("run"),
                "nudge": result.get("diff_index_advisory_nudge", 0),
                "hints": result.get("diff_index_advisory_signal", {}).get("hints", []),
            }
            for result in result_rows
            if abs(float(result.get("diff_index_advisory_nudge", 0) or 0)) > 0
        ],
        "suppressed_low_support_signals": collect_signal_rows(result_rows, "suppressed_low_support_signals"),
        "contested_signals": collect_signal_rows(result_rows, "contested_signals"),
        "advisory_bias_calibration": {
            "advisory_budget_available": advisory_budget.summary().get("remaining", 0),
            "advisory_budget_used": advisory_budget.summary().get("used_by_source", {}),
            "diagnosis_bias_used": bool(diagnosis_bias),
            "diff_index_bias_used": any(abs(float(result.get("diff_index_advisory_nudge", 0) or 0)) > 0 for result in result_rows),
            "signals_suppressed": len(collect_signal_rows(result_rows, "suppressed_low_support_signals")) + len(collect_signal_rows(result_rows, "contested_signals")),
            "signals_ignored_due_to_low_support": len(collect_signal_rows(result_rows, "suppressed_low_support_signals")),
            "signals_ignored_due_to_contested_history": len(collect_signal_rows(result_rows, "contested_signals")),
            "bias_changed_exploration_order": bias_changed_order,
        },
        "filler_memory_influence_enabled": bool(enable_filler_memory_influence),
        "filler_memory_influence_summary": summarize_filler_memory_influence(result_rows),
    }
    if update_memory and best.get("legal"):
        memory = save_generic_ratio_memory(archetype, mode, report)
        report["memory_updated"] = True
        report["ratio_memory_summary"] = {
            "best_package_ratios": memory.get("best_package_ratios", {}),
            "best_score": memory.get("best_score", 0),
            "last_best_score": memory.get("last_best_score", 0),
            "best_balance": memory.get("best_balance", {}),
        }
    return report


def generate_ratio_profiles(mode: str, runs: int, diagnosis: dict[str, Any] | None = None) -> list[dict[str, int]]:
    base = dict(GENERIC_QUOTAS.get(mode, GENERIC_QUOTAS["meta"]))
    bias = diagnosis_to_ratio_bias(diagnosis or {})
    if bias:
        base = apply_ratio_bias(base, bias)
    profiles = [base]
    variants = [
        {"starters_searchers": 2, "extenders": -1, "interruptions": 1},
        {"starters_searchers": -1, "extenders": 2, "payoffs": 1},
        {"interruptions": 3, "board_breakers": 1, "payoffs": -1},
        {"board_breakers": 3, "interruptions": -2, "extenders": 1},
        {"payoffs": 2, "recovery": 1, "max_bricks": 1},
        {"starters_searchers": 1, "extenders": 1, "recovery": 1},
        {"starters_searchers": -2, "interruptions": 2, "board_breakers": 2},
        {"extenders": 3, "max_bricks": -1, "payoffs": -1},
    ]
    if bias:
        variants.insert(0, bias)
        if "repair_dependency_high" in set((diagnosis or {}).get("suspected_causes", [])):
            variants.insert(1, {"starters_searchers": 1, "extenders": 1, "payoffs": -1, "max_bricks": -1})
    index = 0
    while len(profiles) < runs:
        profile = dict(base)
        adjustment = variants[index % len(variants)]
        wave = index // len(variants)
        for key, delta in adjustment.items():
            profile[key] = bounded_value(key, profile.get(key, 0) + delta + (1 if wave and key in {"starters_searchers", "extenders"} else 0))
        profiles.append(profile)
        index += 1
    return profiles


def card_movements(baseline_deck: list[dict[str, Any]], candidate_deck: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    baseline = Counter(card_name(card) for card in baseline_deck)
    candidate = Counter(card_name(card) for card in candidate_deck)
    names = sorted(set(baseline) | set(candidate))
    increases = {name: candidate[name] - baseline[name] for name in names if candidate[name] > baseline[name]}
    decreases = {name: baseline[name] - candidate[name] for name in names if baseline[name] > candidate[name]}
    return {"copy_increases": increases, "copy_decreases": decreases}


def candidate_selection_key(result: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(result.get("score", 0) or 0),
        float(result.get("diff_index_advisory_nudge", 0) or 0),
        float(result.get("confidence", 0) or 0),
    )


def card_name(card: Any) -> str:
    return str(card.get("name", card)) if isinstance(card, dict) else str(card)


def collect_signal_rows(results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for result in results:
        for row in result.get("diff_index_advisory_signal", {}).get(key, []) or []:
            marker = tuple(sorted((str(k), str(v)) for k, v in row.items()))
            if marker in seen:
                continue
            seen.add(marker)
            rows.append(row)
    return rows[:50]


def summarize_filler_memory_influence(results: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = set()
    blocked = set()
    rejected = set()
    applied: Counter[str] = Counter()
    changed_order = 0
    before_after = []
    enabled_count = 0
    for result in results:
        state = result.get("filler_memory_influence", {}) if isinstance(result.get("filler_memory_influence"), dict) else {}
        if state.get("enabled"):
            enabled_count += 1
        allowed.update(state.get("fillers_allowed_for_influence", []) or [])
        blocked.update(state.get("fillers_blocked_from_influence", []) or [])
        rejected.update(state.get("rejected_due_to_not_activation_ready", []) or [])
        for name, value in (state.get("filler_memory_bias_applied", {}) or {}).items():
            applied[str(name)] += float(value or 0)
        if state.get("influence_changed_order"):
            changed_order += 1
        if state.get("selected_filler_before_bias") or state.get("selected_filler_after_bias"):
            before_after.append(
                {
                    "run": result.get("run"),
                    "before": state.get("selected_filler_before_bias"),
                    "after": state.get("selected_filler_after_bias"),
                    "changed": bool(state.get("influence_changed_order")),
                }
            )
    return {
        "enabled_variant_count": enabled_count,
        "fillers_allowed_for_influence": sorted(allowed),
        "fillers_blocked_from_influence": sorted(blocked),
        "rejected_due_to_not_activation_ready": sorted(rejected),
        "filler_memory_bias_applied": {name: round(value, 6) for name, value in sorted(applied.items())},
        "influence_changed_order_count": changed_order,
        "selection_before_after": before_after[:20],
    }


def load_tuning_diagnosis(archetype: str, mode: str) -> dict[str, Any]:
    try:
        profile = load_generic_benchmark_history(archetype, mode)
    except Exception:
        return {}
    diagnosis = profile.get("latest_diagnosis", {}) if isinstance(profile, dict) else {}
    return diagnosis if isinstance(diagnosis, dict) else {}


def diagnosis_to_ratio_bias(diagnosis: dict[str, Any]) -> dict[str, int]:
    causes = set(diagnosis.get("suspected_causes", [])) if isinstance(diagnosis, dict) else set()
    bias: dict[str, int] = {}
    if "starter_density_low" in causes:
        bias["starters_searchers"] = bias.get("starters_searchers", 0) + 1
    if "extender_shortage" in causes:
        bias["extenders"] = bias.get("extenders", 0) + 1
    if "payoff_overfill" in causes:
        bias["payoffs"] = bias.get("payoffs", 0) - 1
    if "brick_pressure_high" in causes:
        bias["max_bricks"] = bias.get("max_bricks", 0) - 1
    if "interruption_shortage" in causes:
        bias["interruptions"] = bias.get("interruptions", 0) + 1
    if "board_breaker_overfill" in causes:
        bias["board_breakers"] = bias.get("board_breakers", 0) - 1
    if "repair_dependency_high" in causes:
        bias["starters_searchers"] = bias.get("starters_searchers", 0) + 1
        bias["extenders"] = bias.get("extenders", 0) + 1
        bias["payoffs"] = bias.get("payoffs", 0) - 1
        bias["max_bricks"] = bias.get("max_bricks", 0) - 1
    if "quota_instability" in causes or "ratio_overfitting" in causes:
        bias["max_bricks"] = bias.get("max_bricks", 0) - 1
    return {key: max(-2, min(2, value)) for key, value in bias.items() if value}


def apply_ratio_bias(profile: dict[str, int], bias: dict[str, int]) -> dict[str, int]:
    adjusted = dict(profile)
    for key, delta in bias.items():
        adjusted[key] = bounded_value(key, adjusted.get(key, 0) + delta)
    return adjusted


def bounded_value(key: str, value: int) -> int:
    if key == "max_bricks":
        return max(2, min(6, value))
    return max(0, min(16, value))


def safe_fallback_profile(mode: str) -> dict[str, int]:
    base = dict(GENERIC_QUOTAS.get(mode, GENERIC_QUOTAS["meta"]))
    base.update(
        {
            "starters_searchers": max(base.get("starters_searchers", 10), 14),
            "extenders": max(base.get("extenders", 6), 9),
            "interruptions": max(base.get("interruptions", 6), 10),
            "board_breakers": max(base.get("board_breakers", 2), 3),
            "payoffs": min(base.get("payoffs", 3), 3),
            "max_bricks": min(base.get("max_bricks", 4), 3),
        }
    )
    return base


def deck_is_legal(main: list[dict[str, Any]], extra: list[dict[str, Any]], blocked: list[str], build_report: dict[str, Any]) -> bool:
    hard_terms = ("blocked card", "copy limit exceeded", "main deck below", "main deck above", "Extra Deck above")
    warnings = list(build_report.get("remaining_warnings", [])) + list(build_report.get("quota_warnings", []))
    return len(main) == 40 and len(extra) <= 15 and not blocked and not any(any(term in warning for term in hard_terms) for warning in warnings)


def common_repair_warnings(results: list[dict[str, Any]]) -> list[tuple[str, int]]:
    from collections import Counter

    counter = Counter(warning for result in results for warning in result.get("remaining_warnings", []))
    return counter.most_common(10)


def average_score_by_filler_usage(results: list[dict[str, Any]], used: bool) -> float:
    rows = [float(result.get("score", 0) or 0) for result in results if bool(result.get("contextual_filler_used")) is used]
    return round(mean(rows), 2) if rows else 0.0


def build_filler_impact(
    archetype: str,
    mode: str,
    deck: list[dict[str, Any]],
    extra: list[dict[str, Any]],
    build_report: dict[str, Any],
    breakdown: dict[str, Any],
    legal: bool,
    blocked: list[str],
) -> dict[str, Any]:
    if not build_report.get("contextual_filler_used"):
        return {}
    pre_main = build_report.get("_pre_contextual_filler_main", []) or []
    pre_deck = list(pre_main) + list(extra)
    try:
        pre_score = score_deck_breakdown(pre_deck, archetype, mode).get("final_score", 0)
    except Exception:
        pre_score = 0
    pre_count = int(build_report.get("pre_contextual_filler_main_count", len(pre_main)) or len(pre_main))
    final_confidence = float(build_report.get("generic_confidence_score", 0) or 0)
    baseline_confidence = round(max(0.0, final_confidence - (0.08 if pre_count < 40 else 0.0)), 4)
    baseline_result = {
        "score": pre_score,
        "confidence": baseline_confidence,
        "main_count": pre_count,
        "package_counts": build_report.get("pre_contextual_filler_package_counts", {}),
    }
    filler_result = {
        "score": breakdown.get("final_score", 0),
        "confidence": final_confidence,
        "main_count": len(split_deck(deck)[0]),
        "package_counts": build_report.get("package_counts", {}),
        "selected_fillers": build_report.get("selected_fillers", []),
        "filler_roles": build_report.get("filler_roles", {}),
        "contextual_filler_used": build_report.get("contextual_filler_used", False),
        "repair_used": build_report.get("repair_used", False),
        "pre_contextual_filler_main_count": pre_count,
        "quota_warnings": build_report.get("quota_warnings", []),
        "remaining_warnings": build_report.get("remaining_warnings", []),
        "legal_observation": bool(legal),
        "blocked_card_violations": blocked,
    }
    return analyze_filler_impact(archetype, mode, baseline_result, filler_result)


def filler_impact_classification_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for result in results:
        for classification in (result.get("filler_impact", {}).get("impact_classification", {}) or {}).values():
            counter[str(classification)] += 1
    return dict(counter)
