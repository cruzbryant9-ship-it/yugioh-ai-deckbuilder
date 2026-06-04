from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_package_planner import build_semi_specialized_package_plan
from SystemAIYugioh.card_database import CardDatabase


BALANCE_ROLES = (
    "starters_searchers",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "extra_deck_payoffs",
)

DEFAULT_MOVEMENT_STRENGTHS = (0.0, 0.5, 0.75, 1.0)
PHASE8D_PROPOSED_MOVEMENT = 0.75


def replay_quota_plan(archetype: str, mode: str = "meta", runs: int = 5) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    plan = build_semi_specialized_package_plan(archetype, mode, cards)
    quota_targets = plan.get("quota_targets", {}) if isinstance(plan.get("quota_targets"), dict) else {}
    run_rows = [build_generic_observation(cards, archetype, mode, index + 1) for index in range(max(1, runs))]
    generic_balance = build_balance(run_rows, quota_targets)
    proposed_balance = project_proposed_balance(generic_balance, quota_targets)
    generic_gap = total_gap(generic_balance)
    proposed_gap = total_gap(proposed_balance)
    improved_roles = []
    worsened_roles = []
    for role in BALANCE_ROLES:
        before = abs(float(generic_balance.get(role, {}).get("gap", 0) or 0))
        after = abs(float(proposed_balance.get(role, {}).get("gap", 0) or 0))
        if after < before:
            improved_roles.append(role)
        elif after > before:
            worsened_roles.append(role)
    return {
        "archetype": archetype,
        "mode": mode,
        "runs": max(1, runs),
        "generic_balance": generic_balance,
        "proposed_balance": proposed_balance,
        "gap_delta": round(generic_gap - proposed_gap, 4),
        "generic_total_gap": round(generic_gap, 4),
        "proposed_total_gap": round(proposed_gap, 4),
        "improved_roles": improved_roles,
        "worsened_roles": worsened_roles,
        "risk_flags": risk_flags(run_rows, generic_balance, proposed_balance, plan),
        "run_observations": run_rows,
        "profile_targets": quota_targets,
        "not_activated": True,
    }


def replay_quota_sensitivity(
    archetype: str,
    mode: str = "meta",
    runs: int = 5,
    movement_strengths: list[float] | tuple[float, ...] | None = None,
) -> dict[str, Any]:
    strengths = list(movement_strengths or DEFAULT_MOVEMENT_STRENGTHS)
    cards = CardDatabase().load_cards()
    plan = build_semi_specialized_package_plan(archetype, mode, cards)
    quota_targets = plan.get("quota_targets", {}) if isinstance(plan.get("quota_targets"), dict) else {}
    run_rows = [build_generic_observation(cards, archetype, mode, index + 1) for index in range(max(1, runs))]
    generic_balance = build_balance(run_rows, quota_targets)
    baseline_gap = total_gap(generic_balance)
    results = []
    for strength in strengths:
        normalized_strength = clamp_strength(strength)
        balance = project_sensitivity_balance(generic_balance, quota_targets, normalized_strength)
        gap = total_gap(balance)
        improved_roles, worsened_roles = compare_role_gaps(generic_balance, balance)
        results.append(
            {
                "movement_strength": normalized_strength,
                "total_gap": round(gap, 4),
                "gap_delta_vs_baseline": round(baseline_gap - gap, 4),
                "role_gaps": {
                    role: {
                        "target": row.get("target", 0),
                        "projected_observed": row.get("projected_observed", row.get("average_observed", 0)),
                        "gap": row.get("gap", 0),
                        "gap_type": row.get("gap_type", "met"),
                        "absolute_gap": row.get("absolute_gap", 0),
                    }
                    for role, row in balance.items()
                },
                "improved_roles": improved_roles,
                "worsened_roles": worsened_roles,
                "risk_flags": risk_flags(run_rows, generic_balance, balance, plan),
                "not_activated": True,
            }
        )
    stability = classify_stability(results)
    return {
        "archetype": archetype,
        "mode": mode,
        "runs": max(1, runs),
        "movement_strengths": [row["movement_strength"] for row in results],
        "generic_balance": generic_balance,
        "generic_total_gap": round(baseline_gap, 4),
        "sensitivity_results": results,
        "stability_classification": stability,
        "risk_flags": sorted(set(flag for row in results for flag in row.get("risk_flags", []))),
        "run_observations": run_rows,
        "profile_targets": quota_targets,
        "phase8d_proposed_movement": PHASE8D_PROPOSED_MOVEMENT,
        "not_activated": True,
    }


def build_generic_observation(cards: list[dict[str, Any]], archetype: str, mode: str, run: int) -> dict[str, Any]:
    deck, _pool = build_deck(cards, archetype, mode=mode, use_learning=True, generic_tune_runs=0)
    report = dict(get_last_build_report())
    package_counts = dict(report.get("package_counts", {}) or {})
    package_counts["extra_deck_payoffs"] = count_extra_deck_payoffs(deck, archetype)
    return {
        "run": run,
        "builder_used": report.get("builder_used"),
        "deck_size": len(deck),
        "main_card_names": [str(card.get("name", "")) for card in deck if not is_extra_deck_card(card)],
        "extra_card_names": [str(card.get("name", "")) for card in deck if is_extra_deck_card(card)],
        "package_counts": package_counts,
        "quota_warnings": list(report.get("quota_warnings", []) or []),
        "repair_used": bool(report.get("repair_used", False)),
        "repair_success": bool(report.get("repair_success", True)),
        "repair_action_count": int(report.get("repair_action_count", 0) or 0),
        "safe_filler_used_count": int(report.get("safe_filler_used_count", 0) or 0),
        "not_activated": True,
    }


