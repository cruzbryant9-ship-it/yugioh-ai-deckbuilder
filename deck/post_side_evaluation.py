from __future__ import annotations

from typing import Any

from deck.builder import score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.hand_simulator import real_combo_report
from deck.package_builder import summarize_package_metrics
from deck.package_quality import score_package_quality
from deck.side_deck_planner import build_side_deck
from deck.side_plan_optimizer import optimize_side_plan
from SystemAIYugioh.metric_registry import GRAPH_METRICS, MONTE_CARLO_PROBABILITY_METRICS, OPPONENT_METRICS, RESOURCE_METRICS
from SystemAIYugioh.opponent_metric_builder import build_opponent_metric_bundle
from SystemAIYugioh.score_snapshot import DEFAULT_SCORE_CACHE


def evaluate_post_side_plan(
    deck: list[dict[str, Any]],
    card_pool: list[dict[str, Any]],
    archetype: str,
    mode: str,
    matchup: str | Any,
    going: str,
    max_candidates: int = 12,
    use_memory: bool = True,
) -> dict[str, Any]:
    main_deck, extra_deck = split_deck(deck)
    side_report = build_side_deck(deck, archetype, matchup, card_pool, going=going)
    optimized = optimize_side_plan(
        main_deck,
        side_report["side_deck"],
        matchup,
        going,
        card_pool,
        max_candidates=max_candidates,
        archetype=archetype,
        mode=mode,
        use_memory=use_memory,
    )
    post_side_deck = list(optimized["best_post_side_main"]) + list(extra_deck)
    game1 = score_full_deck(deck, archetype, mode)
    post_side = score_full_deck(post_side_deck, archetype, mode)
    blocked = blocked_card_violations(post_side_deck)
    size_valid = len(optimized["best_post_side_main"]) == len(main_deck)
    valid = bool(optimized["valid_candidate_count"] > 0 and not blocked and size_valid)
    warnings = list(optimized["warnings"])
    if blocked:
        warnings.append(f"blocked cards after siding: {', '.join(sorted(set(blocked)))}")
    if not size_valid:
        warnings.append("post-side main deck size is invalid")
    signal_keys = (*OPPONENT_METRICS, *GRAPH_METRICS, *RESOURCE_METRICS, *MONTE_CARLO_PROBABILITY_METRICS)
    metric_bundle = build_opponent_metric_bundle(
        optimized,
        side_report,
        matchup=matchup,
        curated=str(getattr(matchup, "name", matchup)).endswith(" curated profile"),
        simulated=True,
        keys=signal_keys,
    )
    return {
        "game1_score": game1["final_score"],
        "post_side_score": post_side["final_score"],
        "post_side_delta": round(post_side["final_score"] - game1["final_score"], 2),
        "post_side_valid": valid,
        "side_cards_used": optimized["best_side_in"],
        "cards_sided_out": optimized["best_side_out"],
        "post_side_warnings": sorted(set(warnings)),
        "candidate_count": optimized["candidate_count"],
        "valid_candidate_count": optimized["valid_candidate_count"],
        "rejected_candidate_count": optimized["rejected_candidate_count"],
        "pruned_candidate_count": optimized.get("pruned_candidate_count", 0),
        "duplicate_candidate_count": optimized.get("duplicate_candidate_count", 0),
        "early_rejection_count": optimized.get("early_rejection_count", 0),
        "valid_candidate_rate": round(optimized["valid_candidate_count"] / max(optimized["candidate_count"], 1), 4),
        "rejection_reasons": optimized["rejection_reasons"],
        "optimization_used": optimized["optimization_used"],
        "post_side_memory_used": optimized.get("post_side_memory_used", False),
        "curated_opponent_memory_used": optimized.get("curated_opponent_memory_used", False),
        **metric_bundle,
        "best_post_side_score": post_side["final_score"],
        "best_side_in": optimized["best_side_in"],
        "best_side_out": optimized["best_side_out"],
        "side_deck_score": side_report["side_deck_score"],
        "matchup_coverage_score": side_report["matchup_coverage_score"],
        "choke_report": optimized.get("choke_report", side_report.get("choke_report", {})),
        "game1_metrics": game1,
        "post_side_metrics": post_side,
        "post_side_main": [card["name"] for card in optimized["best_post_side_main"]],
        "recommended_side_deck": [card["name"] for card in side_report["side_deck"]],
        "blocked_card_violations_after_siding": sorted(set(blocked)),
        "post_side_deck_size_valid": size_valid,
    }


def score_full_deck(deck: list[dict[str, Any]], archetype: str, mode: str) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        breakdown = score_deck_breakdown(deck, archetype, mode)
        gameplay = real_combo_report(deck, archetype, samples=30)
        package_report = summarize_package_metrics(deck)
        package_quality = score_package_quality(deck, package_report, breakdown)
        return {
            "final_score": breakdown["final_score"],
            "playable_hand_rate": gameplay.get("playable_hand_rate", 0),
            "brick_rate": gameplay.get("brick_rate", 0),
            "resilience_score": gameplay.get("resilience_score", 0),
            "ash_vulnerability_rate": gameplay.get("ash_vulnerability_rate", 0),
            "imperm_vulnerability_rate": gameplay.get("imperm_vulnerability_rate", 0),
            "veiler_vulnerability_rate": gameplay.get("veiler_vulnerability_rate", 0),
            "droll_vulnerability_rate": gameplay.get("droll_vulnerability_rate", 0),
            "crow_vulnerability_rate": gameplay.get("crow_vulnerability_rate", 0),
            "nibiru_vulnerability_rate": gameplay.get("nibiru_vulnerability_rate", 0),
            "package_quality_score": package_quality["final_package_quality_score"],
        }

    return DEFAULT_SCORE_CACHE.cached_full_score(deck, archetype, mode, load)
