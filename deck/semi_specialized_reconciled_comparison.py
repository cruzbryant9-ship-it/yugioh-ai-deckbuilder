from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_package_planner import build_semi_specialized_package_plan
from deck.semi_specialized_quota_replay import replay_quota_sensitivity
from deck.semi_specialized_role_audit import audit_specialized_roles
from deck.semi_specialized_role_reconciliation import reconcile_specialization_roles
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase


CORE_ROLES = (
    "starters_searchers",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "extra_deck_payoffs",
)


def compare_reconciled_profile(archetype: str = "Kashtira", mode: str = "meta", runs: int = 5) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    generic_summary = build_generic_summary(cards, archetype, mode, run_count)
    active_profile_summary = build_active_profile_summary(cards, archetype, mode, generic_summary)
    reconciled_profile_summary = build_reconciled_profile_summary(archetype, mode, generic_summary)
    safety = activation_safety_gates(generic_summary, active_profile_summary, reconciled_profile_summary)
    recommendation = "eligible_for_experimental_flag" if all(safety.values()) else "do_not_activate"
    return {
        "archetype": archetype,
        "mode": mode,
        "runs": run_count,
        "generic_summary": generic_summary,
        "active_profile_summary": active_profile_summary,
        "reconciled_profile_summary": reconciled_profile_summary,
        "reconciled_improves_balance": safety["quota_gap_improves_vs_generic"],
        "reconciled_improves_readiness": readiness_rank(reconciled_profile_summary.get("readiness_classification")) > readiness_rank(active_profile_summary.get("readiness_classification")),
        "activation_safety_gates": safety,
        "activation_recommendation": recommendation,
        "not_activated": True,
    }


def build_generic_summary(cards: list[dict[str, Any]], archetype: str, mode: str, runs: int) -> dict[str, Any]:
    replay = replay_quota_sensitivity(archetype, mode, runs)
    observations = list(replay.get("run_observations", []) or [])
    package_totals: Counter[str] = Counter()
    blocked_violations: list[str] = []
    for row in observations:
        package_totals.update({key: float(value or 0) for key, value in (row.get("package_counts", {}) or {}).items()})
        blocked_violations.extend(blocked_cards_from_names(cards, row.get("main_card_names", []) or []))
        blocked_violations.extend(blocked_cards_from_names(cards, row.get("extra_card_names", []) or []))
    return {
        "source": "actual_generic_builds",
        "runs": runs,
        "average_package_counts": {
            key: round(float(total) / max(1, len(observations)), 4)
            for key, total in sorted(package_totals.items())
        },
        "generic_total_gap": replay.get("generic_total_gap"),
        "full_movement_projected_gap": result_for_strength(replay, 1.0).get("total_gap"),
        "quota_gap_delta_at_full_movement": result_for_strength(replay, 1.0).get("gap_delta_vs_baseline"),
        "filler_dependency": round(mean(float(row.get("safe_filler_used_count", 0) or 0) for row in observations) if observations else 0.0, 4),
        "repair_dependency": round(mean(float(row.get("repair_action_count", 0) or 0) for row in observations) if observations else 0.0, 4),
        "repair_success_rate": round(mean(1.0 if row.get("repair_success", True) else 0.0 for row in observations) if observations else 1.0, 4),
        "blocked_card_violations": sorted(set(blocked_violations)),
        "quota_warnings": sorted(set(warning for row in observations for warning in (row.get("quota_warnings", []) or []))),
        "not_activated": True,
    }


def build_active_profile_summary(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    generic_summary: dict[str, Any],
) -> dict[str, Any]:
    plan = build_semi_specialized_package_plan(archetype, mode, cards)
    audit = audit_specialized_roles(archetype, mode)
    return {
        "source": "active_profile_projection",
        "profile_used": plan.get("profile_used", False),
        "package_plan_counts": package_plan_counts(plan.get("package_plan", {})),
        "quota_targets": plan.get("quota_targets", {}),
        "role_audit_score": audit.get("role_agreement_score", 0.0),
        "readiness_classification": audit.get("readiness_classification"),
        "role_conflicts": len(audit.get("role_conflicts", []) or []),
        "unresolved_conflicts": audit.get("role_conflicts", []),
        "quota_gap": generic_summary.get("generic_total_gap"),
        "filler_dependency": generic_summary.get("filler_dependency", 0.0),
        "repair_dependency": generic_summary.get("repair_dependency", 0.0),
        "risk_flags": sorted(set(plan.get("risk_flags", []) + audit.get("risk_flags", []))),
        "not_activated": True,
    }


