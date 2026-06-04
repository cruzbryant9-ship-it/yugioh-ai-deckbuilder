from __future__ import annotations

from copy import deepcopy
from typing import Any


KASHTIRA_PROFILE: dict[str, Any] = {
    "archetype": "Kashtira",
    "profile_version": 1,
    "status": "pilot_design_only",
    "core_cards": [
        "Kashtira Unicorn",
        "Kashtira Fenrir",
        "Kashtira Riseheart",
        "Kashtira Birth",
        "Kashtiratheosis",
        "Pressured Planet Wraitsoth",
    ],
    "starters": [
        "Kashtira Unicorn",
        "Kashtira Fenrir",
        "Pressured Planet Wraitsoth",
        "Kashtiratheosis",
    ],
    "extenders": [
        "Kashtira Birth",
        "Kashtira Riseheart",
        "Scareclaw Kashtira",
        "Tearlaments Kashtira",
        "Kashtira Big Bang",
    ],
    "payoffs": [
        "Kashtira Arise-Heart",
        "Kashtira Shangri-Ira",
        "Kashtira Riseheart",
    ],
    "interruptions": [
        "Kashtira Arise-Heart",
        "Kashtira Fenrir",
        "Kashtira Big Bang",
        "Kashtira Preparations",
    ],
    "board_breakers": [
        "Book of Eclipse",
        "Dark Ruler No More",
        "Evenly Matched",
        "Lightning Storm",
    ],
    "bricks_garnets": [
        "Kashtira Big Bang",
        "Kashtira Ogre",
        "Kashtira Preparations",
        "Kashtira Overlap",
    ],
    "extra_deck_preferences": [
        "Kashtira Arise-Heart",
        "Kashtira Shangri-Ira",
        "Divine Arsenal AA-ZEUS - Sky Thunder",
        "Number 11: Big Eye",
    ],
    "package_quotas": {
        "starters_searchers": {"min": 10, "target": 12, "max": 14},
        "extenders": {"min": 5, "target": 7, "max": 9},
        "payoffs": {"min": 2, "target": 4, "max": 6},
        "interruptions": {"min": 7, "target": 9, "max": 12},
        "board_breakers": {"min": 2, "target": 3, "max": 5},
        "max_bricks": {"min": 1, "target": 3, "max": 4},
        "extra_deck_payoffs": {"min": 4, "target": 6, "max": 8},
    },
    "filler_limits": {
        "max_completion_only_fillers": 2,
        "prefer_engine_or_staple_fillers": True,
        "forbidden_filler_roles": ["low_confidence_engine_requirement", "unattributed_completion_only"],
    },
    "repair_constraints": {
        "max_average_repair_actions_for_ready": 3,
        "prefer_repairing_with": ["starters_searchers", "interruptions", "board_breakers"],
        "avoid_repairing_with": ["bricks_garnets", "unattributed_fillers"],
    },
    "known_risk_flags": [
        "filler dependency is slightly above Phase 8B readiness gate",
        "banlist changes can sharply affect starter density",
        "do not infer full combo graph until package ratios stabilize under pilot review",
    ],
    "role_confidence_notes": {
        "Kashtira Unicorn": "high-confidence starter/searcher",
        "Kashtira Fenrir": "high-confidence starter/interruption",
        "Kashtira Riseheart": "extender/payoff bridge",
        "Kashtira Birth": "recovery/extender",
        "Kashtira Arise-Heart": "primary payoff/interruption",
        "Kashtira Big Bang": "powerful but can become brick/filler pressure",
    },
}

SPECIALIZATION_PROFILES = {
    "kashtira": KASHTIRA_PROFILE,
}


def load_specialization_profile(archetype: str) -> dict[str, Any] | None:
    profile = SPECIALIZATION_PROFILES.get(str(archetype).casefold())
    return deepcopy(profile) if profile else None


def available_specialization_profiles() -> list[str]:
    return sorted(profile["archetype"] for profile in SPECIALIZATION_PROFILES.values())
