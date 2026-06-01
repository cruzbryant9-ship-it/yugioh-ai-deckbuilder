from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.builder import build_deck, score_deck_breakdown
from deck.curated_opponent_memory import (
    curated_memory_summary,
    curated_opponent_name,
    load_curated_opponent_memory,
    update_curated_opponent_memory,
)
from deck.opponent_analyzer import analyze_opponent_deck
from deck.opponent_probability_simulator import simulate_opponent_openings
from deck.deck_utils import split_deck
from deck.side_deck_planner import build_side_deck
from deck.side_plan_optimizer import optimize_side_plan
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.opponent_metric_builder import build_opponent_metric_bundle, display_opponent_metric
from SystemAIYugioh.report_schema import normalize_report
from SystemAIYugioh.regression_gates import evaluate_curated_opponent_memory_update
from SystemAIYugioh.runtime_context import DEFAULT_RUNTIME_CONTEXT, RuntimeContext

REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "opponent_profiles"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze an opponent decklist and produce matchup-specific side recommendations.")
    parser.add_argument("--decklist", required=True)
    parser.add_argument("--archetype", required=True)
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--going", choices=("first", "second", "both"), default="both")
    return parser.parse_args()


def run_analysis(decklist_path: str, archetype: str, mode: str, going: str, runtime_context: RuntimeContext | None = None) -> dict[str, Any]:
    runtime_context = runtime_context or DEFAULT_RUNTIME_CONTEXT
    startup_safety_cleanup()
    cards = runtime_context.cards(refresh=True)
    parsed = runtime_context.parsed_decklist(decklist_path)
    opponent = analyze_opponent_deck(parsed, cards)
    probability = simulate_opponent_openings(parsed, opponent, runs=1000)
    deck, _pool = build_deck(cards, archetype, mode=mode, matchup=opponent, going=going)
    main_deck, extra_deck = split_deck(deck)
    side_report = build_side_deck(deck, archetype, opponent, cards, going=going, probability_estimates=probability)
    optimized = optimize_side_plan(main_deck, side_report["side_deck"], opponent, going, cards, archetype=archetype, mode=mode, probability_estimates=probability)
    no_memory_optimized = optimize_side_plan(
        main_deck,
        side_report["side_deck"],
        opponent,
        going,
        cards,
        archetype=archetype,
        mode=mode,
        use_memory=False,
        probability_estimates=probability,
    )
    game1_score = score_deck_breakdown(deck, archetype, mode)["final_score"]
    post_side_deck = list(optimized["best_post_side_main"]) + list(extra_deck)
    post_side_score = score_deck_breakdown(post_side_deck, archetype, mode)["final_score"]
    no_memory_delta = round(float(no_memory_optimized.get("best_score", game1_score)) - float(game1_score), 2)
    opponent_metrics = build_opponent_metric_bundle(
        optimized,
        side_report,
        matchup=opponent,
        curated=bool(curated_opponent_name(opponent)),
        simulated=True,
    )
    run_result = {
        "post_side_valid": optimized["valid_candidate_count"] > 0,
        "post_side_delta": round(post_side_score - game1_score, 2),
        "post_side_score": post_side_score,
        "side_cards_used": optimized["best_side_in"],
        "cards_sided_out": optimized["best_side_out"],
        "engine_variant": optimized.get("engine_variant") or "unknown",
        "matchup_coverage_score": side_report.get("matchup_coverage_score", 0),
        "blocked_card_violations_after_siding": [],
    }
    memory_gate = evaluate_curated_opponent_memory_update(run_result, {"post_side_delta": no_memory_delta})
    updated_memory = {}
    if curated_opponent_name(opponent) and memory_gate["accepted"]:
        updated_memory = update_curated_opponent_memory(archetype, mode, opponent, going, [run_result])
    current_memory = updated_memory or load_curated_opponent_memory(archetype, mode, opponent, going)
    return {
        "config": {"decklist": decklist_path, "archetype": archetype, "mode": mode, "going": going},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "opponent_profile": profile_to_dict(opponent),
        "parsed_counts": {key: len(parsed.get(key, [])) for key in ("main", "extra", "side", "all_cards")},
        "opponent_probability": probability,
        "game1_score": game1_score,
        "post_side_score": post_side_score,
        "post_side_delta": round(post_side_score - game1_score, 2),
        "no_memory_post_side_delta": no_memory_delta,
        "memory_aided_delta": round(round(post_side_score - game1_score, 2) - no_memory_delta, 2),
        "side_deck": [card["name"] for card in side_report["side_deck"]],
        "choke_report": optimized.get("choke_report", side_report.get("choke_report", {})),
        **opponent_metrics,
        "side_in": optimized["best_side_in"],
        "side_out": optimized["best_side_out"],
        "candidate_count": optimized["candidate_count"],
        "valid_candidate_count": optimized["valid_candidate_count"],
        "valid_candidate_rate": round(optimized["valid_candidate_count"] / max(optimized["candidate_count"], 1), 4),
        "optimization_used": optimized["optimization_used"],
        "curated_opponent_memory_used": optimized.get("curated_opponent_memory_used", False),
        "curated_opponent_memory_updated": bool(updated_memory),
        "curated_opponent_memory_gate": memory_gate,
        "curated_opponent_memory_summary": curated_memory_summary(current_memory) if current_memory else {},
    }


def profile_to_dict(profile: Any) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in profile.__dict__.items()
    }


def save_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    opponent = str(report["opponent_profile"]["archetype"]).lower().replace(" ", "_")
    path = REPORT_DIR / f"{timestamp}_{opponent}_opponent_profile.json"
    atomic_write_json(path, normalize_report("opponent_analysis", report))
    return path


