from __future__ import annotations

from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile


def build_semi_specialized_package_plan(
    archetype: str,
    mode: str = "meta",
    card_pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = load_specialization_profile(archetype)
    if not profile:
        return {
            "archetype": archetype,
            "mode": mode,
            "profile_used": False,
            "package_plan": {},
            "quota_targets": {},
            "risk_flags": ["no semi-specialization profile exists"],
            "not_activated": True,
        }

    available_names = {str(card.get("name", "")) for card in card_pool or []}
    package_plan = {
        "core": profile["core_cards"],
        "starters": profile["starters"],
        "extenders": profile["extenders"],
        "payoffs": profile["payoffs"],
        "interruptions": profile["interruptions"],
        "board_breakers": profile["board_breakers"],
        "bricks_garnets": profile["bricks_garnets"],
        "extra_deck_preferences": profile["extra_deck_preferences"],
    }
    quota_targets = {
        key: values.get("target")
        for key, values in profile.get("package_quotas", {}).items()
        if isinstance(values, dict)
    }
    missing_profile_cards = sorted(
        name
        for names in package_plan.values()
        for name in names
        if available_names and name not in available_names
    )
    risk_flags = list(profile.get("known_risk_flags", []))
    if missing_profile_cards:
        risk_flags.append(f"profile cards missing from local card pool: {', '.join(missing_profile_cards[:8])}")
    if quota_targets.get("max_bricks", 0) > 3:
        risk_flags.append("brick target requires manual review")
    return {
        "archetype": profile["archetype"],
        "mode": mode,
        "profile_used": True,
        "profile_version": profile.get("profile_version"),
        "package_plan": package_plan,
        "quota_targets": quota_targets,
        "filler_limits": profile.get("filler_limits", {}),
        "repair_constraints": profile.get("repair_constraints", {}),
        "role_confidence_notes": profile.get("role_confidence_notes", {}),
        "risk_flags": risk_flags,
        "not_activated": True,
    }
