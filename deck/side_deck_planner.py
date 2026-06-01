from __future__ import annotations

from collections import Counter
from typing import Any

from SystemAIYugioh.banlist import get_card_limit
from deck.choke_simulator import simulate_choke_points
from deck.matchup_profiles import MatchupProfile, get_matchup_profile
from deck.opponent_profiles import OpponentProfile, opponent_to_matchup_profile
from deck.side_deck_scoring import score_side_deck


SIDE_TERMS = {
    "Ash Blossom": ("ash blossom",),
    "Droll & Lock Bird": ("droll",),
    "Nibiru": ("nibiru",),
    "Infinite Impermanence": ("infinite impermanence",),
    "Effect Veiler": ("effect veiler",),
    "D.D. Crow": ("d.d. crow", "dd crow"),
    "Ghost Belle": ("ghost belle",),
    "Called by the Grave": ("called by the grave",),
    "Harpie's Feather Duster": ("harpie's feather duster",),
    "Lightning Storm": ("lightning storm",),
    "Cosmic Cyclone": ("cosmic cyclone",),
    "Evenly Matched": ("evenly matched",),
    "Dark Ruler No More": ("dark ruler no more",),
    "Book of Eclipse": ("book of eclipse",),
    "Raigeki": ("raigeki",),
    "Solemn Judgment": ("solemn judgment",),
    "Skill Drain": ("skill drain",),
    "Bystial": ("bystial",),
}


