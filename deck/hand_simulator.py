from __future__ import annotations

import random
from collections import Counter
from statistics import mean
from typing import Any

from deck.combo_lines import ComboLine, combo_lines_for_archetype, line_is_available
from deck.interruption_profiles import InterruptionProfile, interruption_profiles, profile_by_name
from deck.line_validator import validate_graph_lines

HAND_SIZE = 5

HANDTRAP_TERMS = (
    "ash blossom",
    "effect veiler",
    "droll",
    "ghost belle",
    "ghost ogre",
    "nibiru",
    "d.d. crow",
    "infinite impermanence",
)
BOARD_BREAKER_TERMS = (
    "dark ruler no more",
    "evenly matched",
    "lightning storm",
    "raigeki",
    "harpie's feather duster",
    "forbidden droplet",
    "kaiju",
    "book of eclipse",
)


def sample_opening_hand(deck: list[dict[str, Any]], hand_size: int = HAND_SIZE) -> list[dict[str, Any]]:
    if len(deck) <= hand_size:
        return list(deck)
    return random.sample(deck, hand_size)


def simulate_hand(
    deck: list[dict[str, Any]],
    archetype: str,
    hand: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hand_cards = hand if hand is not None else sample_opening_hand(deck)
    hand_names = {str(card.get("name", "")) for card in hand_cards}
    lines = available_combo_lines(hand_names, archetype)
    graph_results = validate_graph_lines(
        hand_cards,
        archetype,
        deck=deck,
        extra_deck=[card for card in deck if is_extra_deck_card(card)],
    )
    valid_graphs = [result for result in graph_results if result["valid"]]
    best_graph = max(valid_graphs, key=lambda result: result["final_line_score"], default=None)
    failed_graphs = [result for result in graph_results if not result["valid"]]
    best_failed_graph = max(
        failed_graphs,
        key=lambda result: (
            len(result.get("completed_nodes", [])),
            float(result.get("payoff_score", 0) or 0),
            float(result.get("resource_score", 0) or 0),
            -float(result.get("risk_score", 0) or 0),
        ),
        default=None,
    )
    conflicts = detect_conflicts(hand_cards, lines, archetype)
    scored_lines = [(line, line_play_score(line, conflicts)) for line in lines]
    fallback_line, fallback_line_score = max(scored_lines, key=lambda item: item[1], default=(None, 0.0))
    best_line = fallback_line
    best_line_score = fallback_line_score
    if best_graph and best_graph["final_line_score"] >= best_line_score:
        best_line = None
        best_line_score = float(best_graph["final_line_score"])

    starter_count = sum(1 for card in hand_cards if is_starter(card, archetype))
    extender_count = sum(1 for card in hand_cards if is_extender(card))
    brick_count = sum(1 for card in hand_cards if is_brick(card))
    interruption_count = sum(1 for card in hand_cards if is_interruption(card))
    follow_up_count = sum(1 for card in hand_cards if is_follow_up(card))
    handtrap_count = sum(1 for card in hand_cards if has_name_term(card, HANDTRAP_TERMS))
    board_breaker_count = sum(1 for card in hand_cards if has_name_term(card, BOARD_BREAKER_TERMS))
    normal_summon_starters = sum(1 for line in lines if line.normal_summon_required)
    normal_summon_conflict = conflicts["normal_summon_conflict"]
    playable = bool(valid_graphs) or bool(lines) or starter_count > 0

    endboard = sorted({item for line in lines for item in line.endboard} | set(best_graph.get("endboard", []) if best_graph else []))
    recovery_routes = sorted({item for line in lines for item in line.recovery_routes})
    weak_to = sorted({item for line in lines for item in line.weak_to})

    line_score = best_line_score
    score = (
        line_score
        + starter_count * 1.4
        + extender_count * 1.0
        + interruption_count * 1.2
        + follow_up_count * 0.8
        + handtrap_count * 0.8
        + board_breaker_count * 0.8
        - brick_count * 1.3
        - (1.0 if normal_summon_conflict else 0.0)
    )

    return {
        "hand": [str(card.get("name", "")) for card in hand_cards],
        "playable": playable,
        "available_lines": [line.name for line in lines],
        "best_line": best_graph["line_name"] if best_graph else (best_line.name if best_line else None),
        "starter_count": starter_count,
        "extender_count": extender_count,
        "brick_count": brick_count,
        "interruption_count": interruption_count,
        "follow_up_count": follow_up_count,
        "handtrap_count": handtrap_count,
        "board_breaker_count": board_breaker_count,
        "normal_summon_conflict": normal_summon_conflict,
        "once_per_turn_conflicts": conflicts["once_per_turn_conflicts"],
        "dead_duplicate_count": conflicts["dead_duplicate_count"],
        "unsupported_piece_count": conflicts["unsupported_piece_count"],
        "payoff_without_enabler": conflicts["payoff_without_enabler"],
        "enabler_without_payoff": conflicts["enabler_without_payoff"],
        "conflicting_lines": conflicts["conflicting_lines"],
        "estimated_endboard": endboard,
        "recovery_routes": recovery_routes,
        "weak_to": weak_to,
        "best_line_score": round(best_line_score, 2),
        "graph_valid_lines": [result["line_name"] for result in valid_graphs],
        "best_graph_line": best_graph["line_name"] if best_graph else None,
        "graph_attempt_count": len(graph_results),
        "graph_valid_count": len(valid_graphs),
        "optional_line_failure_count": len(failed_graphs) if valid_graphs else 0,
        "best_line_failure": bool(graph_results and not valid_graphs),
        "no_valid_line": not bool(valid_graphs),
        "best_graph_failure_reason": best_failed_graph.get("failure_reason") if best_failed_graph else None,
        "normalized_failure_categories": normalized_failure_categories(best_failed_graph if not valid_graphs else None),
        "graph_failures": [
            {"line_name": result["line_name"], "failed_node": result["failed_node"], "failure_reason": result["failure_reason"]}
            for result in graph_results
            if not result["valid"]
        ],
        "resource_movements": best_graph.get("resource_movements", []) if best_graph else [],
        "graph_payoff_score": best_graph["payoff_score"] if best_graph else 0.0,
        "graph_resource_score": best_graph["resource_score"] if best_graph else 0.0,
        "graph_risk_score": best_graph["risk_score"] if best_graph else 0.0,
        "chosen_branches": best_graph.get("chosen_branches", []) if best_graph else [],
        "branch_score": best_graph.get("branch_score", 0.0) if best_graph else 0.0,
        "chain_windows": best_graph.get("chain_windows", []) if best_graph else [],
        "interruption_window_count": best_graph.get("interruption_window_count", 0) if best_graph else 0,
        "interruption_risk": best_graph.get("interruption_risk", 0.0) if best_graph else 0.0,
        "line_resilience_score": best_graph.get("resilience_score", 0.0) if best_graph else 0.0,
        "recovery_routes_seen": best_graph.get("recovery_routes_seen", []) if best_graph else [],
        "score": round(max(0.0, score), 2),
    }


def simulate_interrupted_hand(
    hand: list[dict[str, Any]],
    deck: list[dict[str, Any]],
    interruption_profile: InterruptionProfile | str,
    archetype: str = "Blue-Eyes",
) -> dict[str, Any]:
    profile = profile_by_name(interruption_profile) if isinstance(interruption_profile, str) else interruption_profile
    result = simulate_hand(deck, archetype, hand=hand)
    if profile is None:
        return {"profile": str(interruption_profile), "line_still_produces_payoff": bool(result.get("graph_valid_lines")), "recovery_route": None, "resilience_score": result.get("line_resilience_score", 0.0)}
    windows = result.get("chain_windows", [])
    vulnerable = any(profile.name in window.get("possible_responses", []) for window in windows)
    recovery_routes = result.get("recovery_routes_seen", []) or result.get("recovery_routes", [])
    recovered = bool(recovery_routes) and result.get("graph_valid_lines")
    line_still_produces_payoff = bool(result.get("graph_valid_lines")) and (not vulnerable or recovered)
    penalty = profile.risk_score + (profile.recovery_difficulty if vulnerable and not recovered else 0)
    resilience_score = max(0.0, float(result.get("line_resilience_score", 0.0) or 0.0) - (penalty if vulnerable else 0))
    return {
        "profile": profile.name,
        "vulnerable": vulnerable,
        "line_still_produces_payoff": line_still_produces_payoff,
        "recovery_route": recovery_routes[0] if recovered else None,
        "resilience_score": round(resilience_score, 2),
    }


def real_combo_report(deck: list[dict[str, Any]], archetype: str, samples: int = 100) -> dict[str, Any]:
    if not deck or samples < 1:
        return empty_real_combo_report()

    results = [simulate_hand(deck, archetype) for _ in range(samples)]
    playable_results = [result for result in results if result["playable"]]
    line_counter = Counter(
        line
        for result in results
        for line in result.get("available_lines", [])
    )
    best_line_counter = Counter(
        result["best_line"]
        for result in results
        if result.get("best_line")
    )
    choke_counter = Counter(
        weak
        for result in results
        for weak in result.get("weak_to", [])
    )

    playable_hand_rate = len(playable_results) / len(results)
    brick_rate = sum(1 for result in results if result["brick_count"] >= 2) / len(results)
    normal_summon_conflict_rate = sum(1 for result in results if result["normal_summon_conflict"]) / len(results)
    once_per_turn_conflict_rate = sum(1 for result in results if result["once_per_turn_conflicts"]) / len(results)
    dead_duplicate_rate = sum(1 for result in results if result["dead_duplicate_count"] > 0) / len(results)
    payoff_without_enabler_rate = sum(1 for result in results if result["payoff_without_enabler"]) / len(results)
    enabler_without_payoff_rate = sum(1 for result in results if result["enabler_without_payoff"]) / len(results)
    graph_valid_line_rate = sum(1 for result in results if result["graph_valid_lines"]) / len(results)
    graph_failed_line_rate = sum(1 for result in results if result["graph_failures"] and not result["graph_valid_lines"]) / len(results)
    optional_line_failure_rate = sum(1 for result in results if result.get("optional_line_failure_count", 0) > 0) / len(results)
    best_line_failure_rate = sum(1 for result in results if result.get("best_line_failure")) / len(results)
    no_valid_line_rate = sum(1 for result in results if result.get("no_valid_line")) / len(results)
    branch_valid_rate = sum(1 for result in results if result.get("chosen_branches")) / len(results)
    no_valid_branch_rate = sum(
        1
        for result in results
        for failure in result.get("graph_failures", [])
        if failure_category(failure.get("failure_reason")) == "no_valid_branch"
    ) / len(results)
    interruption_window_count = mean(result.get("interruption_window_count", 0) for result in results)
    average_interruption_risk = mean(float(result.get("interruption_risk", 0) or 0) for result in results)
    recovery_route_rate = sum(1 for result in results if result.get("recovery_routes_seen")) / len(results)
    interrupted_results = [
        simulate_interrupted_hand(
            [{"name": name} for name in result.get("hand", [])],
            deck,
            profile,
            archetype,
        )
        for result in results[: min(len(results), 20)]
        for profile in interruption_profiles()
    ]
    interrupted_line_success_rate = (
        sum(1 for item in interrupted_results if item.get("line_still_produces_payoff")) / len(interrupted_results)
        if interrupted_results
        else 0.0
    )
    resilience_score = mean(float(result.get("line_resilience_score", 0) or 0) for result in results)
    vulnerability_rates = {
        profile.name: (
            sum(1 for result in results if any(profile.name in window.get("possible_responses", []) for window in result.get("chain_windows", []))) / len(results)
        )
        for profile in interruption_profiles()
    }
    graph_failure_counter = Counter(
        failure["failure_reason"]
        for result in results
        for failure in result.get("graph_failures", [])
        if failure.get("failure_reason")
    )
    resource_failure_counter = Counter(
        failure_category(failure.get("failure_reason"))
        for result in results
        for failure in result.get("graph_failures", [])
        if failure.get("failure_reason")
    )
    normalized_failure_counter = Counter(
        category
        for result in results
        for category in result.get("normalized_failure_categories", [])
    )
    recovery_route_frequency = sum(1 for result in results if result.get("recovery_routes")) / len(results)
    average_endboard_score = mean(endboard_value(result.get("estimated_endboard", [])) for result in results)
    average_line_score = mean(result["score"] for result in results)
    interruption_resilience_score = mean(
        min(10.0, result["interruption_count"] * 1.5 + len(result.get("recovery_routes", [])) * 0.8)
        for result in results
    )
    follow_up_score = mean(min(10.0, result["follow_up_count"] * 1.4 + len(result.get("recovery_routes", [])) * 0.6) for result in results)

    return {
        "samples": samples,
        "playable_hand_rate": round(playable_hand_rate, 4),
        "brick_rate": round(brick_rate, 4),
        "average_brick_count": round(mean(result["brick_count"] for result in results), 2),
        "average_starter_count": round(mean(result["starter_count"] for result in results), 2),
        "average_extender_count": round(mean(result["extender_count"] for result in results), 2),
        "average_interruption_count": round(mean(result["interruption_count"] for result in results), 2),
        "most_common_combo_lines": line_counter.most_common(10),
        "best_line_frequency": best_line_counter.most_common(10),
        "average_endboard_score": round(average_endboard_score, 2),
        "combo_line_score": round(average_line_score, 2),
        "normal_summon_conflict_rate": round(normal_summon_conflict_rate, 4),
        "once_per_turn_conflict_rate": round(once_per_turn_conflict_rate, 4),
        "dead_duplicate_rate": round(dead_duplicate_rate, 4),
        "payoff_without_enabler_rate": round(payoff_without_enabler_rate, 4),
        "enabler_without_payoff_rate": round(enabler_without_payoff_rate, 4),
        "best_line_average_score": round(mean(result.get("best_line_score", 0) for result in results), 2),
        "graph_valid_line_rate": round(graph_valid_line_rate, 4),
        "graph_average_line_score": round(mean(result.get("best_line_score", 0) for result in results if result.get("graph_valid_lines")) if graph_valid_line_rate else 0.0, 2),
        "graph_average_payoff_score": round(mean(result.get("graph_payoff_score", 0) for result in results), 2),
        "graph_average_resource_score": round(mean(result.get("graph_resource_score", 0) for result in results), 2),
        "graph_average_risk_score": round(mean(result.get("graph_risk_score", 0) for result in results), 2),
        "graph_failed_line_rate": round(graph_failed_line_rate, 4),
        "optional_line_failure_rate": round(optional_line_failure_rate, 4),
        "best_line_failure_rate": round(best_line_failure_rate, 4),
        "no_valid_line_rate": round(no_valid_line_rate, 4),
        "branch_valid_rate": round(branch_valid_rate, 4),
        "no_valid_branch_rate": round(no_valid_branch_rate, 4),
        "average_branch_score": round(mean(result.get("branch_score", 0) for result in results), 2),
        "interruption_window_count": round(interruption_window_count, 2),
        "average_interruption_risk": round(average_interruption_risk, 2),
        "ash_vulnerability_rate": round(vulnerability_rates.get("Ash Blossom", 0.0), 4),
        "imperm_vulnerability_rate": round(vulnerability_rates.get("Infinite Impermanence", 0.0), 4),
        "veiler_vulnerability_rate": round(vulnerability_rates.get("Effect Veiler", 0.0), 4),
        "droll_vulnerability_rate": round(vulnerability_rates.get("Droll & Lock Bird", 0.0), 4),
        "crow_vulnerability_rate": round(vulnerability_rates.get("D.D. Crow", 0.0), 4),
        "nibiru_vulnerability_rate": round(vulnerability_rates.get("Nibiru", 0.0), 4),
        "recovery_route_rate": round(recovery_route_rate, 4),
        "interrupted_line_success_rate": round(interrupted_line_success_rate, 4),
        "resilience_score": round(resilience_score, 2),
        "most_common_graph_failure_reason": graph_failure_counter.most_common(1)[0][0] if graph_failure_counter else None,
        "resource_valid_line_rate": round(graph_valid_line_rate, 4),
        "missing_material_rate": round(resource_failure_counter["missing_material"] / len(results), 4),
        "missing_search_target_rate": round(resource_failure_counter["missing_search_target"] / len(results), 4),
        "missing_extra_deck_rate": round(resource_failure_counter["missing_extra_deck_card"] / len(results), 4),
        "cost_failure_rate": round(resource_failure_counter["cost_unavailable"] / len(results), 4),
        "normalized_search_failure_rate": round(normalized_failure_counter["search"] / len(results), 4),
        "normalized_cost_failure_rate": round(normalized_failure_counter["cost"] / len(results), 4),
        "normalized_material_failure_rate": round(normalized_failure_counter["material"] / len(results), 4),
        "normalized_extra_deck_failure_rate": round(normalized_failure_counter["extra_deck"] / len(results), 4),
        "cost_condition_valid_rate": round(1.0 - ((normalized_failure_counter["cost"] + normalized_failure_counter["condition"]) / len(results)), 4),
        "cost_failure_rate_normalized": round(normalized_failure_counter["cost"] / len(results), 4),
        "condition_failure_rate_normalized": round(normalized_failure_counter["condition"] / len(results), 4),
        "reveal_cost_failure_rate": round(normalized_failure_counter["reveal_cost"] / len(results), 4),
        "discard_cost_failure_rate": round(normalized_failure_counter["discard_cost"] / len(results), 4),
        "gy_condition_failure_rate": round(normalized_failure_counter["gy_condition"] / len(results), 4),
        "control_condition_failure_rate": round(normalized_failure_counter["control_condition"] / len(results), 4),
        "history_condition_failure_rate": round(normalized_failure_counter["history_condition"] / len(results), 4),
        "summon_history_failure_rate": round(normalized_failure_counter["summon_history"] / len(results), 4),
        "gy_history_failure_rate": round(normalized_failure_counter["gy_history"] / len(results), 4),
        "activation_history_failure_rate": round(normalized_failure_counter["activation_history"] / len(results), 4),
        "resolution_history_failure_rate": round(normalized_failure_counter["resolution_history"] / len(results), 4),
        "normal_summon_failure_rate": round(resource_failure_counter["normal_summon_used"] / len(results), 4),
        "once_per_turn_failure_rate": round(resource_failure_counter["once_per_turn_conflict"] / len(results), 4),
        "typed_material_valid_rate": round(graph_valid_line_rate, 4),
        "synchro_material_failure_rate": round(
            (resource_failure_counter["missing_tuner"] + resource_failure_counter["missing_non_tuner"]) / len(results),
            4,
        ),
        "fusion_material_failure_rate": round(
            (resource_failure_counter["missing_named_material"] + resource_failure_counter["missing_generic_material"]) / len(results),
            4,
        ),
        "ritual_material_failure_rate": round(
            (resource_failure_counter["missing_ritual_spell"] + resource_failure_counter["insufficient_levels"] + resource_failure_counter["missing_ritual_tribute"]) / len(results),
            4,
        ),
        "link_material_failure_rate": round(resource_failure_counter["missing_link_materials"] / len(results), 4),
        "named_material_failure_rate": round(resource_failure_counter["missing_named_material"] / len(results), 4),
        "synchro_exact_level_valid_rate": round(1.0 - normalized_failure_counter["synchro_level"] / len(results), 4),
        "synchro_level_failure_rate": round(normalized_failure_counter["synchro_level"] / len(results), 4),
        "ritual_level_valid_rate": round(1.0 - normalized_failure_counter["ritual_level"] / len(results), 4),
        "ritual_level_failure_rate": round(normalized_failure_counter["ritual_level"] / len(results), 4),
        "xyz_material_valid_rate": round(1.0 - normalized_failure_counter["xyz_material"] / len(results), 4),
        "link_material_valid_rate": round(1.0 - normalized_failure_counter["link_material"] / len(results), 4),
        "interruption_resilience_score": round(interruption_resilience_score, 2),
        "follow_up_score": round(follow_up_score, 2),
        "recovery_route_frequency": round(recovery_route_frequency, 4),
        "choke_point_frequency": choke_counter.most_common(10),
    }


def empty_real_combo_report() -> dict[str, Any]:
    return {
        "samples": 0,
        "playable_hand_rate": 0.0,
        "brick_rate": 0.0,
        "average_brick_count": 0.0,
        "average_starter_count": 0.0,
        "average_extender_count": 0.0,
        "average_interruption_count": 0.0,
        "most_common_combo_lines": [],
        "best_line_frequency": [],
        "average_endboard_score": 0.0,
        "combo_line_score": 0.0,
        "normal_summon_conflict_rate": 0.0,
        "once_per_turn_conflict_rate": 0.0,
        "dead_duplicate_rate": 0.0,
        "payoff_without_enabler_rate": 0.0,
        "enabler_without_payoff_rate": 0.0,
        "best_line_average_score": 0.0,
        "graph_valid_line_rate": 0.0,
        "graph_average_line_score": 0.0,
        "graph_average_payoff_score": 0.0,
        "graph_average_resource_score": 0.0,
        "graph_average_risk_score": 0.0,
        "graph_failed_line_rate": 0.0,
        "optional_line_failure_rate": 0.0,
        "best_line_failure_rate": 0.0,
        "no_valid_line_rate": 0.0,
        "branch_valid_rate": 0.0,
        "no_valid_branch_rate": 0.0,
        "average_branch_score": 0.0,
        "interruption_window_count": 0.0,
        "average_interruption_risk": 0.0,
        "ash_vulnerability_rate": 0.0,
        "imperm_vulnerability_rate": 0.0,
        "veiler_vulnerability_rate": 0.0,
        "droll_vulnerability_rate": 0.0,
        "crow_vulnerability_rate": 0.0,
        "nibiru_vulnerability_rate": 0.0,
        "recovery_route_rate": 0.0,
        "interrupted_line_success_rate": 0.0,
        "resilience_score": 0.0,
        "most_common_graph_failure_reason": None,
        "resource_valid_line_rate": 0.0,
        "missing_material_rate": 0.0,
        "missing_search_target_rate": 0.0,
        "missing_extra_deck_rate": 0.0,
        "cost_failure_rate": 0.0,
        "normalized_search_failure_rate": 0.0,
        "normalized_cost_failure_rate": 0.0,
        "normalized_material_failure_rate": 0.0,
        "normalized_extra_deck_failure_rate": 0.0,
        "cost_condition_valid_rate": 0.0,
        "cost_failure_rate_normalized": 0.0,
        "condition_failure_rate_normalized": 0.0,
        "reveal_cost_failure_rate": 0.0,
        "discard_cost_failure_rate": 0.0,
        "gy_condition_failure_rate": 0.0,
        "control_condition_failure_rate": 0.0,
        "history_condition_failure_rate": 0.0,
        "summon_history_failure_rate": 0.0,
        "gy_history_failure_rate": 0.0,
        "activation_history_failure_rate": 0.0,
        "resolution_history_failure_rate": 0.0,
        "normal_summon_failure_rate": 0.0,
        "once_per_turn_failure_rate": 0.0,
        "typed_material_valid_rate": 0.0,
        "synchro_material_failure_rate": 0.0,
        "fusion_material_failure_rate": 0.0,
        "ritual_material_failure_rate": 0.0,
        "link_material_failure_rate": 0.0,
        "named_material_failure_rate": 0.0,
        "synchro_exact_level_valid_rate": 0.0,
        "synchro_level_failure_rate": 0.0,
        "ritual_level_valid_rate": 0.0,
        "ritual_level_failure_rate": 0.0,
        "xyz_material_valid_rate": 0.0,
        "link_material_valid_rate": 0.0,
        "interruption_resilience_score": 0.0,
        "follow_up_score": 0.0,
        "recovery_route_frequency": 0.0,
        "choke_point_frequency": [],
    }


def available_combo_lines(hand_names: set[str], archetype: str) -> list[ComboLine]:
    return [
        line
        for line in combo_lines_for_archetype(archetype)
        if line_is_available(line, hand_names)
    ]


def detect_conflicts(hand_cards: list[dict[str, Any]], lines: list[ComboLine], archetype: str) -> dict[str, Any]:
    hand_names = [str(card.get("name", "")) for card in hand_cards]
    name_counts = Counter(hand_names)
    normal_summon_lines = [line.name for line in lines if line.normal_summon_required]
    tag_counts = Counter(tag for line in lines for tag in line.once_per_turn_tags)
    once_per_turn_conflicts = sorted(tag for tag, count in tag_counts.items() if count > 1)
    high_level_count = sum(1 for card in hand_cards if is_brick(card))
    dead_duplicate_count = sum(max(0, count - 1) for name, count in name_counts.items() if is_once_per_turn_name(name) or is_hard_payoff_name(name))
    enablers = sum(1 for card in hand_cards if is_starter(card, archetype) or is_extender(card) or is_searcher(card))
    payoffs = sum(1 for card in hand_cards if is_payoff(card))
    ritual_pieces = sum(1 for name in hand_names if "Chaos MAX" in name or name == "Chaos Form")
    dead_ritual = ritual_pieces == 1 and not any(name in hand_names for name in ("Bingo Machine, Go!!!", "Wishes for Eyes of Blue"))
    unsupported_piece_count = max(0, high_level_count - max(enablers, 1)) + (1 if dead_ritual else 0)
    payoff_without_enabler = payoffs > 0 and enablers == 0
    enabler_without_payoff = enablers > 0 and payoffs == 0 and not lines
    conflicting_lines = conflicting_line_names(lines)

    return {
        "normal_summon_conflict": len(normal_summon_lines) > 1,
        "once_per_turn_conflicts": once_per_turn_conflicts,
        "dead_duplicate_count": dead_duplicate_count,
        "unsupported_piece_count": unsupported_piece_count,
        "payoff_without_enabler": payoff_without_enabler,
        "enabler_without_payoff": enabler_without_payoff,
        "conflicting_lines": conflicting_lines,
    }


def line_play_score(line: ComboLine, conflicts: dict[str, Any]) -> float:
    score = line.effective_score
    score += len(line.endboard) * 0.8
    score += len(line.interruptions) * 1.0
    score += len(line.follow_up) * 0.5
    score += len(line.recovery_routes) * 0.35
    score -= line.brick_risk * 2.0
    if line.normal_summon_required and conflicts["normal_summon_conflict"]:
        score -= 1.5
    score -= len(conflicts["once_per_turn_conflicts"]) * 0.8
    score -= conflicts["dead_duplicate_count"] * 0.5
    score -= conflicts["unsupported_piece_count"] * 0.7
    if conflicts["payoff_without_enabler"]:
        score -= 1.5
    if conflicts["enabler_without_payoff"]:
        score -= 0.8
    return max(0.0, score)


def conflicting_line_names(lines: list[ComboLine]) -> list[str]:
    conflicts = []
    for index, line in enumerate(lines):
        for other in lines[index + 1 :]:
            if line.normal_summon_required and other.normal_summon_required:
                conflicts.append(f"{line.name} <> {other.name}: normal summon")
                continue
            if set(line.once_per_turn_tags).intersection(other.once_per_turn_tags):
                conflicts.append(f"{line.name} <> {other.name}: once per turn")
    return conflicts


def is_starter(card: dict[str, Any], archetype: str) -> bool:
    text = card_text(card)
    name = str(card.get("name", "")).lower()
    return (
        "normal summon" in text
        or "add 1" in text
        or "from your deck" in text
        or "bingo machine" in name
        or "wishes for eyes" in name
        or "sage with eyes" in name
        or "white stone" in name
        or "dictator of d" in name
    )


def is_extender(card: dict[str, Any]) -> bool:
    text = card_text(card)
    return (
        "special summon" in text
        or "summon this card" in text
        or "from your hand" in text
        or "from your graveyard" in text
        or "from your gy" in text
    )


def is_interruption(card: dict[str, Any]) -> bool:
    text = card_text(card)
    card_type = str(card.get("type", "")).lower()
    return (
        "negate" in text
        or "destroy" in text
        or "banish" in text
        or "shuffle" in text
        or "quick effect" in text
        or "trap" in card_type
        or has_name_term(card, HANDTRAP_TERMS)
    )


def is_follow_up(card: dict[str, Any]) -> bool:
    text = card_text(card)
    return "add" in text or "draw" in text or "graveyard" in text or "gy" in text or "set 1" in text


def is_searcher(card: dict[str, Any]) -> bool:
    text = card_text(card)
    return "add" in text or "from your deck" in text or "search" in text


def is_payoff(card: dict[str, Any]) -> bool:
    name = str(card.get("name", ""))
    text = card_text(card)
    return is_hard_payoff_name(name) or "fusion summon" in text or "ritual summon" in text


def is_once_per_turn_name(name: str) -> bool:
    lowered = name.lower()
    return any(term in lowered for term in ("bingo machine", "wishes for eyes", "ultimate fusion", "true light", "dictator of d"))


def is_hard_payoff_name(name: str) -> bool:
    lowered = name.lower()
    return any(term in lowered for term in ("chaos max", "ultimate dragon", "tyrant dragon", "spirit dragon", "jet dragon", "alternative white dragon"))


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    card_type = str(card.get("type", "")).lower()
    return any(extra_type in card_type for extra_type in ("fusion", "synchro", "xyz", "link"))


def is_brick(card: dict[str, Any]) -> bool:
    text = card_text(card)
    card_type = str(card.get("type", "")).lower()
    level = safe_int(card.get("level"))
    return level >= 7 and "special summon" not in text and "ritual" not in card_type and "fusion" not in card_type


def endboard_value(endboard: list[str]) -> float:
    value = 0.0
    for item in endboard:
        lowered = str(item).lower()
        value += 1.0
        if "negate" in lowered or "interruption" in lowered:
            value += 1.5
        if "protection" in lowered or "jet" in lowered:
            value += 1.0
        if "chaos max" in lowered or "spirit dragon" in lowered:
            value += 1.4
    return min(10.0, value)


def card_text(card: dict[str, Any]) -> str:
    return f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".lower()


def has_name_term(card: dict[str, Any], terms: tuple[str, ...]) -> bool:
    name = str(card.get("name", "")).lower()
    return any(term in name for term in terms)


def failure_category(reason: str | None) -> str:
    if not reason:
        return "unknown"
    return str(reason).split(":", 1)[0]


def normalized_failure_categories(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    category = failure_category(result.get("failure_reason"))
    if category in {"missing_search_target"}:
        return ["search"]
    if category in {"cost_unavailable"}:
        return ["cost"]
    if category in {"cost_reveal_unavailable"}:
        return ["cost", "reveal_cost"]
    if category in {"cost_discard_unavailable"}:
        return ["cost", "discard_cost"]
    if category in {"cost_send_unavailable", "cost_banish_unavailable"}:
        return ["cost"]
    if category in {"condition_control_unmet"}:
        return ["condition", "control_condition"]
    if category in {"condition_gy_unmet"}:
        return ["condition", "gy_condition"]
    if category in {"condition_target_unavailable", "activation_restriction_failed"}:
        return ["condition"]
    if category in {"no_valid_branch"}:
        return ["condition", "branch"]
    if category in {"history_condition_unmet"}:
        return ["condition", "history_condition"]
    if category in {"summon_history_missing"}:
        return ["condition", "history_condition", "summon_history"]
    if category in {"gy_history_missing"}:
        return ["condition", "history_condition", "gy_history"]
    if category in {"activation_history_missing"}:
        return ["condition", "history_condition", "activation_history"]
    if category in {"resolution_history_missing"}:
        return ["condition", "history_condition", "resolution_history"]
    if category in {"missing_extra_deck_card"}:
        return ["extra_deck"]
    if category in {
        "missing_material",
        "missing_tuner",
        "missing_non_tuner",
        "missing_named_material",
        "missing_generic_material",
        "missing_ritual_tribute",
    }:
        return ["material"]
    if category in {"insufficient_levels"}:
        return ["material", "ritual_level"]
    if category in {"synchro_level_mismatch"}:
        return ["material", "synchro_level"]
    if category in {"missing_xyz_materials", "xyz_level_mismatch"}:
        return ["material", "xyz_material"]
    if category in {"missing_link_materials"}:
        return ["material", "link_material"]
    return [category]


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
