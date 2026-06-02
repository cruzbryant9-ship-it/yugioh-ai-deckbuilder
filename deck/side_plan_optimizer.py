from __future__ import annotations

from collections import Counter, OrderedDict
from itertools import combinations
from typing import Any

from deck.builder import card_role_flags, score_deck_breakdown
from deck.choke_simulator import simulate_choke_points
from deck.curated_opponent_memory import (
    curated_memory_card_adjustment,
    curated_opponent_name,
    load_curated_opponent_memory,
)
from deck.matchup_profiles import MatchupProfile, get_matchup_profile
from deck.opponent_profiles import OpponentProfile
from deck.post_side_memory import load_post_side_memory, memory_card_adjustment
from deck.side_application import apply_side_plan
from deck.side_deck_planner import resolve_matchup_context
from SystemAIYugioh.banlist import get_card_limit

SIDE_COUNTS = (3, 6, 9, 12, 15)
CORE_TERMS = ("blue-eyes", "eyes of blue", "white stone", "dictator of d", "bingo machine")
SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES = 4096
SIDE_CANDIDATE_SCORE_CACHE: OrderedDict[tuple[tuple[str, ...], str, str], float] = OrderedDict()
SIDE_CANDIDATE_SCORE_STATS = {"hits": 0, "misses": 0}


