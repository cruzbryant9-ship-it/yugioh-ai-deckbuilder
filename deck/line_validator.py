from __future__ import annotations

from collections import Counter
from typing import Any

from deck.card_metadata import get_card_level, get_card_rank, get_link_rating
from deck.card_conditions import apply_cost, can_pay_cost, can_satisfy_condition, condition_failure_reason
from deck.card_text_parser import parse_card_text
from deck.chain_model import build_chain_window, estimate_interruption_risk, estimate_recovery_adjusted_resilience
from deck.line_graph import LineGraph, line_graphs_for_archetype
from deck.resource_state import ResourceState


def validate_line(
    hand: list[dict[str, Any]],
    graph: LineGraph,
    deck: list[dict[str, Any]] | None = None,
    extra_deck: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = build_resource_state(hand, deck, extra_deck)
    completed = []
    endboard = []
    interruption_points = []
    payoff_score = 0.0
    resource_score = float(len(hand))
    risk_score = 0.0
    locks: set[str] = set()
    chosen_branches: list[dict[str, Any]] = []
    branch_score = 0.0
    chain_windows: list[dict[str, Any]] = []
    interruption_risk = 0.0
    recovery_routes_seen: set[str] = set(graph.recovery_options)

    for node in graph.nodes:
        state.record_event("node_started", node.name)
        if getattr(node, "opens_chain", False) or getattr(node, "response_window", False) or getattr(node, "vulnerable_to", ()):
            effect_type = chain_effect_type(node)
            window = build_chain_window(
                len(chain_windows) + 1,
                node.card or node.summon_card or node.search_card or node.name,
                effect_type,
                getattr(node, "vulnerable_to", ()),
            )
            chain_windows.append(window)
            recovery_routes_seen.update(getattr(node, "recovery_routes", ()) or ())
            interruption_risk += float(getattr(node, "interruption_penalty", 0.0) or 0.0)
            interruption_risk = max(0.0, interruption_risk - float(getattr(node, "bait_value", 0.0) or 0.0) * 0.25)
        node_costs = list(getattr(node, "costs", ()) or ())
        node_conditions = list(getattr(node, "conditions", ()) or ())
        if getattr(node, "parsed_card_text_source", None):
            parsed = parse_card_text(node.parsed_card_text_source)
            node_costs.extend(parsed.get("costs", []))
            node_conditions.extend(parsed.get("conditions", []))
        for condition in node_conditions:
            if not can_satisfy_condition(state, condition):
                return failed(graph, completed, node.name, condition_failure_reason(condition), endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for cost in node_costs:
            cost_failure = apply_cost(state, cost)
            if cost_failure:
                return failed(graph, completed, node.name, cost_failure, endboard, interruption_points, payoff_score, resource_score, risk_score, state)
            resource_score -= 0.25
        if getattr(node, "branches", ()):
            branch_result = choose_branch(state, node.branches)
            if not branch_result["valid"]:
                return failed(graph, completed, node.name, branch_result["failure_reason"], endboard, interruption_points, payoff_score, resource_score, risk_score, state)
            chosen_branches.append({"node": node.name, "branch": branch_result["name"], "score": branch_result["score"]})
            branch_score += float(branch_result["score"])
            resource_score += float(branch_result["score"]) * 0.05
        if node.normal_summon_required:
            if not state.use_normal_summon():
                return failed(graph, completed, node.name, "normal_summon_used", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        if node.once_per_turn_tag:
            if not state.use_once_per_turn(node.once_per_turn_tag):
                return failed(graph, completed, node.name, "once_per_turn_conflict", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        missing_cards = [
            card
            for card in node.requires_cards
            if not resource_has_anywhere(state, card)
        ]
        if missing_cards:
            return failed(graph, completed, node.name, f"missing_required_card: {', '.join(missing_cards)}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for card in node.requires_in_deck:
            if not state.has_card("deck", card) and not state.has_card("hand", card) and not state.has_card("field", card):
                return failed(graph, completed, node.name, f"missing_search_target: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for card in node.requires_in_extra:
            if not state.has_card("extra_deck", card) and not state.has_card("field", card):
                return failed(graph, completed, node.name, f"missing_extra_deck_card: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for card in node.cost_cards:
            if not consume_anywhere(state, card):
                return failed(graph, completed, node.name, f"cost_unavailable: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
            resource_score -= 0.4
        typed_material_node = bool(node.synchro_requirements or node.fusion_materials or node.named_materials or node.generic_materials or node.ritual_level_requirement or node.link_requirements or getattr(node, "xyz_requirements", ()))
        if not typed_material_node:
            for card in node.consumes_cards:
                if card in node.cost_cards:
                    continue
                if not consume_anywhere(state, card):
                    return failed(graph, completed, node.name, f"cost_unavailable: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
                resource_score -= 0.4
        for card in node.sends_to_gy:
            if state.has_card("deck", card):
                state.move_card("deck", "graveyard", card)
            elif state.has_card("hand", card):
                state.move_card("hand", "graveyard", card)
            else:
                return failed(graph, completed, node.name, f"missing_required_card: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for card in node.required_materials:
            if not resource_has_anywhere(state, card):
                return failed(graph, completed, node.name, f"missing_material: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        typed_failure = validate_typed_materials(state, node)
        if typed_failure:
            return failed(graph, completed, node.name, typed_failure, endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        if not typed_material_node:
            for card in node.consumes_materials:
                if not consume_anywhere(state, card):
                    return failed(graph, completed, node.name, f"missing_material: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
                resource_score -= 0.25
        if node.search_card:
            if state.has_card("deck", node.search_card):
                state.search_deck(node.search_card)
            elif not state.has_card("hand", node.search_card) and not state.has_card("field", node.search_card):
                return failed(graph, completed, node.name, f"missing_search_target: {node.search_card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        if node.extra_deck_card:
            if not state.has_card("extra_deck", node.extra_deck_card) and not state.has_card("field", node.extra_deck_card):
                return failed(graph, completed, node.name, f"missing_extra_deck_card: {node.extra_deck_card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
            if state.has_card("extra_deck", node.extra_deck_card):
                state.summon_from_extra(node.extra_deck_card)
        if node.summon_card:
            if node.summon_type == "normal" and state.has_card("hand", node.summon_card):
                state.summon_from_hand(node.summon_card)
            elif node.summon_type == "special":
                if state.has_card("hand", node.summon_card):
                    state.summon_from_hand(node.summon_card)
                elif state.has_card("deck", node.summon_card):
                    state.summon_from_deck(node.summon_card)
                elif not state.has_card("field", node.summon_card):
                    return failed(graph, completed, node.name, f"payoff_unreachable: {node.summon_card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
            elif node.summon_type == "ritual":
                if state.has_card("hand", node.summon_card):
                    state.summon_from_hand(node.summon_card)
                elif not state.has_card("field", node.summon_card):
                    return failed(graph, completed, node.name, f"payoff_unreachable: {node.summon_card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        for card in node.produces_cards:
            state.add_card("hand", card)
            resource_score += 0.25
        for card in node.produces_to_field:
            state.add_card("field", card)
        for card in node.produces_to_gy:
            state.add_card("graveyard", card)
        for card, source, destination in node.moves_cards:
            if not state.move_card(source, destination, card):
                return failed(graph, completed, node.name, f"missing_required_card: {card}", endboard, interruption_points, payoff_score, resource_score, risk_score, state)
        locks.update(node.locks_applied)
        for lock in node.locks_applied:
            state.apply_lock(lock)
        interruption_points.extend(node.interruption_points)
        payoff_score += node.payoff_score
        risk_score += len(node.interruption_points) * 0.35
        completed.append(node.name)
        state.record_event("node_completed", node.name)
        state.record_event("effect_resolved", node.name)

    endboard = list(graph.endboard)
    follow_up = sum(1 for option in graph.recovery_options if resource_has_anywhere(state, option)) + len(graph.recovery_options)
    final_line_score = payoff_score + branch_score * 0.4 + len(endboard) * 1.2 + follow_up * 0.4 + resource_score * 0.25 - risk_score
    return {
        "valid": True,
        "line_name": graph.name,
        "completed_nodes": completed,
        "failed_node": None,
        "failure_reason": None,
        "endboard": endboard,
        "follow_up": follow_up,
        "interruption_points": interruption_points,
        "payoff_score": round(payoff_score, 2),
        "resource_score": round(resource_score, 2),
        "risk_score": round(risk_score, 2),
        "chosen_branches": chosen_branches,
        "branch_score": round(branch_score, 2),
        "chain_windows": chain_windows,
        "interruption_window_count": len(chain_windows),
        "interruption_risk": round(estimate_interruption_risk(chain_windows) + interruption_risk, 2),
        "resilience_score": estimate_recovery_adjusted_resilience(estimate_interruption_risk(chain_windows) + interruption_risk, sorted(recovery_routes_seen)),
        "recovery_routes_seen": sorted(recovery_routes_seen),
        "final_line_score": round(max(0.0, final_line_score), 2),
        "resource_movements": list(state.movements),
        "resource_state": state.snapshot(),
    }


def validate_graph_lines(
    hand: list[dict[str, Any]],
    archetype: str,
    deck: list[dict[str, Any]] | None = None,
    extra_deck: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return [validate_line(hand, graph, deck=deck, extra_deck=extra_deck) for graph in line_graphs_for_archetype(archetype)]


def failed(
    graph: LineGraph,
    completed: list[str],
    failed_node: str,
    reason: str,
    endboard: list[str],
    interruption_points: list[str],
    payoff_score: float,
    resource_score: float,
    risk_score: float,
    state: ResourceState | None = None,
) -> dict[str, Any]:
    return {
        "valid": False,
        "line_name": graph.name,
        "completed_nodes": completed,
        "failed_node": failed_node,
        "failure_reason": reason,
        "endboard": endboard,
        "follow_up": 0,
        "interruption_points": interruption_points,
        "payoff_score": round(payoff_score, 2),
        "resource_score": round(resource_score, 2),
        "risk_score": round(risk_score + 1.0, 2),
        "chosen_branches": [],
        "branch_score": 0.0,
        "chain_windows": [],
        "interruption_window_count": 0,
        "interruption_risk": 0.0,
        "resilience_score": 0.0,
        "recovery_routes_seen": [],
        "final_line_score": 0.0,
        "resource_movements": list(state.movements) if state else [],
        "resource_state": state.snapshot() if state else {},
    }


def build_resource_state(
    hand: list[dict[str, Any]],
    deck: list[dict[str, Any]] | None,
    extra_deck: list[dict[str, Any]] | None,
) -> ResourceState:
    hand_names = [str(card.get("name", "")) for card in hand]
    deck_cards = deck or hand
    extra_cards = extra_deck or [card for card in deck_cards if is_extra_deck_card(card)]
    main_deck_names = [str(card.get("name", "")) for card in deck_cards if not is_extra_deck_card(card)]
    extra_deck_names = [str(card.get("name", "")) for card in extra_cards]
    deck_counter = Counter(main_deck_names)
    for name in hand_names:
        if deck_counter[name] > 0:
            deck_counter[name] -= 1
    remaining_main_deck = []
    remaining_counts = Counter(deck_counter)
    for card in deck_cards:
        name = str(card.get("name", ""))
        if is_extra_deck_card(card):
            continue
        if remaining_counts[name] > 0:
            remaining_main_deck.append(card)
            remaining_counts[name] -= 1
    return ResourceState(hand=hand, deck=remaining_main_deck, extra_deck=extra_cards)


def resource_has_anywhere(state: ResourceState, card_name: str) -> bool:
    return any(state.has_card(location, card_name) for location in ("hand", "field", "graveyard", "deck", "extra_deck"))


def consume_anywhere(state: ResourceState, card_name: str) -> bool:
    for location in ("hand", "field", "graveyard", "deck"):
        if state.consume_card(location, card_name):
            return True
    return False


def validate_typed_materials(state: ResourceState, node: Any) -> str | None:
    location = getattr(node, "material_location", "hand") or "hand"
    if node.summon_type == "synchro" and node.synchro_requirements:
        if not any(requirement.get("tuner") and state.has_matching_card(location, requirement) for requirement in node.synchro_requirements):
            return "missing_tuner"
        if not any(requirement.get("non_tuner") and state.has_matching_card(location, requirement) for requirement in node.synchro_requirements):
            return "missing_non_tuner"
        target_level = target_card_level(state, node.extra_deck_card)
        combo = find_material_combo(state, location, node.synchro_requirements, exact_level=target_level or None)
        if combo is None and target_level:
            fallback_combo = find_material_combo(state, location, node.synchro_requirements)
            if fallback_combo is not None:
                return "synchro_level_mismatch"
        if combo is None:
            return "missing_generic_material"
        consume_combo(state, location, combo)
        return None

    if node.summon_type == "fusion":
        if node.named_materials:
            combo = find_material_combo(state, location, node.named_materials)
            if combo is None:
                return "missing_named_material"
            consume_combo(state, location, combo)
        if node.fusion_materials and state.consume_materials(location, node.fusion_materials) is None:
            return "missing_generic_material"
        if node.generic_materials and state.consume_materials(location, node.generic_materials) is None:
            return "missing_generic_material"
        return None

    if node.summon_type == "ritual":
        if node.ritual_spell and node.ritual_spell not in node.cost_cards and not resource_has_anywhere(state, node.ritual_spell):
            return "missing_ritual_spell"
        target_level = target_card_level(state, node.summon_card)
        required_level = node.ritual_level_requirement or target_level
        if required_level:
            requirements = node.typed_materials or ({"monster": True},)
            candidates = []
            for requirement in requirements:
                candidates.extend(state.find_cards(location, requirement))
            if node.summon_card:
                candidates = [card for card in candidates if card != node.summon_card]
            total_level = sum(get_card_level(state.card_objects.get(card, card)) for card in candidates)
            if total_level < required_level:
                return "insufficient_levels"
            consumed_level = 0
            consumed = []
            for card in candidates:
                if state.consume_card(location, card):
                    consumed.append(card)
                    consumed_level += get_card_level(state.card_objects.get(card, card))
                    if consumed_level >= required_level:
                        break
            if consumed_level < required_level:
                for card in consumed:
                    state.add_card(location, card)
                return "missing_ritual_tribute"
        return None

    if node.summon_type == "xyz":
        requirements = getattr(node, "xyz_requirements", ()) or node.typed_materials
        target_rank = target_card_rank(state, node.extra_deck_card)
        material_count = getattr(node, "xyz_material_count", None) or len(requirements) or 2
        if requirements:
            combo = find_material_combo(state, location, requirements)
        else:
            combo = find_level_matched_cards(state, location, target_rank, material_count)
        if combo is None:
            return "missing_xyz_materials"
        if target_rank and any(get_card_level(state.card_objects.get(card, card)) != target_rank for card in combo):
            return "xyz_level_mismatch"
        consume_combo(state, location, combo)
        return None

    if node.summon_type == "link" and node.link_requirements:
        target_rating = target_link_rating(state, node.extra_deck_card)
        required_count = getattr(node, "link_material_count", None) or target_rating or len(node.link_requirements)
        combo = find_material_combo(state, location, node.link_requirements)
        if combo is None or len(combo) < required_count:
            return "missing_link_materials"
        consume_combo(state, location, combo)
    return None


def target_card_level(state: ResourceState, card_name: str | None) -> int:
    if not card_name:
        return 0
    return get_card_level(state.card_objects.get(card_name, card_name))


def target_card_rank(state: ResourceState, card_name: str | None) -> int:
    if not card_name:
        return 0
    return get_card_rank(state.card_objects.get(card_name, card_name))


def target_link_rating(state: ResourceState, card_name: str | None) -> int:
    if not card_name:
        return 0
    return get_link_rating(state.card_objects.get(card_name, card_name))


def find_material_combo(
    state: ResourceState,
    location: str,
    requirements: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    exact_level: int | None = None,
) -> list[str] | None:
    requirement_list = list(requirements)
    if not requirement_list:
        return []
    zone_counts = state._zone(location).copy()
    candidates_by_requirement = [state.find_cards(location, requirement) for requirement in requirement_list]
    if any(not candidates for candidates in candidates_by_requirement):
        return None

    def choose(index: int, chosen: list[str]) -> list[str] | None:
        if index >= len(candidates_by_requirement):
            if exact_level:
                total = sum(get_card_level(state.card_objects.get(card, card)) for card in chosen)
                if total != exact_level:
                    return None
            return list(chosen)
        for card in candidates_by_requirement[index]:
            if zone_counts[card] <= 0:
                continue
            zone_counts[card] -= 1
            chosen.append(card)
            result = choose(index + 1, chosen)
            if result is not None:
                return result
            chosen.pop()
            zone_counts[card] += 1
        return None

    return choose(0, [])


def find_level_matched_cards(state: ResourceState, location: str, level: int, count: int) -> list[str] | None:
    if not level or count <= 0:
        return None
    matches = [
        card
        for card in state.find_cards(location, {"monster": True})
        if get_card_level(state.card_objects.get(card, card)) == level
    ]
    return matches[:count] if len(matches) >= count else None


def consume_combo(state: ResourceState, location: str, cards: list[str]) -> None:
    for card in cards:
        state.consume_card(location, card)


def chain_effect_type(node: Any) -> str:
    if node.search_card or node.action_type == "search" or any(effect.get("type") == "search" for branch in getattr(node, "branches", ()) for effect in branch.get("effects", ())):
        return "search"
    if node.sends_to_gy or node.action_type == "send_to_gy":
        return "send_to_gy"
    if node.summon_type == "special":
        return "summon_chain"
    if node.summon_card or "monster" in node.action_type:
        return "monster_effect"
    if "gy" in node.action_type:
        return "gy_effect"
    return "field_effect"


def choose_branch(state: ResourceState, branches: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> dict[str, Any]:
    valid = []
    failures = []
    for branch in branches:
        failure = branch_failure_reason(state, branch)
        if failure:
            failures.append(failure)
            continue
        valid.append(branch)
    if not valid:
        return {"valid": False, "failure_reason": failures[0] if failures else "no_valid_branch"}
    chosen = max(valid, key=lambda item: float(item.get("score", 0) or 0))
    for cost in chosen.get("costs", ()):
        failure = apply_cost(state, cost)
        if failure:
            return {"valid": False, "failure_reason": failure}
    for effect in chosen.get("effects", ()):
        failure = apply_branch_effect(state, effect)
        if failure:
            return {"valid": False, "failure_reason": failure}
    name = str(chosen.get("name", "unnamed branch"))
    state.record_event("branch_chosen", name)
    state.record_event("effect_resolved", name)
    return {"valid": True, "name": name, "score": float(chosen.get("score", 0) or 0)}


def branch_failure_reason(state: ResourceState, branch: dict[str, Any]) -> str | None:
    for condition in branch.get("conditions", ()):
        if not can_satisfy_condition(state, condition):
            return condition_failure_reason(condition)
    for cost in branch.get("costs", ()):
        if not can_pay_cost(state, cost):
            cost_type = str(cost.get("type", ""))
            if cost_type == "reveal":
                return "cost_reveal_unavailable"
            if cost_type == "discard":
                return "cost_discard_unavailable"
            if cost_type == "send_to_gy":
                return "cost_send_unavailable"
            if cost_type == "banish":
                return "cost_banish_unavailable"
            return "cost_unavailable"
    for effect in branch.get("effects", ()):
        failure = branch_effect_availability_failure(state, effect)
        if failure:
            return failure
    return None


def branch_effect_availability_failure(state: ResourceState, effect: dict[str, Any]) -> str | None:
    effect_type = str(effect.get("type", ""))
    card = str(effect.get("card", ""))
    if effect_type == "search" and card and not (state.has_card("deck", card) or state.has_card("hand", card) or state.has_card("field", card)):
        return f"condition_target_unavailable: {card}"
    if effect_type == "special_summon" and card and not (state.has_card("hand", card) or state.has_card("deck", card) or state.has_card("field", card)):
        return f"condition_target_unavailable: {card}"
    return None


def apply_branch_effect(state: ResourceState, effect: dict[str, Any]) -> str | None:
    effect_type = str(effect.get("type", ""))
    card = str(effect.get("card", ""))
    if effect_type == "search" and card:
        if state.has_card("deck", card):
            state.search_deck(card)
        else:
            state.record_event("searched", card, {"already_accessible": True})
        return None
    if effect_type == "special_summon" and card:
        if state.has_card("hand", card):
            state.summon_from_hand(card)
        elif state.has_card("deck", card):
            state.summon_from_deck(card)
        else:
            state.record_event("special_summoned", card, {"already_accessible": True})
        return None
    if effect_type == "activate" and card:
        state.record_event("activated", card)
        return None
    if effect_type == "mark_setup" and card:
        state.record_event("effect_resolved", card)
        return None
    state.record_event("effect_resolved", effect_type or "branch_effect")
    return None


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    card_type = str(card.get("type", "")).lower()
    return any(extra_type in card_type for extra_type in ("fusion", "synchro", "xyz", "link"))
