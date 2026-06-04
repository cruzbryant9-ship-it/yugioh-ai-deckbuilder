from __future__ import annotations

from copy import deepcopy
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.semi_specialized_role_audit import audit_profile_roles, audit_specialized_roles
from SystemAIYugioh.card_database import CardDatabase


PROFILE_LIST_KEYS = (
    "starters",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "bricks_garnets",
    "extra_deck_preferences",
)

ROLE_TO_PROFILE_KEY = {
    "starters_searchers": "starters",
    "extenders": "extenders",
    "payoffs": "payoffs",
    "interruptions": "interruptions",
    "board_breakers": "board_breakers",
    "bricks_garnets": "bricks_garnets",
    "extra_deck_payoffs": "extra_deck_preferences",
}


def reconcile_specialization_roles(archetype: str, mode: str = "meta") -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    profile = load_specialization_profile(archetype)
    if not profile:
        return empty_reconciliation(archetype, mode, "no specialization profile found")
    current_audit = audit_specialized_roles(archetype, mode)
    projected_profile = deepcopy(profile)
    proposed_role_updates: dict[str, dict[str, Any]] = {}
    kept_roles: dict[str, list[str]] = {}
    downgraded_roles: dict[str, list[dict[str, Any]]] = {}
    dual_role_assignments: dict[str, list[str]] = {}
    resolved_conflicts: list[dict[str, Any]] = []
    unresolved_conflicts: list[dict[str, Any]] = []

    for conflict in current_audit.get("role_conflicts", []) or []:
        card = str(conflict.get("card", ""))
        role = str(conflict.get("profile_role", ""))
        reason = str(conflict.get("reason", ""))
        if card == "Kashtira Riseheart" and role == "payoffs":
            remove_profile_role(projected_profile, card, "payoffs")
            add_profile_role(projected_profile, card, "extenders")
            dual_role_assignments[card] = ["extenders", "payoff_bridge"]
            proposed_role_updates[card] = {
                "from": ["extenders", "payoffs"],
                "to": ["extenders", "payoff_bridge"],
                "recommendation": "treat as extender with payoff-bridge note instead of counted payoff",
                "reason": reason,
                "proposed_only": True,
                "not_activated": True,
            }
            downgraded_roles.setdefault(card, []).append({"from": "payoffs", "to": "payoff_bridge", "reason": reason})
            resolved_conflicts.append(conflict)
            continue
        if role == "bricks_garnets" and "high benchmark usage" in reason:
            remove_profile_role(projected_profile, card, "bricks_garnets")
            proposed_role_updates.setdefault(
                card,
                {
                    "from": ["bricks_garnets"],
                    "to": ["engine_risk"],
                    "recommendation": "downgrade from counted brick/garnet to non-quota engine-risk note",
                    "reason": reason,
                    "proposed_only": True,
                    "not_activated": True,
                },
            )
            downgraded_roles.setdefault(card, []).append({"from": "bricks_garnets", "to": "engine_risk", "reason": reason})
            resolved_conflicts.append(conflict)
            continue
        if role == "bricks_garnets" and "lacks supporting" in reason:
            remove_profile_role(projected_profile, card, "bricks_garnets")
            proposed_role_updates.setdefault(
                card,
                {
                    "from": ["bricks_garnets"],
                    "to": ["manual_risk_note"],
                    "recommendation": "remove from counted brick/garnet quota until text/usage support appears",
                    "reason": reason,
                    "proposed_only": True,
                    "not_activated": True,
                },
            )
            downgraded_roles.setdefault(card, []).append({"from": "bricks_garnets", "to": "manual_risk_note", "reason": reason})
            resolved_conflicts.append(conflict)
            continue
        unresolved_conflicts.append(conflict)

    projected_profile["proposed_only"] = True
    projected_profile["not_activated"] = True
    projected_profile["role_reconciliation_notes"] = {
        "dual_role_assignments": dual_role_assignments,
        "downgraded_roles": downgraded_roles,
        "source": "Phase 8G projection only",
    }
    projected_audit = audit_profile_roles(projected_profile, cards, archetype, mode)
    for key in PROFILE_LIST_KEYS:
        kept = sorted(set(projected_profile.get(key, []) or []))
        if kept:
            kept_roles[key] = kept
    return {
        "archetype": archetype,
        "mode": mode,
        "proposed_role_updates": proposed_role_updates,
        "kept_roles": kept_roles,
        "downgraded_roles": downgraded_roles,
        "dual_role_assignments": dual_role_assignments,
        "unresolved_conflicts": projected_audit.get("role_conflicts", []),
        "resolved_conflicts": resolved_conflicts,
        "conflicts_resolved": max(0, len(current_audit.get("role_conflicts", []) or []) - len(projected_audit.get("role_conflicts", []) or [])),
        "current_audit_score": current_audit.get("role_agreement_score", 0.0),
        "expected_audit_score_after_reconciliation": projected_audit.get("role_agreement_score", 0.0),
        "readiness_before": current_audit.get("readiness_classification"),
        "projected_readiness_after": projected_audit.get("readiness_classification"),
        "current_conflict_count": len(current_audit.get("role_conflicts", []) or []),
        "projected_conflict_count": len(projected_audit.get("role_conflicts", []) or []),
        "current_low_confidence_count": len(current_audit.get("low_confidence_assignments", []) or []),
        "projected_low_confidence_count": len(projected_audit.get("low_confidence_assignments", []) or []),
        "projection_audit": projected_audit,
        "proposed_only": True,
        "not_activated": True,
    }


def remove_profile_role(profile: dict[str, Any], card: str, role: str) -> None:
    key = ROLE_TO_PROFILE_KEY.get(role, role)
    values = [str(name) for name in profile.get(key, []) or [] if str(name) != card]
    profile[key] = values


def add_profile_role(profile: dict[str, Any], card: str, role: str) -> None:
    key = ROLE_TO_PROFILE_KEY.get(role, role)
    values = [str(name) for name in profile.get(key, []) or []]
    if card not in values:
        values.append(card)
    profile[key] = sorted(values)


def empty_reconciliation(archetype: str, mode: str, reason: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "mode": mode,
        "proposed_role_updates": {},
        "kept_roles": {},
        "downgraded_roles": {},
        "dual_role_assignments": {},
        "unresolved_conflicts": [{"reason": reason}],
        "expected_audit_score_after_reconciliation": 0.0,
        "proposed_only": True,
        "not_activated": True,
    }