def optimize_side_plan(
    main_deck: list[dict[str, Any]],
    side_deck: list[dict[str, Any]],
    matchup: str | MatchupProfile | OpponentProfile | None,
    going: str,
    card_pool: list[dict[str, Any]],
    max_candidates: int = 50,
    archetype: str = "",
    mode: str = "meta",
    use_memory: bool = True,
    probability_estimates: dict[str, float] | None = None,
) -> dict[str, Any]:
    profile = resolve_matchup_context(matchup)
    choke_report = simulate_choke_points(matchup, [str(card.get("name", "")) for card in side_deck], probability_estimates=probability_estimates)
    memory = load_post_side_memory(archetype, mode, profile.name, going) if use_memory and archetype else {}
    curated_memory = load_curated_opponent_memory(archetype, mode, matchup, going) if use_memory and archetype and curated_opponent_name(matchup) else {}
    game1_score = score_deck_breakdown(main_deck, archetype, mode).get("final_score", 0.0)
    candidate_side_ins = side_in_pool(side_deck, profile, going, memory, curated_memory, choke_report)
    candidate_side_outs = side_out_priority(main_deck, profile, going, memory, curated_memory)
    rejection_reasons: Counter[str] = Counter()
    best: dict[str, Any] | None = None
    candidate_count = 0
    valid_count = 0
    pruned_candidate_count = 0
    duplicate_candidate_count = 0
    early_rejection_count = 0
    seen_candidates: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()

    for count in SIDE_COUNTS:
        if count > len(candidate_side_ins) or count > len(candidate_side_outs):
            continue
        for side_in_names, side_out_names in candidate_pairs(candidate_side_ins, candidate_side_outs, count):
            if candidate_count >= max_candidates:
                break
            signature = (tuple(sorted(side_in_names)), tuple(sorted(side_out_names)))
            if signature in seen_candidates:
                duplicate_candidate_count += 1
                continue
            seen_candidates.add(signature)
            if low_value_candidate(side_in_names, candidate_side_ins, count):
                pruned_candidate_count += 1
                continue
            candidate_count += 1
            result = apply_side_plan(main_deck, side_deck, list(side_in_names), list(side_out_names))
            if not result["valid"]:
                early_rejection_count += 1
                for warning in result["warnings"] or ["invalid side plan"]:
                    rejection_reasons[warning] += 1
                continue
            valid_count += 1
            score = cached_candidate_score(result["post_side_main"], archetype, mode)
            candidate = {
                "post_side_main": result["post_side_main"],
                "side_in": result["applied_side_in"],
                "side_out": result["applied_side_out"],
                "score": score,
                "warnings": result["warnings"],
            }
            if best is None or candidate_score(candidate, game1_score) > candidate_score(best, game1_score):
                best = candidate
        if candidate_count >= max_candidates:
            break

    if best is None:
        fallback = first_pass_fallback(main_deck, side_deck, profile, going, card_pool)
        rejection_reasons.update(fallback.get("rejection_reasons", {}))
        return {
            "best_post_side_main": fallback["best_post_side_main"],
            "best_side_in": fallback["best_side_in"],
            "best_side_out": fallback["best_side_out"],
            "best_score": fallback["best_score"],
            "game1_score": round(float(game1_score), 2),
            "post_side_delta": round(float(fallback["best_score"]) - float(game1_score), 2),
            "candidate_count": candidate_count,
            "valid_candidate_count": valid_count,
            "rejected_candidate_count": max(0, candidate_count - valid_count),
            "pruned_candidate_count": pruned_candidate_count,
            "duplicate_candidate_count": duplicate_candidate_count,
            "early_rejection_count": early_rejection_count,
            "rejection_reasons": dict(rejection_reasons),
            "optimization_used": False,
            "post_side_memory_used": bool(memory),
            "curated_opponent_memory_used": bool(curated_memory),
            "warnings": fallback["warnings"] or ["no valid optimized side plan found"],
            "choke_report": choke_report,
            "choke_stop_rate": choke_report["average_stop_rate"],
            "opponent_recovery_rate": choke_report["average_recovery_rate"],
            "choke_coverage_score": choke_report["choke_coverage_score"],
            "best_interruption_overlap": choke_report["best_interruption_overlap"],
            "poor_interruption_count": choke_report["poor_interruption_count"],
            "timing_precision_score": choke_report["timing_precision_score"],
            "pivot_risk_score": choke_report["pivot_risk_score"],
            "best_timing_window_count": choke_report["best_timing_window_count"],
            "late_interruption_risk": choke_report["late_interruption_risk"],
            "early_interruption_risk": choke_report["early_interruption_risk"],
            "backup_line_success_rate": choke_report["backup_line_success_rate"],
            "graph_stop_rate": choke_report["graph_stop_rate"],
            "graph_pivot_rate": choke_report["graph_pivot_rate"],
            "graph_endboard_reduction_score": choke_report["graph_endboard_reduction_score"],
            "graph_best_interruption_count": choke_report["graph_best_interruption_count"],
            "graph_poor_interruption_count": choke_report["graph_poor_interruption_count"],
            "graph_timing_precision_score": choke_report["graph_timing_precision_score"],
            "opponent_resource_valid_rate": choke_report["opponent_resource_valid_rate"],
            "opponent_resource_failure_rate": choke_report["opponent_resource_failure_rate"],
            "opponent_pivot_success_rate": choke_report["opponent_pivot_success_rate"],
            "opponent_backup_success_rate": choke_report["opponent_backup_success_rate"],
            "opponent_missing_card_failures": choke_report["opponent_missing_card_failures"],
            "opponent_missing_extra_failures": choke_report["opponent_missing_extra_failures"],
            "opponent_once_per_turn_failures": choke_report["opponent_once_per_turn_failures"],
            "opponent_normal_summon_failures": choke_report["opponent_normal_summon_failures"],
            "opponent_starter_open_rate": choke_report["opponent_starter_open_rate"],
            "opponent_extender_open_rate": choke_report["opponent_extender_open_rate"],
            "opponent_interruption_open_rate": choke_report["opponent_interruption_open_rate"],
            "opponent_brick_rate": choke_report["opponent_brick_rate"],
            "probability_weighted_resource_valid_rate": choke_report["probability_weighted_resource_valid_rate"],
            "probability_weighted_stop_rate": choke_report["probability_weighted_stop_rate"],
            "probability_weighted_pivot_rate": choke_report["probability_weighted_pivot_rate"],
            "probability_weighted_backup_rate": choke_report["probability_weighted_backup_rate"],
        }

    return {
        "best_post_side_main": best["post_side_main"],
        "best_side_in": best["side_in"],
        "best_side_out": best["side_out"],
        "best_score": round(float(best["score"]), 2),
        "game1_score": round(float(game1_score), 2),
        "post_side_delta": round(float(best["score"]) - float(game1_score), 2),
        "candidate_count": candidate_count,
        "valid_candidate_count": valid_count,
        "rejected_candidate_count": max(0, candidate_count - valid_count),
        "pruned_candidate_count": pruned_candidate_count,
        "duplicate_candidate_count": duplicate_candidate_count,
        "early_rejection_count": early_rejection_count,
        "rejection_reasons": dict(rejection_reasons.most_common(10)),
        "optimization_used": True,
        "post_side_memory_used": bool(memory),
        "curated_opponent_memory_used": bool(curated_memory),
        "warnings": best["warnings"],
        "choke_report": choke_report,
        "choke_stop_rate": choke_report["average_stop_rate"],
        "opponent_recovery_rate": choke_report["average_recovery_rate"],
        "choke_coverage_score": choke_report["choke_coverage_score"],
        "best_interruption_overlap": choke_report["best_interruption_overlap"],
        "poor_interruption_count": choke_report["poor_interruption_count"],
        "timing_precision_score": choke_report["timing_precision_score"],
        "pivot_risk_score": choke_report["pivot_risk_score"],
        "best_timing_window_count": choke_report["best_timing_window_count"],
        "late_interruption_risk": choke_report["late_interruption_risk"],
        "early_interruption_risk": choke_report["early_interruption_risk"],
        "backup_line_success_rate": choke_report["backup_line_success_rate"],
        "graph_stop_rate": choke_report["graph_stop_rate"],
        "graph_pivot_rate": choke_report["graph_pivot_rate"],
        "graph_endboard_reduction_score": choke_report["graph_endboard_reduction_score"],
        "graph_best_interruption_count": choke_report["graph_best_interruption_count"],
        "graph_poor_interruption_count": choke_report["graph_poor_interruption_count"],
        "graph_timing_precision_score": choke_report["graph_timing_precision_score"],
        "opponent_resource_valid_rate": choke_report["opponent_resource_valid_rate"],
        "opponent_resource_failure_rate": choke_report["opponent_resource_failure_rate"],
        "opponent_pivot_success_rate": choke_report["opponent_pivot_success_rate"],
        "opponent_backup_success_rate": choke_report["opponent_backup_success_rate"],
        "opponent_missing_card_failures": choke_report["opponent_missing_card_failures"],
        "opponent_missing_extra_failures": choke_report["opponent_missing_extra_failures"],
        "opponent_once_per_turn_failures": choke_report["opponent_once_per_turn_failures"],
        "opponent_normal_summon_failures": choke_report["opponent_normal_summon_failures"],
        "opponent_starter_open_rate": choke_report["opponent_starter_open_rate"],
        "opponent_extender_open_rate": choke_report["opponent_extender_open_rate"],
        "opponent_interruption_open_rate": choke_report["opponent_interruption_open_rate"],
        "opponent_brick_rate": choke_report["opponent_brick_rate"],
        "probability_weighted_resource_valid_rate": choke_report["probability_weighted_resource_valid_rate"],
        "probability_weighted_stop_rate": choke_report["probability_weighted_stop_rate"],
        "probability_weighted_pivot_rate": choke_report["probability_weighted_pivot_rate"],
        "probability_weighted_backup_rate": choke_report["probability_weighted_backup_rate"],
    }


