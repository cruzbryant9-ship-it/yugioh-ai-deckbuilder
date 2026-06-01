from __future__ import annotations

from typing import Any

from deck.interruption_profiles import InterruptionProfile, interruption_profiles


def create_chain_link(
    chain_link: int,
    activating_card: str,
    effect_type: str,
    response_window: bool = True,
    possible_responses: list[str] | None = None,
    resolution_outcome: str = "resolved",
) -> dict[str, Any]:
    return {
        "chain_link": chain_link,
        "activating_card": activating_card,
        "effect_type": effect_type,
        "response_window": response_window,
        "possible_responses": possible_responses or [],
        "resolution_outcome": resolution_outcome,
    }


def possible_responses(effect_type: str, vulnerable_to: tuple[str, ...] | list[str] = ()) -> list[InterruptionProfile]:
    allowed = {item.casefold() for item in vulnerable_to}
    matches = []
    for profile in interruption_profiles():
        if allowed and profile.name.casefold() not in allowed:
            continue
        if effect_type in profile.can_respond_to or any(kind in effect_type for kind in profile.can_respond_to):
            matches.append(profile)
    return matches


def build_chain_window(chain_link: int, activating_card: str, effect_type: str, vulnerable_to: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    responses = possible_responses(effect_type, vulnerable_to)
    outcome = "resolved" if not responses else "resolved_with_risk"
    return create_chain_link(
        chain_link=chain_link,
        activating_card=activating_card,
        effect_type=effect_type,
        response_window=bool(responses),
        possible_responses=[profile.name for profile in responses],
        resolution_outcome=outcome,
    )


def estimate_interruption_risk(chain_windows: list[dict[str, Any]]) -> float:
    profiles = {profile.name: profile for profile in interruption_profiles()}
    risk = 0.0
    seen_once_per_chain = set()
    for window in chain_windows:
        for response in window.get("possible_responses", []):
            if response in seen_once_per_chain:
                continue
            seen_once_per_chain.add(response)
            risk += profiles.get(response).risk_score if profiles.get(response) else 0.5
    return round(risk, 2)


def estimate_recovery_adjusted_resilience(risk: float, recovery_routes: list[str] | tuple[str, ...]) -> float:
    recovery = min(5.0, len(recovery_routes) * 1.25)
    return round(max(0.0, 10.0 - risk + recovery), 2)