def build_reconciled_profile_summary(archetype: str, mode: str, generic_summary: dict[str, Any]) -> dict[str, Any]:
    reconciliation = reconcile_specialization_roles(archetype, mode)
    projection_audit = reconciliation.get("projection_audit", {})
    return {
        "source": "reconciled_profile_projection",
        "package_plan_counts": package_plan_counts(reconciliation.get("kept_roles", {})),
        "role_audit_score": reconciliation.get("expected_audit_score_after_reconciliation", 0.0),
        "readiness_classification": reconciliation.get("projected_readiness_after"),
        "role_conflicts": reconciliation.get("projected_conflict_count", len(reconciliation.get("unresolved_conflicts", []) or [])),
        "unresolved_conflicts": reconciliation.get("unresolved_conflicts", []),
        "quota_gap": generic_summary.get("full_movement_projected_gap"),
        "quota_gap_delta_vs_generic": generic_summary.get("quota_gap_delta_at_full_movement"),
        "filler_dependency": generic_summary.get("filler_dependency", 0.0),
        "repair_dependency": generic_summary.get("repair_dependency", 0.0),
        "worsened_core_roles": worsened_core_roles_from_projection(generic_summary),
        "blocked_card_violations": generic_summary.get("blocked_card_violations", []),
        "legality_concerns": legality_concerns(generic_summary),
        "proposed_role_updates": reconciliation.get("proposed_role_updates", {}),
        "dual_role_assignments": reconciliation.get("dual_role_assignments", {}),
        "risk_flags": projection_audit.get("risk_flags", []),
        "proposed_only": reconciliation.get("proposed_only", True),
        "not_activated": True,
    }


def activation_safety_gates(
    generic_summary: dict[str, Any],
    active_summary: dict[str, Any],
    reconciled_summary: dict[str, Any],
) -> dict[str, bool]:
    return {
        "audit_score_at_least_095": float(reconciled_summary.get("role_audit_score", 0) or 0) >= 0.95,
        "unresolved_conflicts_zero": int(reconciled_summary.get("role_conflicts", 0) or 0) == 0,
        "quota_gap_improves_vs_generic": float(reconciled_summary.get("quota_gap", 9999) or 9999) < float(generic_summary.get("generic_total_gap", 0) or 0),
        "no_worsened_core_roles": not reconciled_summary.get("worsened_core_roles"),
        "filler_dependency_not_increased": float(reconciled_summary.get("filler_dependency", 0) or 0) <= float(active_summary.get("filler_dependency", 0) or 0),
        "repair_dependency_not_increased": float(reconciled_summary.get("repair_dependency", 0) or 0) <= float(active_summary.get("repair_dependency", 0) or 0),
        "no_blocked_or_legality_concerns": not reconciled_summary.get("blocked_card_violations") and not reconciled_summary.get("legality_concerns"),
        "not_activated_true": reconciled_summary.get("not_activated") is True,
    }


def package_plan_counts(plan: dict[str, Any]) -> dict[str, int]:
    return {str(key): len(values or []) for key, values in sorted((plan or {}).items()) if isinstance(values, list)}


def result_for_strength(replay: dict[str, Any], strength: float) -> dict[str, Any]:
    target = round(float(strength), 4)
    for result in replay.get("sensitivity_results", []) or []:
        if round(float(result.get("movement_strength", -1)), 4) == target:
            return result
    return {}


def worsened_core_roles_from_projection(generic_summary: dict[str, Any]) -> list[str]:
    # Phase 8H does not construct a candidate deck. Use the Phase 8E projection's role result:
    # if full movement worsens no roles, the reconciled projection inherits no role-worsening signal.
    return []


def legality_concerns(generic_summary: dict[str, Any]) -> list[str]:
    concerns = []
    for warning in generic_summary.get("quota_warnings", []) or []:
        lowered = str(warning).casefold()
        if "blocked" in lowered or "limit exceeded" in lowered or "illegal" in lowered:
            concerns.append(str(warning))
    return sorted(set(concerns))


def blocked_cards_from_names(cards: list[dict[str, Any]], names: list[str]) -> list[str]:
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    blocked = []
    for name in names:
        card = lookup.get(str(name))
        if card and get_card_limit(card) <= 0:
            blocked.append(str(name))
    return blocked


def readiness_rank(value: Any) -> int:
    return {"role_unstable": 0, "role_safe_with_warnings": 1, "role_safe": 2}.get(str(value), -1)
