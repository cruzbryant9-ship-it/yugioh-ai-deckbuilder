from __future__ import annotations

from statistics import mean
from typing import Any

from deck.builder import score_deck_breakdown
from deck.archetype_role_inference import infer_archetype_roles
from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_card_shift_explainer import explain_card_shifts
from deck.generic_deck_builder import build_generic_deck
from deck.generic_package_extractor import extract_generic_packages
from deck.generic_package_replay import build_package_replay_report
from deck.generic_ratio_memory import load_generic_ratio_memory, record_targeted_recommendation_result
from deck.rejection_classification import classify_rejection_causes, harmful_learning_eligible
from SystemAIYugioh.memory_context import normalize_provenance

MIN_SAFE_TARGETED_IMPROVEMENT = 0.1
MIN_SAFE_CONFIDENCE = 0.15


def run_targeted_retest(
    archetype: str,
    card_pool: list[dict[str, Any]],
    mode: str,
    recommendations: dict[str, Any] | list[dict[str, Any]],
    runs_per_recommendation: int = 3,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance)
    recommendation_rows = recommendation_list(recommendations)
    runs_per_recommendation = max(1, int(runs_per_recommendation))
    baseline_score = baseline_memory_score(archetype, mode)
    baseline_deck, baseline_report = build_generic_deck(archetype, card_pool, mode=mode, use_ratio_memory=True)
    actual_baseline_score = float(score_deck_breakdown(baseline_deck, archetype, mode).get("final_score", 0) or 0)
    if baseline_score <= 0:
        baseline_score = actual_baseline_score
    role_map = build_role_map(card_pool, archetype)
    package_data = extract_generic_packages(card_pool, archetype)
    tested: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, recommendation in enumerate(recommendation_rows, start=1):
        result = test_recommendation(
            archetype,
            card_pool,
            mode,
            recommendation,
            runs_per_recommendation,
            baseline_score,
            index,
            baseline_deck,
            role_map,
            package_data,
        )
        tested.append(result)
        if not result["safe"]:
            causes = classify_rejection_causes(result)
            rejected.append(
                {
                    "recommendation": recommendation,
                    "score": result["average_score"],
                    "improvement": result["improvement"],
                    "rejection_reason": result["rejection_reason"],
                    "rejection_causes": causes,
                    "harmful_learning_eligible": harmful_learning_eligible({**result, "rejection_causes": causes}),
                    "card_shift_explanation": result.get("card_shift_explanation", {}),
                    "package_replay_report": result.get("package_replay_report", {}),
                }
            )

    safe_results = [result for result in tested if result["safe"]]
    best = max(safe_results, key=lambda row: (row["average_score"], row.get("confidence", 0)), default=None)
    accepted = accepted_payload(best) if best else None
    best_score = float(best.get("average_score", 0)) if best else max((float(row.get("average_score", 0)) for row in tested), default=0.0)
    improvement = round((float(accepted.get("score", 0)) - baseline_score) if accepted else best_score - baseline_score, 4)
    report = {
        "archetype": archetype,
        "mode": mode,
        "tested_recommendations": len(recommendation_rows),
        "accepted_recommendation": accepted,
        "best_score": round(best_score, 4),
        "baseline_score": round(baseline_score, 4),
        "actual_baseline_score": round(actual_baseline_score, 4),
        "baseline_deck_names": [str(card.get("name", "")) for card in baseline_deck],
        "baseline_package_counts": baseline_report.get("package_counts", {}),
        "improvement": improvement,
        "rejected_recommendations": rejected,
        "targeted_retest_used": True,
        "tested_results": tested,
        "provenance": provenance,
    }
    record_targeted_recommendation_result(archetype, mode, report, provenance=provenance)
    return report