def main() -> None:
    args = parse_args()
    report = run_analysis(args.decklist, args.archetype, args.mode, args.going)
    path = save_report(report)
    profile = report["opponent_profile"]
    print("\nOpponent Deck Analysis")
    print(f"Opponent archetype: {profile['archetype']}")
    print(f"Profile source: {profile.get('profile_source', 'inferred')}")
    print(f"Matched curated profile: {profile.get('matched_curated_profile') or 'none'}")
    print(f"Nearest matchup: {profile['nearest_matchup']}")
    print(f"Likely engines: {profile['likely_engines']}")
    print(f"Expected threats: {profile['expected_endboard']}")
    print(f"Choke points: {profile['choke_points']}")
    print(f"Best counters: {profile.get('best_counters', [])}")
    print(f"Weak counters: {profile.get('weak_counters', [])}")
    if profile.get("curated_notes"):
        print(f"Curated notes: {profile['curated_notes']}")
    choke = report.get("choke_report", {})
    print(f"Opponent likely lines: {choke.get('likely_lines', [])}")
    print(f"Likely opponent branches: {[result.get('branch_points', []) for result in choke.get('line_branch_results', [])]}")
    print(f"Best choke points: {[result.get('choke_points', []) for result in choke.get('choke_results', [])]}")
    print(f"Best interruptions: {choke.get('best_interruptions', [])}")
    print(f"Best timing windows: {choke.get('best_timing_windows', [])}")
    print(f"Opponent graph route: {choke.get('graph_route', [])}")
    print(f"Best interruption nodes: {choke.get('best_interruption_nodes', [])}")
    print(f"Poor interruption nodes: {choke.get('poor_interruption_nodes', [])}")
    print(f"Bad timing windows: {choke.get('bad_timing_windows', [])}")
    print(f"Poor interruptions: {choke.get('poor_interruptions', [])}")
    print(f"Cards that are good but timing-sensitive: {choke.get('recommended_interruptions', [])}")
    print(f"Cards that are poor because they hit too late: {choke.get('poor_interruptions', [])}")
    print(f"Choke stop rate: {display_opponent_metric(report.get('choke_stop_rate'))}")
    print(f"Opponent recovery rate: {display_opponent_metric(report.get('opponent_recovery_rate'))}")
    print(f"Timing precision score: {report.get('timing_precision_score', 0)}")
    print(f"Pivot risk score: {report.get('pivot_risk_score', 0)}")
    print(f"Backup line success rate: {display_opponent_metric(report.get('backup_line_success_rate'))}")
    print(f"Graph stop rate: {display_opponent_metric(report.get('graph_stop_rate'))}")
    print(f"Graph pivot rate: {display_opponent_metric(report.get('graph_pivot_rate'))}")
    print(f"Graph endboard reduction score: {display_opponent_metric(report.get('graph_endboard_reduction_score'))}")
    print(f"Opponent resource valid rate: {display_opponent_metric(report.get('opponent_resource_valid_rate'))}")
    print(f"Opponent resource failure rate: {display_opponent_metric(report.get('opponent_resource_failure_rate'))}")
    print(f"Opponent pivot success rate: {display_opponent_metric(report.get('opponent_pivot_success_rate'))}")
    print(f"Opponent backup success rate: {display_opponent_metric(report.get('opponent_backup_success_rate'))}")
    print(f"Opponent missing card failures: {report.get('opponent_missing_card_failures', {})}")
    print(f"Opponent missing Extra Deck failures: {report.get('opponent_missing_extra_failures', {})}")
    print(f"Opponent starter open rate: {display_opponent_metric(report.get('opponent_starter_open_rate'))}")
    print(f"Opponent extender open rate: {display_opponent_metric(report.get('opponent_extender_open_rate'))}")
    print(f"Opponent interruption open rate: {display_opponent_metric(report.get('opponent_interruption_open_rate'))}")
    print(f"Opponent brick rate: {display_opponent_metric(report.get('opponent_brick_rate'))}")
    print(f"Probability-weighted stop rate: {display_opponent_metric(report.get('probability_weighted_stop_rate'))}")
    print(f"Probability-weighted pivot rate: {display_opponent_metric(report.get('probability_weighted_pivot_rate'))}")
    print(f"Probability-weighted backup rate: {display_opponent_metric(report.get('probability_weighted_backup_rate'))}")
    if choke.get("route_results"):
        best = choke["route_results"][0].get("best_interruption")
        print(f"Expected outcome if interrupted: {best.get('outcome_if_interrupted') if isinstance(best, dict) else 'unknown'}")
        print(f"Expected outcome if not interrupted: {best.get('outcome_if_not_interrupted') if isinstance(best, dict) else 'unknown'}")
    print(f"Recommended side-in: {report['side_in']}")
    reasons = report.get("side_deck", [])
    if reasons:
        print(f"Why side cards matter: {choke.get('recommended_interruptions', [])}")
    print(f"Recommended side-out: {report['side_out']}")
    print(f"Post-side score estimate: {report['post_side_score']}")
    print(f"Post-side delta estimate: {report['post_side_delta']}")
    print(f"Curated opponent memory used: {report.get('curated_opponent_memory_used')}")
    print(f"Curated opponent memory updated: {report.get('curated_opponent_memory_updated')}")
    print(f"Memory-aided delta: {report.get('memory_aided_delta')}")
    memory = report.get("curated_opponent_memory_summary", {})
    if memory:
        print(f"Best remembered side-ins: {memory.get('top_side_ins', [])[:5]}")
        print(f"Best remembered side-outs: {memory.get('top_side_outs', [])[:5]}")
        print(f"Best remembered engine: {memory.get('best_engine')}")
    print(f"Saved report: {path}")


if __name__ == "__main__":
    main()
