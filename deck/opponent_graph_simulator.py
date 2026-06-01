from __future__ import annotations

from collections import Counter
from typing import Any

from deck.opponent_branch_graph import OpponentActionNode, OpponentBranchGraph
from deck.opponent_resource_state import OpponentResourceState
from deck.timing_windows import best_timing_for_interruption, is_poor_timing

INTERRUPTION_ALIASES = {
    "Ash Blossom": ("ash blossom", "ash blossom & joyous spring"),
    "Droll & Lock Bird": ("droll",),
    "D.D. Crow": ("d.d. crow", "dd crow"),
    "Ghost Belle": ("ghost belle", "ghost belle & haunted mansion"),
    "Infinite Impermanence": ("infinite impermanence", "imperm"),
    "Effect Veiler": ("effect veiler", "veiler"),
    "Nibiru": ("nibiru",),
    "Cosmic Cyclone": ("cosmic cyclone",),
    "Harpie's Feather Duster": ("harpie", "feather duster"),
    "Lightning Storm": ("lightning storm",),
    "Evenly Matched": ("evenly matched",),
    "Book of Eclipse": ("book of eclipse",),
    "Called by the Grave": ("called by the grave",),
    "Bystial": ("bystial",),
    "Dimension Shifter": ("dimension shifter",),
    "Kaiju": ("kaiju",),
}


def simulate_opponent_graph(opponent_graph: OpponentBranchGraph, available_interruptions: list[str], probability_estimates: dict[str, float] | None = None) -> dict[str, Any]:
    normalized = [normalize_interruption(card) for card in available_interruptions]
    interruptions = [card for card in normalized if card]
    route_results = []
    stop_scores = []
    pivot_scores = []
    reduction_scores = []
    timing_scores = []
    best_interruptions: Counter[str] = Counter()
    best_nodes: Counter[str] = Counter()
    poor_nodes: Counter[str] = Counter()
    resource_valid = 0
    resource_fail = 0
    pivot_success = 0
    backup_success = 0
    missing_card_failures: Counter[str] = Counter()
    missing_extra_failures: Counter[str] = Counter()
    once_per_turn_failures = 0
    normal_summon_failures = 0

    for starter in opponent_graph.starter_nodes:
        state = initial_resource_state(opponent_graph)
        current = starter
        visited = set()
        route = []
        route_best = None
        route_stop = 0.0
        route_pivot = 0.0
        route_reduction = 0.0
        route_timing = 0.0
        while current and current in opponent_graph.nodes and current not in visited:
            visited.add(current)
            node = opponent_graph.nodes[current]
            resource_check = validate_and_apply_node_resources(state, node)
            if resource_check["valid"]:
                resource_valid += 1
            else:
                resource_fail += 1
                reason = str(resource_check.get("reason", "resource_failure"))
                if reason == "missing_extra_deck_card":
                    missing_extra_failures[str(resource_check.get("card", ""))] += 1
                elif reason == "once_per_turn_used":
                    once_per_turn_failures += 1
                elif reason == "normal_summon_used":
                    normal_summon_failures += 1
                else:
                    missing_card_failures[str(resource_check.get("card", reason))] += 1
                if node.if_interrupted_go_to and node.if_interrupted_go_to in opponent_graph.nodes:
                    pivot_success += 1
                    current = node.if_interrupted_go_to
                    route.append({"node": node_to_dict(node), "resource_check": resource_check, "resource_pivot": current, "hits": [], "poor": []})
                    continue
                route.append({"node": node_to_dict(node), "resource_check": resource_check, "resource_stopped": True, "hits": [], "poor": []})
                break
            tests = [test_interruption_at_node(node, interruption) for interruption in interruptions]
            hits = [test for test in tests if test["legal"] and test["stop_rate"] > 0]
            poor = [test for test in tests if not test["legal"] or test["poor_timing"]]
            if hits:
                best = max(hits, key=lambda item: (item["stop_rate"], item["endboard_reduction"], item["timing_precision"]))
                route_best = best if route_best is None or best["stop_rate"] > route_best["stop_rate"] else route_best
                best_interruptions[str(best["interruption"])] += 1
                best_nodes[node.node_id] += 1
                route_stop = max(route_stop, best["stop_rate"])
                route_reduction = max(route_reduction, best["endboard_reduction"])
                route_timing = max(route_timing, best["timing_precision"])
            for bad in poor:
                poor_nodes[node.node_id] += 1
            pivot = 1.0 if node.if_interrupted_go_to else 0.0
            if node.if_interrupted_go_to:
                backup_success += 1
            route_pivot = max(route_pivot, pivot * max(0.1, 1.0 - route_stop * 0.5))
            route.append({"node": node_to_dict(node), "resource_check": resource_check, "hits": hits, "poor": poor})
            current = node.if_resolved_go_to
        stop_scores.append(route_stop)
        pivot_scores.append(route_pivot)
        reduction_scores.append(route_reduction)
        timing_scores.append(route_timing)
        route_results.append(
            {
                "starter_node": starter,
                "route": route,
                "best_interruption": route_best,
                "graph_stop_rate": round(route_stop, 4),
                "graph_pivot_rate": round(route_pivot, 4),
                "graph_endboard_reduction_score": round(route_reduction, 4),
                "graph_timing_precision_score": round(route_timing, 4),
            }
        )

    graph_stop_rate = average(stop_scores)
    graph_pivot_rate = average(pivot_scores)
    opponent_resource_valid_rate = round(resource_valid / max(resource_valid + resource_fail, 1), 4)
    opponent_backup_success_rate = round(backup_success / max(resource_valid + resource_fail, 1), 4)
    probability_metrics = probability_weighted_metrics(
        probability_estimates,
        opponent_resource_valid_rate,
        graph_stop_rate,
        graph_pivot_rate,
        opponent_backup_success_rate,
    )
    return {
        "graph_name": opponent_graph.graph_name,
        "opponent": opponent_graph.opponent_archetype,
        "graph_route": [node_to_dict(opponent_graph.nodes[node_id]) for node_id in opponent_graph.starter_nodes if node_id in opponent_graph.nodes],
        "route_results": route_results,
        "graph_stop_rate": graph_stop_rate,
        "graph_pivot_rate": graph_pivot_rate,
        "graph_endboard_reduction_score": average(reduction_scores),
        "graph_timing_precision_score": average(timing_scores),
        "best_interruptions": [name for name, _count in best_interruptions.most_common()],
        "best_interruption_nodes": [node_id for node_id, _count in best_nodes.most_common()],
        "poor_interruption_nodes": [node_id for node_id, _count in poor_nodes.most_common()],
        "graph_best_interruption_count": len(best_nodes),
        "graph_poor_interruption_count": len(poor_nodes),
        "opponent_resource_valid_rate": opponent_resource_valid_rate,
        "opponent_resource_failure_rate": round(resource_fail / max(resource_valid + resource_fail, 1), 4),
        "opponent_pivot_success_rate": round(pivot_success / max(resource_fail, 1), 4) if resource_fail else 0.0,
        "opponent_backup_success_rate": opponent_backup_success_rate,
        "opponent_missing_card_failures": dict(missing_card_failures.most_common(10)),
        "opponent_missing_extra_failures": dict(missing_extra_failures.most_common(10)),
        "opponent_once_per_turn_failures": once_per_turn_failures,
        "opponent_normal_summon_failures": normal_summon_failures,
        **probability_metrics,
    }