def test_recommendation(
    archetype: str,
    card_pool: list[dict[str, Any]],
    mode: str,
    recommendation: dict[str, Any],
    runs: int,
    baseline_score: float,
    index: int,
    baseline_deck: list[dict[str, Any]],
    role_map: dict[str, str],
    package_data: dict[str, Any],
) -> dict[str, Any]:
    scores: list[float] = []
    legal_runs = 0
    blocked_violations: list[str] = []
    warnings: list[str] = []
    best_deck: list[dict[str, Any]] = []
    best_report: dict[str, Any] = {}
    best_score = -999.0
    ratio_profile = recommendation.get("ratio_profile", {})

    for _run in range(runs):
        deck, build_report = build_generic_deck(archetype, card_pool, mode=mode, ratio_profile=ratio_profile, use_ratio_memory=False)
        main, extra = split_deck(deck)
        blocked = blocked_card_violations(deck)
        blocked_violations.extend(blocked)
        warnings.extend(build_report.get("remaining_warnings", []) or [])
        warnings.extend(build_report.get("quota_warnings", []) or [])
        legal = deck_is_legal(main, extra, blocked, build_report)
        if legal:
            legal_runs += 1
        score = float(score_deck_breakdown(deck, archetype, mode).get("final_score", 0) or 0)
        scores.append(score)
        if score > best_score:
            best_score = score
            best_deck = deck
            best_report = build_report

    average_score = round(mean(scores), 4) if scores else 0.0
    improvement = round(average_score - baseline_score, 4)
    safe, reason = safety_check(average_score, baseline_score, legal_runs, runs, blocked_violations, warnings, best_report)
    shift = explain_card_shifts(baseline_deck, best_deck, role_map, package_data, improvement)
    replay = build_package_replay_report(archetype, baseline_deck, best_deck, role_map, package_data, improvement)
    decision_explanation = explain_decision(safe, reason, shift, improvement)
    return {
        "recommendation_index": index,
        "recommendation": recommendation,
        "ratio_profile": ratio_profile,
        "runs": runs,
        "average_score": average_score,
        "best_score": round(best_score, 4),
        "baseline_score": round(baseline_score, 4),
        "improvement": improvement,
        "legal_run_count": legal_runs,
        "blocked_card_violations": sorted(set(blocked_violations)),
        "quota_warnings": sorted(set(warnings)),
        "confidence": best_report.get("generic_confidence_score", 0),
        "package_counts": best_report.get("package_counts", {}),
        "repair_used": best_report.get("repair_used", False),
        "repair_success": best_report.get("repair_success", False),
        "repair_actions": best_report.get("repair_actions", []),
        "safe": safe,
        "rejection_reason": reason,
        "decision_explanation": decision_explanation,
        "card_shift_explanation": shift,
        "package_replay_report": replay,
        "best_deck_names": [str(card.get("name", "")) for card in best_deck],
    }


def safety_check(
    average_score: float,
    baseline_score: float,
    legal_runs: int,
    runs: int,
    blocked: list[str],
    warnings: list[str],
    build_report: dict[str, Any],
) -> tuple[bool, str | None]:
    if legal_runs < runs:
        return False, "illegal_or_unrepaired_deck"
    if blocked:
        return False, "blocked_card_violation"
    hard_terms = ("blocked card", "copy limit exceeded", "main deck below", "main deck above", "Extra Deck above")
    if any(any(term in str(warning) for term in hard_terms) for warning in warnings):
        return False, "hard_legality_warning"
    if float(build_report.get("generic_confidence_score", 0) or 0) < MIN_SAFE_CONFIDENCE:
        return False, "confidence_too_low"
    if average_score - baseline_score < MIN_SAFE_TARGETED_IMPROVEMENT:
        return False, "no_safe_improvement"
    return True, None


def accepted_payload(best: dict[str, Any] | None) -> dict[str, Any] | None:
    if not best:
        return None
    recommendation = best.get("recommendation", {})
    return {
        "ratio_profile": best.get("ratio_profile", {}),
        "score": best.get("average_score", 0),
        "improvement": best.get("improvement", 0),
        "reason": recommendation.get("reason", ""),
        "diagnosis_causes": recommendation.get("diagnosis_causes", []),
        "risk_level": recommendation.get("risk_level", "medium"),
        "package_counts": best.get("package_counts", {}),
        "confidence": best.get("confidence", 0),
        "card_shift_explanation": best.get("card_shift_explanation", {}),
        "package_replay_report": best.get("package_replay_report", {}),
        "decision_explanation": best.get("decision_explanation", ""),
    }


def recommendation_list(recommendations: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(recommendations, dict):
        rows = recommendations.get("recommendations", [])
    else:
        rows = recommendations
    return [row for row in rows if isinstance(row, dict) and isinstance(row.get("ratio_profile"), dict)]


def baseline_memory_score(archetype: str, mode: str) -> float:
    memory = load_generic_ratio_memory(archetype, mode)
    score = safe_float(memory.get("best_score"))
    return score if score > 0 else 0.0


def build_role_map(card_pool: list[dict[str, Any]], archetype: str) -> dict[str, str]:
    analysis = infer_archetype_roles(card_pool, archetype)
    role_map: dict[str, str] = {}
    roles = analysis.get("roles", {}) if isinstance(analysis, dict) else {}
    for role, names in roles.items():
        for name in names or []:
            role_map[str(name)] = str(role)
    return role_map


def explain_decision(safe: bool, reason: str | None, shift: dict[str, Any], improvement: float) -> str:
    if safe:
        return f"Accepted because the candidate improved by {round(improvement, 4)} while passing legality and confidence checks. {shift.get('explanation', '')}"
    return f"Rejected because {reason or 'it failed safety checks'}. {shift.get('explanation', '')}"


def deck_is_legal(main: list[dict[str, Any]], extra: list[dict[str, Any]], blocked: list[str], build_report: dict[str, Any]) -> bool:
    hard_terms = ("blocked card", "copy limit exceeded", "main deck below", "main deck above", "Extra Deck above")
    warnings = list(build_report.get("remaining_warnings", []) or []) + list(build_report.get("quota_warnings", []) or [])
    return len(main) == 40 and len(extra) <= 15 and not blocked and not any(any(term in str(warning) for term in hard_terms) for warning in warnings)


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
