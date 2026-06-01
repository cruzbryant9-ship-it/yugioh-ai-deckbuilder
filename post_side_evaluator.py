from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.builder import build_deck
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.opponent_profiles import OpponentProfile
from deck.post_side_memory import memory_summary, update_post_side_memory
from deck.post_side_evaluation import evaluate_post_side_plan
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.opponent_metric_builder import display_opponent_metric, summarize_opponent_metrics
from SystemAIYugioh.report_schema import normalize_report
from SystemAIYugioh.runtime_context import DEFAULT_RUNTIME_CONTEXT, RuntimeContext

POST_SIDE_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "post_side"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Game 1 deck quality against recommended post-side deck quality.")
    parser.add_argument("--archetype", required=True)
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--matchup", choices=list_matchup_names(), default="unknown_meta")
    parser.add_argument("--going", choices=("first", "second", "both"), default="both")
    parser.add_argument("--runs", type=int, default=20)
    return parser.parse_args()


def run_post_side_evaluation(archetype: str, mode: str, matchup: str, going: str, runs: int, runtime_context: RuntimeContext | None = None) -> dict[str, Any]:
    runtime_context = runtime_context or DEFAULT_RUNTIME_CONTEXT
    startup_safety_cleanup()
    cards = runtime_context.cards(refresh=True)
    results = []
    for run_number in range(1, runs + 1):
        try:
            deck, _pool = build_deck(cards, archetype, mode=mode, matchup=matchup, going=going)
            result = evaluate_post_side_plan(deck, cards, archetype, mode, matchup, going)
            result["run"] = run_number
            result["ok"] = True
        except Exception as exc:
            result = {"run": run_number, "ok": False, "error": str(exc)}
        results.append(result)
    summary = summarize_results(results)
    updated_memory = {}
    if summary.get("successful_runs", 0) and summary.get("average_post_side_delta", 0) >= -8 and summary.get("average_valid_candidate_rate", 0) >= 0.2:
        updated_memory = update_post_side_memory(archetype, mode, matchup, going, [result for result in results if result.get("ok")])
    return {
        "config": {"archetype": archetype, "mode": mode, "matchup": matchup, "going": going, "runs": runs},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "post_side_memory_updated": bool(updated_memory),
        "post_side_memory_summary": memory_summary(updated_memory) if updated_memory else {},
        "runs": results,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if result.get("ok")]
    if not successful:
        return {"successful_runs": 0, "failed_runs": len(results)}
    side_counter = Counter(card for result in successful for card in result.get("side_cards_used", []))
    opponent_summary = summarize_opponent_metrics(successful)
    return {
        "successful_runs": len(successful),
        "failed_runs": len(results) - len(successful),
        "average_game1_score": round(mean(result["game1_score"] for result in successful), 2),
        "average_post_side_score": round(mean(result["post_side_score"] for result in successful), 2),
        "average_post_side_delta": round(mean(result["post_side_delta"] for result in successful), 2),
        "post_side_valid_rate": round(mean(1.0 if result.get("post_side_valid") else 0.0 for result in successful), 4),
        "average_side_deck_score": round(mean(result.get("side_deck_score", 0) for result in successful), 2),
        "average_matchup_coverage_score": round(mean(result.get("matchup_coverage_score", 0) for result in successful), 2),
        "average_candidate_count": round(mean(result.get("candidate_count", 0) for result in successful), 2),
        "average_valid_candidate_count": round(mean(result.get("valid_candidate_count", 0) for result in successful), 2),
        "average_pruned_candidate_count": round(mean(result.get("pruned_candidate_count", 0) for result in successful), 2),
        "average_duplicate_candidate_count": round(mean(result.get("duplicate_candidate_count", 0) for result in successful), 2),
        "average_early_rejection_count": round(mean(result.get("early_rejection_count", 0) for result in successful), 2),
        "average_valid_candidate_rate": round(mean(result.get("valid_candidate_rate", 0) for result in successful), 4),
        "optimization_success_rate": round(mean(1.0 if result.get("optimization_used") else 0.0 for result in successful), 4),
        "post_side_memory_used_rate": round(mean(1.0 if result.get("post_side_memory_used") else 0.0 for result in successful), 4),
        "average_choke_stop_rate": opponent_summary["average_choke_stop_rate"],
        "average_opponent_recovery_rate": opponent_summary["average_opponent_recovery_rate"],
        "average_choke_coverage_score": round(mean(result.get("choke_coverage_score", 0) for result in successful), 2),
        "average_best_interruption_overlap": round(mean(result.get("best_interruption_overlap", 0) for result in successful), 2),
        "average_poor_interruption_count": round(mean(result.get("poor_interruption_count", 0) for result in successful), 2),
        "average_timing_precision_score": round(mean(result.get("timing_precision_score", 0) for result in successful), 4),
        "average_pivot_risk_score": round(mean(result.get("pivot_risk_score", 0) for result in successful), 4),
        "average_best_timing_window_count": round(mean(result.get("best_timing_window_count", 0) for result in successful), 2),
        "average_late_interruption_risk": round(mean(result.get("late_interruption_risk", 0) for result in successful), 4),
        "average_early_interruption_risk": round(mean(result.get("early_interruption_risk", 0) for result in successful), 4),
        "average_backup_line_success_rate": round(mean(result.get("backup_line_success_rate", 0) for result in successful), 4),
        "average_graph_stop_rate": opponent_summary["average_graph_stop_rate"],
        "average_graph_pivot_rate": opponent_summary["average_graph_pivot_rate"],
        "average_graph_endboard_reduction_score": round(mean(result.get("graph_endboard_reduction_score", 0) for result in successful), 4),
        "average_graph_timing_precision_score": round(mean(result.get("graph_timing_precision_score", 0) for result in successful), 4),
        "average_graph_poor_interruption_count": round(mean(result.get("graph_poor_interruption_count", 0) for result in successful), 2),
        "average_opponent_resource_valid_rate": opponent_summary["average_opponent_resource_valid_rate"],
        "average_opponent_resource_failure_rate": opponent_summary["average_opponent_resource_failure_rate"],
        "average_opponent_pivot_success_rate": round(mean(result.get("opponent_pivot_success_rate", 0) for result in successful), 4),
        "average_opponent_backup_success_rate": round(mean(result.get("opponent_backup_success_rate", 0) for result in successful), 4),
        "average_opponent_starter_open_rate": opponent_summary["average_opponent_starter_open_rate"],
        "average_opponent_extender_open_rate": round(mean(result.get("opponent_extender_open_rate", 0) for result in successful), 4),
        "average_opponent_interruption_open_rate": round(mean(result.get("opponent_interruption_open_rate", 0) for result in successful), 4),
        "average_opponent_brick_rate": opponent_summary["average_opponent_brick_rate"],
        "average_probability_weighted_stop_rate": opponent_summary["average_probability_weighted_stop_rate"],
        "opponent_signal_sentinel_counts": opponent_summary["opponent_signal_sentinel_counts"],
        "opponent_signal_provenance_counts": opponent_summary["opponent_signal_provenance_counts"],
        "average_probability_weighted_pivot_rate": round(mean(result.get("probability_weighted_pivot_rate", 0) for result in successful), 4),
        "average_probability_weighted_backup_rate": round(mean(result.get("probability_weighted_backup_rate", 0) for result in successful), 4),
        "most_used_side_cards": side_counter.most_common(15),
    }