def build_side_deck(
    deck: list[dict[str, Any]],
    archetype: str,
    matchup_profile: MatchupProfile | OpponentProfile | str | None,
    card_pool: list[dict[str, Any]],
    going: str = "both",
    probability_estimates: dict[str, float] | None = None,
) -> dict[str, Any]:
    profile = resolve_matchup_context(matchup_profile)
    choke_report = simulate_choke_points(matchup_profile, [str(card.get("name", "")) for card in card_pool], probability_estimates=probability_estimates)
    main_counts = Counter(str(card.get("name", "")) for card in deck)
    candidates = rank_side_candidates(card_pool, profile, going, choke_report)
    side_in_candidates = [card for card, _reason_tags, _score in candidates]
    side_deck: list[dict[str, Any]] = []
    total_counts = Counter(main_counts)
    reasons: dict[str, list[str]] = {}

    for card, reason_tags, _score in candidates:
        if len(side_deck) >= 15:
            break
        name = str(card.get("name", ""))
        limit = get_card_limit(card)
        if limit <= 0 or total_counts[name] >= limit:
            continue
        side_deck.append(card)
        total_counts[name] += 1
        reasons.setdefault(name, sorted(set(reason_tags)))

    side_out = cards_to_side_out(deck, profile)
    side_in = [card for card in side_deck[: len(side_out) or min(5, len(side_deck))]]
    priority_order = [str(card.get("name", "")) for card in side_deck]
    scoring = score_side_deck(side_deck, deck, profile, going)
    return {
        "side_deck": side_deck,
        "reasons": reasons,
        "matchup": profile.name,
        "going_first_plan": list(profile.going_first_priorities),
        "going_second_plan": list(profile.going_second_priorities),
        "side_in": side_in,
        "side_out": side_out,
        "priority_order": priority_order,
        "candidate_side_in_pool": side_in_candidates,
        "side_out_priority": side_out,
        "matchup_reason": list(profile.risk_factors),
        "going_reason": list(profile.going_first_priorities if going == "first" else profile.going_second_priorities if going == "second" else profile.going_first_priorities + profile.going_second_priorities),
        "cards_to_side_out": side_out,
        "scoring": scoring,
        "side_deck_score": scoring["side_deck_score"],
        "matchup_coverage_score": scoring["matchup_coverage_score"],
        "going_first_side_score": scoring["going_first_side_score"],
        "going_second_side_score": scoring["going_second_side_score"],
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


def rank_side_candidates(card_pool: list[dict[str, Any]], profile: MatchupProfile, going: str, choke_report: dict[str, Any] | None = None) -> list[tuple[dict[str, Any], list[str], float]]:
    ranked = []
    for card in card_pool:
        if get_card_limit(card) <= 0:
            continue
        score, reasons = side_candidate_score(card, profile, going, choke_report)
        if score > 0:
            ranked.append((card, reasons, score))
    ranked.sort(key=lambda item: (item[2], str(item[0].get("name", ""))), reverse=True)
    return ranked


def side_candidate_score(card: dict[str, Any], profile: MatchupProfile, going: str, choke_report: dict[str, Any] | None = None) -> tuple[float, list[str]]:
    name = str(card.get("name", ""))
    text = f"{name} {card.get('type', '')} {card.get('desc', '')}".casefold()
    score = 0.0
    reasons = []
    for high_value in profile.high_value_side_cards:
        if high_value.casefold() in name.casefold():
            score += 8.0
            reasons.append("profile_high_value")
    for label, terms in SIDE_TERMS.items():
        if any(term in text for term in terms):
            if label in profile.high_value_side_cards or any(label.casefold() in value.casefold() for value in profile.high_value_side_cards):
                score += 4.0
            reasons.append(label)
    if profile.graveyard_dependency >= 0.6 and any(term in text for term in ("graveyard", "gy", "banish", "bystial")):
        score += 4.0
        reasons.append("anti_graveyard")
    if profile.backrow_density >= 0.6 and any(term in text for term in ("spell/trap", "spell or trap", "harpie", "lightning storm", "cosmic cyclone")):
        score += 4.0
        reasons.append("anti_backrow")
    if profile.monster_effect_density >= 0.7 and any(
        term in text
        for term in (
            "ash blossom",
            "effect veiler",
            "infinite impermanence",
            "droll",
            "nibiru",
            "dark ruler no more",
            "book of eclipse",
            "evenly matched",
        )
    ):
        score += 4.0
        reasons.append("anti_combo")
    if going == "first" and any(term in text for term in ("solemn", "trap", "negate")):
        score += 2.0
        reasons.append("going_first")
    if going == "second" and any(term in text for term in ("destroy", "banish", "dark ruler", "evenly", "raigeki", "book of eclipse")):
        score += 2.0
        reasons.append("going_second")
    choke_score, choke_reasons = choke_candidate_adjustment(name, choke_report or {})
    score += choke_score
    reasons.extend(choke_reasons)
    return score, sorted(set(reasons))


def choke_candidate_adjustment(card_name: str, choke_report: dict[str, Any]) -> tuple[float, list[str]]:
    if not choke_report:
        return 0.0, []
    reasons = []
    score = 0.0
    best = [str(card).casefold() for card in choke_report.get("recommended_interruptions", [])]
    poor = [str(card).casefold() for card in choke_report.get("poor_interruptions", [])]
    name = card_name.casefold()
    if any(card in name or name in card for card in best):
        score += 6.0
        reasons.append("hits_modeled_choke_point")
        if choke_report.get("best_timing_windows"):
            reasons.append("timing_aware_choke")
        if choke_report.get("best_interruption_nodes"):
            reasons.append("graph_interruption_node")
        if choke_report.get("opponent_resource_failure_rate", 0) > 0:
            reasons.append("resource_aware_interruption")
    if any(card in name or name in card for card in poor):
        score -= 4.0
        reasons.append("poor_modeled_interruption")
    return score, reasons


def cards_to_side_out(deck: list[dict[str, Any]], profile: MatchupProfile) -> list[str]:
    low_terms = tuple(term.casefold() for term in profile.low_value_cards)
    suggestions = []
    for card in deck:
        name = str(card.get("name", ""))
        text = f"{name} {card.get('desc', '')}".casefold()
        if any(term in text for term in low_terms):
            suggestions.append(name)
        elif profile.backrow_density >= 0.7 and "battle" in text:
            suggestions.append(name)
        elif profile.graveyard_dependency <= 0.2 and ("d.d. crow" in name.casefold() or "ghost belle" in name.casefold()):
            suggestions.append(name)
    if not suggestions:
        for card in deck:
            name = str(card.get("name", ""))
            text = f"{name} {card.get('type', '')} {card.get('desc', '')}".casefold()
            if "normal monster" in text or "level" in text and "8" in text or "battle" in text:
                suggestions.append(name)
            if len(set(suggestions)) >= 5:
                break
    if not suggestions:
        suggestions = [str(card.get("name", "")) for card in deck[-5:]]
    return sorted(set(suggestions))[:15]


def resolve_matchup_context(matchup_profile: MatchupProfile | OpponentProfile | str | None) -> MatchupProfile:
    if isinstance(matchup_profile, MatchupProfile):
        return matchup_profile
    if isinstance(matchup_profile, OpponentProfile):
        return opponent_to_matchup_profile(matchup_profile)
    return get_matchup_profile(matchup_profile if isinstance(matchup_profile, str) else getattr(matchup_profile, "name", None))