def build_balance(rows: list[dict[str, Any]], quota_targets: dict[str, Any]) -> dict[str, Any]:
    averages = average_counts(rows)
    balance = {}
    for role in BALANCE_ROLES:
        target = float(quota_targets.get(role, 0) or 0)
        observed = float(averages.get(role, 0) or 0)
        gap = observed - target
        balance[role] = {
            "target": target,
            "average_observed": round(observed, 4),
            "gap": round(gap, 4),
            "gap_type": "over" if gap > 0 else "under" if gap < 0 else "met",
            "absolute_gap": round(abs(gap), 4),
        }
    return balance


def project_proposed_balance(generic_balance: dict[str, Any], quota_targets: dict[str, Any]) -> dict[str, Any]:
    return project_sensitivity_balance(generic_balance, quota_targets, 1.0)


def project_sensitivity_balance(
    generic_balance: dict[str, Any],
    quota_targets: dict[str, Any],
    movement_strength: float,
) -> dict[str, Any]:
    capped_strength = clamp_strength(movement_strength)
    projected = {}
    for role, row in generic_balance.items():
        target = float(quota_targets.get(role, row.get("target", 0)) or 0)
        observed = float(row.get("average_observed", 0) or 0)
        gap = observed - target
        phase8d_adjustment = abs(gap) * PHASE8D_PROPOSED_MOVEMENT * capped_strength
        if gap > 0:
            adjusted = max(target, observed - phase8d_adjustment)
        elif gap < 0:
            adjusted = min(target, observed + phase8d_adjustment)
        else:
            adjusted = observed
        projected_gap = adjusted - target
        projected[role] = {
            "target": target,
            "projected_observed": round(adjusted, 4),
            "gap": round(projected_gap, 4),
            "gap_type": "over" if projected_gap > 0 else "under" if projected_gap < 0 else "met",
            "absolute_gap": round(abs(projected_gap), 4),
            "report_only_adjustment": round(adjusted - observed, 4),
        }
    return projected


def clamp_strength(strength: float) -> float:
    try:
        value = float(strength)
    except (TypeError, ValueError):
        value = 0.0
    return round(max(0.0, min(1.0, value)), 4)


def compare_role_gaps(
    baseline_balance: dict[str, Any],
    projected_balance: dict[str, Any],
) -> tuple[list[str], list[str]]:
    improved_roles = []
    worsened_roles = []
    for role in BALANCE_ROLES:
        before = abs(float(baseline_balance.get(role, {}).get("gap", 0) or 0))
        after = abs(float(projected_balance.get(role, {}).get("gap", 0) or 0))
        if after < before:
            improved_roles.append(role)
        elif after > before:
            worsened_roles.append(role)
    return improved_roles, worsened_roles


def classify_stability(results: list[dict[str, Any]]) -> str:
    if not results:
        return "unstable"
    ordered = sorted(results, key=lambda row: float(row.get("movement_strength", 0) or 0))
    gaps = [float(row.get("total_gap", 0) or 0) for row in ordered]
    deltas = [float(row.get("gap_delta_vs_baseline", 0) or 0) for row in ordered]
    worsened_role_count = sum(len(row.get("worsened_roles", []) or []) for row in ordered)
    improvement_collapsed = any(delta < -0.0001 for delta in deltas)
    monotonic_or_near = all(gaps[index] <= gaps[index - 1] + 0.25 for index in range(1, len(gaps)))
    if improvement_collapsed or worsened_role_count > 1:
        return "unstable"
    if monotonic_or_near and worsened_role_count == 0:
        return "stable"
    return "promising_but_watch"


def average_counts(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: Counter[str] = Counter()
    for row in rows:
        for role, count in (row.get("package_counts", {}) or {}).items():
            totals[str(role)] += float(count or 0)
    return {role: round(total / max(1, len(rows)), 4) for role, total in totals.items()}


def total_gap(balance: dict[str, Any]) -> float:
    return sum(float(row.get("absolute_gap", 0) or 0) for row in balance.values())


def count_extra_deck_payoffs(deck: list[dict[str, Any]], archetype: str) -> int:
    names = [str(card.get("name", "")) for card in deck if is_extra_deck_card(card)]
    lowered_archetype = archetype.casefold()
    payoff_terms = ("arise-heart", "shangri-ira", "zeus", "big eye", lowered_archetype)
    return sum(1 for name in names if any(term in name.casefold() for term in payoff_terms))


def risk_flags(
    rows: list[dict[str, Any]],
    generic_balance: dict[str, Any],
    proposed_balance: dict[str, Any],
    plan: dict[str, Any],
) -> list[str]:
    flags = list(plan.get("risk_flags", []) or [])
    warning_count = sum(len(row.get("quota_warnings", []) or []) for row in rows)
    repair_actions = [float(row.get("repair_action_count", 0) or 0) for row in rows]
    filler_counts = [float(row.get("safe_filler_used_count", 0) or 0) for row in rows]
    if warning_count:
        flags.append(f"quota violation risk: {warning_count} generic quota warnings observed")
    if mean(repair_actions or [0]) > 3:
        flags.append("repair dependency risk: average repair actions exceed Phase 8C review limit")
    if mean(filler_counts or [0]) > 0:
        flags.append("filler dependency risk: generic build used safe filler")
    if total_gap(proposed_balance) > total_gap(generic_balance):
        flags.append("projected package balance does not improve")
    if not all(row.get("builder_used") in {"generic", "generic_tuned"} for row in rows):
        flags.append("unexpected builder path observed during replay")
    return sorted(set(flags))


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    return any(term in str(card.get("type", "")).casefold() for term in ("fusion", "synchro", "xyz", "link"))