def save_report(report: dict[str, Any]) -> Path:
    POST_SIDE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype = report["config"]["archetype"].lower().replace(" ", "_")
    mode = report["config"]["mode"]
    matchup = report["config"]["matchup"]
    going = report["config"]["going"]
    path = POST_SIDE_DIR / f"{timestamp}_{archetype}_{mode}_{matchup}_{going}_post_side.json"
    atomic_write_json(path, normalize_report("post_side", report))
    return path


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")
    report = run_post_side_evaluation(args.archetype, args.mode, args.matchup, args.going, args.runs)
    path = save_report(report)
    summary = report["summary"]
    print("\nPost-Side Evaluation")
    print(f"Game 1 average score: {summary.get('average_game1_score', 0)}")
    print(f"Post-side average score: {summary.get('average_post_side_score', 0)}")
    print(f"Average post-side delta: {summary.get('average_post_side_delta', 0)}")
    print(f"Post-side valid rate: {summary.get('post_side_valid_rate', 0)}")
    print(f"Valid candidate rate: {summary.get('average_valid_candidate_rate', 0)}")
    print(f"Optimization success rate: {summary.get('optimization_success_rate', 0)}")
    print(f"Post-side memory used rate: {summary.get('post_side_memory_used_rate', 0)}")
    print(f"Choke stop rate: {display_opponent_metric(summary.get('average_choke_stop_rate'))}")
    print(f"Opponent recovery rate: {display_opponent_metric(summary.get('average_opponent_recovery_rate'))}")
    print(f"Timing precision score: {summary.get('average_timing_precision_score', 0)}")
    print(f"Pivot risk score: {summary.get('average_pivot_risk_score', 0)}")
    print(f"Graph stop rate: {display_opponent_metric(summary.get('average_graph_stop_rate'))}")
    print(f"Graph pivot rate: {display_opponent_metric(summary.get('average_graph_pivot_rate'))}")
    print(f"Opponent resource valid rate: {display_opponent_metric(summary.get('average_opponent_resource_valid_rate'))}")
    print(f"Opponent resource failure rate: {display_opponent_metric(summary.get('average_opponent_resource_failure_rate'))}")
    print(f"Opponent starter open rate: {display_opponent_metric(summary.get('average_opponent_starter_open_rate'))}")
    print(f"Opponent brick rate: {display_opponent_metric(summary.get('average_opponent_brick_rate'))}")
    print(f"Probability-weighted stop rate: {display_opponent_metric(summary.get('average_probability_weighted_stop_rate'))}")
    print(f"Post-side memory updated: {report.get('post_side_memory_updated')}")
    memory = report.get("post_side_memory_summary", {})
    if memory:
        print(f"Top side-in cards learned: {memory.get('top_side_in_cards', [])[:5]}")
        print(f"Top side-out cards learned: {memory.get('top_side_out_cards', [])[:5]}")
        print(f"Best post-side pattern: {memory.get('best_post_side_pattern')}")
    print(f"Saved report: {path}")


if __name__ == "__main__":
    main()