def test_interruption_at_node(node: OpponentActionNode, interruption: str) -> dict[str, Any]:
    legal = node.response_window and (
        any(matches(interruption, vulnerable) for vulnerable in node.vulnerable_to)
        or bool(best_timing_for_interruption(interruption, (node.timing_window,)))
    )
    poor_timing = is_poor_timing(interruption, node.timing_window)
    stop_rate = 0.0
    if legal:
        stop_rate = min(0.95, 0.35 + node.risk_score * 0.35 + (0.15 if any(matches(interruption, vulnerable) for vulnerable in node.vulnerable_to) else 0.0))
    timing_precision = stop_rate * (1.0 if not poor_timing else 0.45)
    return {
        "interruption": interruption,
        "node_id": node.node_id,
        "action_name": node.action_name,
        "timing_window": node.timing_window,
        "legal": legal,
        "poor_timing": poor_timing,
        "stop_rate": round(stop_rate, 4),
        "pivot_route": node.if_interrupted_go_to,
        "endboard_reduction": round(min(1.0, stop_rate * node.payoff_score / 4), 4),
        "timing_precision": round(timing_precision, 4),
        "outcome_if_interrupted": node.if_interrupted_go_to or "line stopped",
        "outcome_if_not_interrupted": node.if_resolved_go_to or "endboard established",
    }


def node_to_dict(node: OpponentActionNode) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "action_name": node.action_name,
        "card": node.card,
        "action_type": node.action_type,
        "timing_window": node.timing_window,
        "vulnerable_to": list(node.vulnerable_to),
        "if_interrupted_go_to": node.if_interrupted_go_to,
        "if_resolved_go_to": node.if_resolved_go_to,
        "endboard_additions": list(node.endboard_additions),
        "risk_score": node.risk_score,
        "payoff_score": node.payoff_score,
        "requires_in_hand": list(node.requires_in_hand),
        "requires_in_deck": list(node.requires_in_deck),
        "requires_on_field": list(node.requires_on_field),
        "requires_in_gy": list(node.requires_in_gy),
        "requires_in_extra": list(node.requires_in_extra),
    }


