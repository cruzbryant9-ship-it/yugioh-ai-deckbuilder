from __future__ import annotations

from typing import Any

from deck.resource_state import ResourceState


def can_pay_cost(resource_state: ResourceState, cost: dict[str, Any]) -> bool:
    cost_type = str(cost.get("type", ""))
    requirement = cost.get("requirement", {"any": True})
    if cost_type == "reveal":
        return resource_state.card_in_hand(requirement)
    if cost_type == "discard":
        return resource_state.card_in_hand(requirement)
    if cost_type == "send_to_gy":
        return resource_state.has_matching_card(str(cost.get("from", "hand")), requirement)
    if cost_type == "banish":
        return resource_state.has_matching_card(str(cost.get("from", "graveyard")), requirement)
    return True


def apply_cost(resource_state: ResourceState, cost: dict[str, Any]) -> str | None:
    cost_type = str(cost.get("type", ""))
    requirement = cost.get("requirement", {"any": True})
    if cost_type == "reveal":
        return None if resource_state.reveal_card(requirement) else "cost_reveal_unavailable"
    if cost_type == "discard":
        return None if resource_state.discard_card(requirement) else "cost_discard_unavailable"
    if cost_type == "send_to_gy":
        source = str(cost.get("from", "hand"))
        return None if resource_state.send_matching_to_gy(requirement, source) else "cost_send_unavailable"
    if cost_type == "banish":
        source = str(cost.get("from", "graveyard"))
        return None if resource_state.banish_matching(requirement, source) else "cost_banish_unavailable"
    return None


def can_satisfy_condition(resource_state: ResourceState, condition: dict[str, Any]) -> bool:
    condition_type = str(condition.get("type", ""))
    requirement = condition.get("requirement", {"any": True})
    if condition_type == "control":
        return resource_state.control_card(requirement)
    if condition_type in {"in_gy", "has_in_gy"}:
        return resource_state.card_in_gy(requirement)
    if condition_type == "on_field":
        return resource_state.card_on_field(requirement)
    if condition_type == "in_hand":
        return resource_state.card_in_hand(requirement)
    if condition_type == "target_in_deck":
        return resource_state.card_in_deck(requirement)
    if condition_type == "target_in_gy":
        return resource_state.card_in_gy(requirement)
    card_name = str(condition.get("card_name", ""))
    if condition_type == "was_summoned_this_turn":
        return resource_state.was_summoned_this_turn(card_name)
    if condition_type == "was_special_summoned_this_turn":
        return resource_state.was_special_summoned_this_turn(card_name)
    if condition_type == "was_sent_to_gy_this_turn":
        return resource_state.was_sent_to_gy_this_turn(card_name)
    if condition_type == "effect_resolved_this_turn":
        return resource_state.was_effect_resolved_this_turn(card_name)
    if condition_type == "card_activated_this_turn":
        return resource_state.was_activated_this_turn(card_name)
    if condition_type == "previous_node_completed":
        return resource_state.has_event("node_completed", card_name or None)
    if condition_type == "previous_card_moved":
        return resource_state.has_event("card_moved", card_name or None)
    return True


def condition_failure_reason(condition: dict[str, Any]) -> str:
    condition_type = str(condition.get("type", ""))
    if condition_type == "control":
        return "condition_control_unmet"
    if condition_type in {"in_gy", "has_in_gy", "target_in_gy"}:
        return "condition_gy_unmet"
    if condition_type in {"target_in_deck", "in_hand", "on_field"}:
        return "condition_target_unavailable"
    if condition_type in {"was_summoned_this_turn", "was_special_summoned_this_turn"}:
        return "summon_history_missing"
    if condition_type == "was_sent_to_gy_this_turn":
        return "gy_history_missing"
    if condition_type == "card_activated_this_turn":
        return "activation_history_missing"
    if condition_type == "effect_resolved_this_turn":
        return "resolution_history_missing"
    if condition_type in {"previous_node_completed", "previous_card_moved"}:
        return "history_condition_unmet"
    return "activation_restriction_failed"