def side_in_pool(
    side_deck: list[dict[str, Any]],
    profile: MatchupProfile,
    going: str,
    memory: dict[str, Any] | None = None,
    curated_memory: dict[str, Any] | None = None,
    choke_report: dict[str, Any] | None = None,
) -> list[str]:
    ranked = []
    for card in side_deck:
        if get_card_limit(card) <= 0:
            continue
        name = str(card.get("name", ""))
        ranked.append(
            (
                side_in_score(card, profile, going)
                + memory_card_adjustment(memory or {}, name, "side_in", card)
                + curated_memory_card_adjustment(curated_memory or {}, name, "side_in", card)
                + choke_side_in_adjustment(name, choke_report or {}),
                name,
            )
        )
    ranked.sort(reverse=True)
    return [name for _score, name in ranked]


def side_out_priority(
    main_deck: list[dict[str, Any]],
    profile: MatchupProfile,
    going: str,
    memory: dict[str, Any] | None = None,
    curated_memory: dict[str, Any] | None = None,
) -> list[str]:
    ranked = []
    seen = set()
    for card in main_deck:
        name = str(card.get("name", ""))
        if name in seen:
            continue
        seen.add(name)
        ranked.append(
            (
                side_out_score(card, profile, going)
                + memory_card_adjustment(memory or {}, name, "side_out", card)
                + curated_memory_card_adjustment(curated_memory or {}, name, "side_out", card),
                name,
            )
        )
    ranked.sort(reverse=True)
    return [name for _score, name in ranked]


def candidate_pairs(side_ins: list[str], side_outs: list[str], count: int) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    pairs: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    top_in = side_ins[: max(count + 4, count)]
    top_out = side_outs[: max(count + 4, count)]
    pairs.append((tuple(top_in[:count]), tuple(top_out[:count])))
    for offset in range(1, min(5, len(top_in) - count + 1, len(top_out) - count + 1)):
        pairs.append((tuple(top_in[offset : offset + count]), tuple(top_out[:count])))
        pairs.append((tuple(top_in[:count]), tuple(top_out[offset : offset + count])))
    for side_in_combo in combinations(top_in[: min(len(top_in), count + 3)], count):
        if len(pairs) >= 20:
            break
        pairs.append((tuple(side_in_combo), tuple(top_out[:count])))
    return pairs


def low_value_candidate(side_in_names: tuple[str, ...], ranked_side_ins: list[str], count: int) -> bool:
    if count <= 3:
        return False
    preferred = set(ranked_side_ins[: max(count + 3, count)])
    return sum(1 for name in side_in_names if name in preferred) < max(1, count - 2)