def initial_resource_state(graph: OpponentBranchGraph) -> OpponentResourceState:
    hand: list[str] = []
    deck: list[str] = []
    extra: list[str] = []
    starter_ids = set(graph.starter_nodes)
    backup_ids = set(graph.backup_routes)
    for node in graph.nodes.values():
        if node.node_id in starter_ids or node.node_id in backup_ids or node.action_type == "backup":
            hand.extend(node.requires_in_hand)
        deck.extend(node.requires_in_deck)
        deck.extend(node.searches_from_deck)
        deck.extend(node.summons_from_deck)
        extra.extend(node.requires_in_extra)
        extra.extend(node.summons_from_extra)
        for route in node.recovery_routes:
            if route and route not in hand and route not in deck:
                hand.append(route)
    hand = list(dict.fromkeys(hand))
    deck = [card for card in dict.fromkeys(deck) if card not in hand]
    extra = list(dict.fromkeys(extra))
    return OpponentResourceState(hand=hand, deck=deck, extra_deck=extra)


def validate_and_apply_node_resources(state: OpponentResourceState, node: OpponentActionNode) -> dict[str, Any]:
    if node.normal_summon_required:
        if state.used_normal_summon:
            return {"valid": False, "reason": "normal_summon_used", "card": node.card}
        state.used_normal_summon = True
        state.record_event("normal_summon", node.card)
    if node.once_per_turn_tag and not state.use_once_per_turn(node.once_per_turn_tag):
        return {"valid": False, "reason": "once_per_turn_used", "card": node.once_per_turn_tag}
    for location, cards, reason in (
        ("hand", node.requires_in_hand, "missing_required_card"),
        ("deck", node.requires_in_deck, "missing_required_card"),
        ("field", node.requires_on_field, "missing_required_card"),
        ("graveyard", node.requires_in_gy, "missing_required_card"),
        ("extra_deck", node.requires_in_extra, "missing_extra_deck_card"),
    ):
        for card in cards:
            if not state.has_card(location, card):
                return {"valid": False, "reason": reason, "card": card, "location": location}
    for card in node.consumes_from_hand:
        if not state.consume_card("hand", card):
            return {"valid": False, "reason": "cost_unavailable", "card": card, "location": "hand"}
    for card in node.consumes_from_field:
        if not state.consume_card("field", card):
            return {"valid": False, "reason": "cost_unavailable", "card": card, "location": "field"}
    for card in node.summons_from_hand:
        if not state.summon_from_hand(card):
            return {"valid": False, "reason": "missing_required_card", "card": card, "location": "hand"}
    for card in node.searches_from_deck:
        if not state.search_deck(card):
            return {"valid": False, "reason": "missing_required_card", "card": card, "location": "deck"}
    for card in node.summons_from_deck:
        if not state.summon_from_deck(card):
            return {"valid": False, "reason": "missing_required_card", "card": card, "location": "deck"}
    for card in node.summons_from_extra:
        if not state.summon_from_extra(card):
            return {"valid": False, "reason": "missing_extra_deck_card", "card": card, "location": "extra_deck"}
    for card in node.adds_to_hand:
        state.add_card("hand", card)
    for card in node.sets_to_field:
        state.add_card("field", card)
    for card in node.sends_to_gy:
        if not state.send_to_gy(card):
            state.add_card("graveyard", card)
    for card in node.banishes_from_gy:
        if not state.banish_from_gy(card):
            return {"valid": False, "reason": "missing_required_card", "card": card, "location": "graveyard"}
    return {"valid": True, "reason": None}


def matches(left: str, right: str) -> bool:
    l = left.casefold()
    r = right.casefold()
    return l in r or r in l


def normalize_interruption(card_name: str) -> str | None:
    lowered = str(card_name).casefold()
    for label, aliases in INTERRUPTION_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return label
    return None


def average(values: list[float]) -> float:
    return round(sum(values) / max(len(values), 1), 4)


def probability_weighted_metrics(
    estimates: dict[str, float] | None,
    resource_valid_rate: float,
    graph_stop_rate: float,
    graph_pivot_rate: float,
    backup_success_rate: float,
) -> dict[str, float]:
    estimates = estimates or {}
    line_access = float(estimates.get("opponent_likely_line_access_rate", 1.0 if estimates else 0.0) or 0.0)
    backup_access = float(estimates.get("opponent_backup_line_access_rate", line_access) or 0.0)
    return {
        "opponent_starter_open_rate": round(float(estimates.get("opponent_starter_open_rate", 0.0) or 0.0), 4),
        "opponent_extender_open_rate": round(float(estimates.get("opponent_extender_open_rate", 0.0) or 0.0), 4),
        "opponent_interruption_open_rate": round(float(estimates.get("opponent_interruption_open_rate", 0.0) or 0.0), 4),
        "opponent_brick_rate": round(float(estimates.get("opponent_brick_rate", 0.0) or 0.0), 4),
        "probability_weighted_resource_valid_rate": round(resource_valid_rate * line_access, 4),
        "probability_weighted_stop_rate": round(graph_stop_rate * line_access, 4),
        "probability_weighted_pivot_rate": round(graph_pivot_rate * line_access, 4),
        "probability_weighted_backup_rate": round(backup_success_rate * backup_access, 4),
    }