def side_in_score(card: dict[str, Any], profile: MatchupProfile, going: str) -> float:
    name = str(card.get("name", ""))
    text = f"{name} {card.get('type', '')} {card.get('desc', '')}".casefold()
    score = 0.0
    if any(term.casefold() in name.casefold() for term in profile.high_value_side_cards):
        score += 12.0
    if profile.monster_effect_density >= 0.7 and any(term in text for term in ("ash blossom", "droll", "nibiru", "effect veiler", "infinite impermanence")):
        score += 5.0
    if profile.backrow_density >= 0.6 and any(term in text for term in ("spell/trap", "harpie", "lightning storm", "cosmic cyclone", "evenly matched")):
        score += 5.0
    if profile.graveyard_dependency >= 0.6 and any(term in text for term in ("graveyard", "gy", "banish", "bystial", "d.d. crow")):
        score += 5.0
    if going == "first" and any(term in text for term in ("solemn", "trap", "negate")):
        score += 3.0
    if going == "second" and any(term in text for term in ("destroy", "banish", "dark ruler", "evenly", "raigeki", "book of eclipse")):
        score += 3.0
    return score


def choke_side_in_adjustment(card_name: str, choke_report: dict[str, Any]) -> float:
    name = card_name.casefold()
    if any(str(card).casefold() in name or name in str(card).casefold() for card in choke_report.get("recommended_interruptions", [])):
        return 4.0
    if any(str(card).casefold() in name or name in str(card).casefold() for card in choke_report.get("poor_interruptions", [])):
        return -3.0
    return 0.0


def side_out_score(card: dict[str, Any], profile: MatchupProfile, going: str) -> float:
    name = str(card.get("name", ""))
    text = f"{name} {card.get('type', '')} {card.get('desc', '')}".casefold()
    score = 0.0
    if any(term.casefold() in text for term in profile.low_value_cards):
        score += 8.0
    if "normal monster" in text or ("level" in text and "8" in text and "special summon" not in text):
        score += 4.0
    if going == "first" and any(term in text for term in ("dark ruler", "raigeki", "lightning storm", "evenly matched")):
        score += 5.0
    if going == "second" and "trap" in text and not any(term in text for term in ("infinite impermanence", "evenly matched")):
        score += 5.0
    if not card_role_flags(card):
        score += 2.0
    if is_core_card(name):
        score -= 6.0
    if any(term in text for term in ("sage with eyes", "white stone", "bingo machine", "dictator of d")):
        score -= 8.0
    return score


def is_core_card(name: str) -> bool:
    lowered = name.casefold()
    return any(term in lowered for term in CORE_TERMS)


def candidate_score(candidate: dict[str, Any], game1_score: float) -> float:
    return float(candidate["score"]) + max(-10.0, min(10.0, float(candidate["score"]) - float(game1_score))) * 0.5


def first_pass_fallback(
    main_deck: list[dict[str, Any]],
    side_deck: list[dict[str, Any]],
    profile: MatchupProfile,
    going: str,
    card_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    count = min(5, len(side_deck), len(main_deck))
    application = apply_side_plan(
        main_deck,
        side_deck,
        [card for card in side_deck[:count]],
        side_out_priority(main_deck, profile, going)[:count],
    )
    score = cached_candidate_score(application["post_side_main"], "", "meta")
    return {
        "best_post_side_main": application["post_side_main"],
        "best_side_in": application["applied_side_in"],
        "best_side_out": application["applied_side_out"],
        "best_score": round(float(score), 2),
        "warnings": application["warnings"],
        "rejection_reasons": Counter(application["warnings"]),
    }


def cached_candidate_score(deck: list[dict[str, Any]], archetype: str, mode: str) -> float:
    key = (tuple(str(card.get("name", "")) for card in deck), archetype, mode)
    if key in SIDE_CANDIDATE_SCORE_CACHE:
        SIDE_CANDIDATE_SCORE_STATS["hits"] += 1
        SIDE_CANDIDATE_SCORE_CACHE.move_to_end(key)
        return SIDE_CANDIDATE_SCORE_CACHE[key]
    SIDE_CANDIDATE_SCORE_STATS["misses"] += 1
    score = float(score_deck_breakdown(deck, archetype, mode).get("final_score", 0.0))
    SIDE_CANDIDATE_SCORE_CACHE[key] = score
    SIDE_CANDIDATE_SCORE_CACHE.move_to_end(key)
    while len(SIDE_CANDIDATE_SCORE_CACHE) > SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES:
        SIDE_CANDIDATE_SCORE_CACHE.popitem(last=False)
    return score


def side_candidate_cache_stats() -> dict[str, int]:
    return dict(SIDE_CANDIDATE_SCORE_STATS)
