from __future__ import annotations

import argparse
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.builder import score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.engine_variants import ENGINE_VARIANTS
from deck.hand_simulator import real_combo_report
from deck.matchup_engine_stats import load_matchup_engine_stats, save_matchup_engine_stats
from deck.matchup_profiles import get_matchup_profile, list_matchup_names
from deck.decklist_parser import parse_decklist_file
from deck.curated_opponent_library import curated_to_opponent_profile, load_curated_profiles
from deck.curated_opponent_memory import (
    curated_memory_summary,
    load_curated_opponent_memory,
    update_curated_opponent_memory,
)
from deck.opponent_analyzer import analyze_opponent_deck
from deck.opponent_profiles import OpponentProfile
from deck.package_builder import build_package_deck
from deck.package_quality import score_package_quality
from deck.post_side_memory import load_post_side_memory, memory_summary
from deck.side_deck_planner import build_side_deck
from deck.post_side_evaluation import evaluate_post_side_plan
from deck.choke_simulator import choke_cache_stats
from deck.side_plan_optimizer import side_candidate_cache_stats
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.matrix_cache import DEFAULT_MATRIX_CACHE, MatrixCache
from SystemAIYugioh.memory_context import provenance_metadata
from SystemAIYugioh.opponent_metric_builder import (
    aggregate_opponent_count_reports,
    build_opponent_metric_bundle,
    opponent_gate_normalization_metadata,
    normalize_opponent_metrics_for_gates,
    summarize_opponent_metrics,
)
from SystemAIYugioh.report_schema import normalize_json_shape, normalize_report
from SystemAIYugioh.regression_gates import evaluate_matchup_matrix_update
from SystemAIYugioh.runtime_context import DEFAULT_RUNTIME_CONTEXT, RuntimeContext
from SystemAIYugioh.score_snapshot import DEFAULT_SCORE_CACHE
from SystemAIYugioh.source_fingerprint import source_fingerprint
from config.settings import MATRIX_FULL_RUNS_PER_CELL, MATRIX_SMOKE_RUNS_PER_CELL
from config.settings import MATRIX_FULL_SIDE_CANDIDATES, MATRIX_MAX_FAILURE_RATE, MATRIX_SMOKE_ENGINE_LIMIT, MATRIX_SMOKE_MATCHUP_LIMIT, MATRIX_SMOKE_SIDE_CANDIDATES

MATRIX_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "matchup_matrix"
GOING_OPTIONS = ("first", "second", "both")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run engine x matchup x going matrix testing.")
    parser.add_argument("--archetype", required=True, help='Archetype to test, for example "Blue-Eyes".')
    parser.add_argument("--mode", choices=("meta", "innovation"), default="meta")
    parser.add_argument("--runs-per-cell", type=int, default=MATRIX_FULL_RUNS_PER_CELL)
    parser.add_argument("--opponent-profiles-folder", default=None)
    parser.add_argument("--use-curated-opponents", action="store_true")
    parser.add_argument("--no-cache", action="store_true", help="Run without reading or writing the persistent matrix cache.")
    parser.add_argument("--no-memory-write", action="store_true", help="Skip persistent matrix and curated-memory writes for infrastructure checks.")
    parser.add_argument("--seed", type=int, default=None, help="Seed Python randomness for reproducible infrastructure checks.")
    parser.add_argument("--smoke", action="store_true", help="Use the smallest matrix settings for quick validation.")
    parser.add_argument("--full", action="store_true", help="Use full matrix settings unless --runs-per-cell is explicitly smaller.")
    return parser.parse_args()


def run_matrix(
    archetype: str,
    mode: str,
    runs_per_cell: int,
    opponent_profiles_folder: str | None = None,
    use_curated_opponents: bool = False,
    runtime_context: RuntimeContext | None = None,
    matrix_cache: MatrixCache | None = None,
    seed: int | None = None,
    update_memory: bool = True,
) -> dict[str, Any]:
    runtime_context = runtime_context or DEFAULT_RUNTIME_CONTEXT
    matrix_cache = matrix_cache or DEFAULT_MATRIX_CACHE
    if seed is not None:
        random.seed(seed)
    startup_safety_cleanup()
    cards = runtime_context.cards(refresh=True)
    if use_curated_opponents:
        matchup_targets = [curated_to_opponent_profile(profile) for profile in runtime_context.curated_profiles()]
    elif opponent_profiles_folder:
        matchup_targets = load_opponent_profile_targets(opponent_profiles_folder, cards)
    else:
        matchup_targets = list(list_matchup_names())
    engine_variants = list(ENGINE_VARIANTS)
    smoke_mode = runs_per_cell <= MATRIX_SMOKE_RUNS_PER_CELL
    provenance = provenance_metadata(source="matrix", smoke=smoke_mode, legal=True)
    if smoke_mode:
        if MATRIX_SMOKE_ENGINE_LIMIT:
            engine_variants = engine_variants[:MATRIX_SMOKE_ENGINE_LIMIT]
        if MATRIX_SMOKE_MATCHUP_LIMIT:
            matchup_targets = matchup_targets[:MATRIX_SMOKE_MATCHUP_LIMIT]
    cells = []
    for variant in engine_variants:
        for matchup in matchup_targets:
            for going in GOING_OPTIONS:
                cells.append(run_cell(cards, archetype, mode, variant, matchup, going, runs_per_cell, use_curated_opponents, matrix_cache, seed))
    rankings = rank_matrix(cells)
    summary = matrix_summary(cells)
    report = {
        "config": {
            "archetype": archetype,
            "mode": mode,
            "runs_per_cell": runs_per_cell,
            "engine_variants": list(engine_variants),
            "matchup_profiles": [matchup_label(matchup) for matchup in matchup_targets],
            "opponent_profiles_folder": opponent_profiles_folder,
            "use_curated_opponents": use_curated_opponents,
            "going": list(GOING_OPTIONS),
            "smoke_mode": smoke_mode,
            "seed": seed,
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cache_fingerprint": matrix_cache.fingerprint.get("fingerprint"),
        "source_fingerprint": matrix_cache.fingerprint.get("source_fingerprint") or source_fingerprint(),
        "summary": summary,
        "rankings": rankings,
        "cells": cells,
        "runtime_stats": {
            "runtime_context": dict(runtime_context.stats),
            "matrix_cache": dict(matrix_cache.stats),
            "score_cache": dict(DEFAULT_SCORE_CACHE.stats),
            "side_candidate_score_cache": side_candidate_cache_stats(),
            "choke_cache": choke_cache_stats(),
        },
    }
    previous = load_matchup_engine_stats(archetype, mode)
    gate_metadata = opponent_gate_normalization_metadata(summary)
    gate = evaluate_matchup_matrix_update(normalize_opponent_metrics_for_gates(summary), previous)
    gate.update(gate_metadata)
    report["regression_gate"] = gate
    memory_safety = validate_matrix_memory_safety(report)
    report["memory_safety"] = memory_safety
    if update_memory and gate["accepted"] and memory_safety["safe"]:
        save_matchup_engine_stats(archetype, mode, build_matchup_engine_profile(report), provenance=provenance)
        report["matchup_engine_stats_updated"] = True
        report["curated_opponent_memory_updated"] = update_curated_memory_from_matrix(archetype, mode, report, provenance) if use_curated_opponents else False
    else:
        report["matchup_engine_stats_updated"] = False
        report["curated_opponent_memory_updated"] = False
        if not update_memory:
            report["memory_update_skipped"] = True
        if gate["accepted"] and not memory_safety["safe"]:
            report["memory_update_blocked"] = True
    return report


def run_cell(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    variant: str,
    matchup: str | OpponentProfile,
    going: str,
    runs: int,
    use_curated_opponents: bool = False,
    matrix_cache: MatrixCache | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    matrix_cache = matrix_cache or DEFAULT_MATRIX_CACHE
    results = []
    profile = matchup
    matchup_name = matchup_label(matchup)
    cache_key = matrix_cache.key(
        archetype=archetype,
        mode=mode,
        variant=variant,
        matchup=matchup_name,
        going=going,
        runs=runs,
        smoke=runs <= MATRIX_SMOKE_RUNS_PER_CELL,
        curated=use_curated_opponents,
        opponent_signal_sentinel_version=1,
        source_fingerprint=(matrix_cache.fingerprint.get("source_fingerprint") or {}).get("fingerprint"),
        seed=seed,
        side_candidates=MATRIX_SMOKE_SIDE_CANDIDATES if runs <= MATRIX_SMOKE_RUNS_PER_CELL else MATRIX_FULL_SIDE_CANDIDATES,
    )
    cached = matrix_cache.get(cache_key)
    if cached is not None:
        cached["cache_hit"] = True
        return cached
    started = time.perf_counter()
    for run_number in range(1, runs + 1):
        try:
            deck, package_report = build_package_deck(cards, archetype, mode=mode, engine_variant=variant)
            main_deck, extra_deck = split_deck(deck)
            breakdown = score_deck_breakdown(deck, archetype, mode)
            gameplay = real_combo_report(deck, archetype, samples=30)
            package_quality = score_package_quality(deck, package_report, breakdown)
            side_report = build_side_deck(deck, archetype, profile, cards, going=going)
            max_candidates = MATRIX_SMOKE_SIDE_CANDIDATES if runs <= MATRIX_SMOKE_RUNS_PER_CELL else MATRIX_FULL_SIDE_CANDIDATES
            post_side_report = evaluate_post_side_plan(deck, cards, archetype, mode, matchup, going, max_candidates=max_candidates)
            remembered = memory_summary(load_post_side_memory(archetype, mode, matchup_name, going))
            blocked = blocked_card_violations(deck) + blocked_card_violations(side_report["side_deck"])
            opponent_metrics = build_opponent_metric_bundle(post_side_report, side_report, matchup=matchup, curated=use_curated_opponents, simulated=True)
            results.append(
                {
                    "run": run_number,
                    "ok": True,
                    "engine_variant": variant,
                    "final_score": breakdown["final_score"],
                    "package_quality": package_quality["final_package_quality_score"],
                    "playable_hand_rate": gameplay.get("playable_hand_rate", 0),
                    "brick_rate": gameplay.get("brick_rate", 0),
                    "resilience_score": gameplay.get("resilience_score", 0),
                    "side_deck_score": side_report["side_deck_score"],
                    "game1_score": post_side_report["game1_score"],
                    "post_side_score": post_side_report["post_side_score"],
                    "post_side_delta": post_side_report["post_side_delta"],
                    "post_side_valid": post_side_report["post_side_valid"],
                    "valid_candidate_rate": post_side_report.get("valid_candidate_rate", 0),
                    "optimization_used": post_side_report.get("optimization_used", False),
                    "post_side_memory_used": post_side_report.get("post_side_memory_used", False),
                    "remembered_side_cards": remembered.get("top_side_in_cards", []),
                    "remembered_side_out_cards": remembered.get("top_side_out_cards", []),
                    "memory_aided_post_side_delta": post_side_report.get("post_side_delta", 0) if post_side_report.get("post_side_memory_used") else 0,
                    "matchup_coverage_score": side_report["matchup_coverage_score"],
                    **opponent_metrics,
                    "going_first_side_score": side_report["going_first_side_score"],
                    "going_second_side_score": side_report["going_second_side_score"],
                    "blocked_card_violations": sorted(set(blocked)),
                    "main_deck": [card["name"] for card in main_deck],
                    "extra_deck": [card["name"] for card in extra_deck],
                    "recommended_side_deck": [card["name"] for card in side_report["side_deck"]],
                    "side_cards_used": post_side_report["side_cards_used"],
                    "cards_sided_out": post_side_report["cards_sided_out"],
                }
            )
        except Exception as exc:
            results.append({"run": run_number, "ok": False, "error": str(exc)})
    cell = normalize_json_shape(summarize_cell(variant, matchup_name, going, results))
    cell["cache_hit"] = False
    cell["cache_generation_time"] = round(time.perf_counter() - started, 4)
    cell["cache_created_timestamp"] = datetime.now(timezone.utc).isoformat()
    cell["cache_fingerprint"] = matrix_cache.fingerprint.get("fingerprint")
    cell["source_fingerprint"] = matrix_cache.fingerprint.get("source_fingerprint") or source_fingerprint()
    matrix_cache.set(cache_key, cell)
    return cell


def summarize_cell(variant: str, matchup: str, going: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if result.get("ok")]
    failed = [result for result in results if not result.get("ok")]
    if not successful:
        return {
            "engine_variant": variant,
            "matchup": matchup,
            "going": going,
            "successful_runs": 0,
            "failed_runs": len(failed),
            "failed_cell": True,
            "failure_rate": 1.0,
            "average_final_score": 0,
            "best_score": 0,
            "blocked_card_violations": [],
            "runs": results,
        }
    best = max(successful, key=lambda result: result["final_score"])
    blocked = sorted({card for result in successful for card in result.get("blocked_card_violations", [])})
    side_cards = Counter(card for result in successful for card in result.get("recommended_side_deck", []))
    opponent_summary = summarize_opponent_metrics(successful, prefix="", include_counts=True)

    return {
        "engine_variant": variant,
        "matchup": matchup,
        "going": going,
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "failed_cell": False,
        "failure_rate": round(len(failed) / max(len(results), 1), 4),
        "average_final_score": round(mean(result["final_score"] for result in successful), 2),
        "best_score": round(max(result["final_score"] for result in successful), 2),
        "package_quality": round(mean(result["package_quality"] for result in successful), 2),
        "playable_hand_rate": round(mean(result["playable_hand_rate"] for result in successful), 4),
        "brick_rate": round(mean(result["brick_rate"] for result in successful), 4),
        "resilience_score": round(mean(result["resilience_score"] for result in successful), 2),
        "side_deck_score": round(mean(result["side_deck_score"] for result in successful), 2),
        "game1_score": round(mean(result["game1_score"] for result in successful), 2),
        "post_side_score": round(mean(result["post_side_score"] for result in successful), 2),
        "post_side_delta": round(mean(result["post_side_delta"] for result in successful), 2),
        "post_side_valid_rate": round(mean(1.0 if result.get("post_side_valid") else 0.0 for result in successful), 4),
        "valid_candidate_rate": round(mean(result.get("valid_candidate_rate", 0) for result in successful), 4),
        "side_optimization_success_rate": round(mean(1.0 if result.get("optimization_used") else 0.0 for result in successful), 4),
        "post_side_memory_used_rate": round(mean(1.0 if result.get("post_side_memory_used") else 0.0 for result in successful), 4),
        "memory_aided_post_side_delta": round(mean(result.get("memory_aided_post_side_delta", 0) for result in successful), 2),
        "matchup_coverage_score": round(mean(result["matchup_coverage_score"] for result in successful), 2),
        "choke_stop_rate": opponent_summary["choke_stop_rate"],
        "opponent_recovery_rate": opponent_summary["opponent_recovery_rate"],
        "choke_coverage_score": round(mean(result.get("choke_coverage_score", 0) for result in successful), 2),
        "best_interruption_overlap": round(mean(result.get("best_interruption_overlap", 0) for result in successful), 2),
        "poor_interruption_count": round(mean(result.get("poor_interruption_count", 0) for result in successful), 2),
        "timing_precision_score": round(mean(result.get("timing_precision_score", 0) for result in successful), 4),
        "pivot_risk_score": round(mean(result.get("pivot_risk_score", 0) for result in successful), 4),
        "best_timing_window_count": round(mean(result.get("best_timing_window_count", 0) for result in successful), 2),
        "late_interruption_risk": round(mean(result.get("late_interruption_risk", 0) for result in successful), 4),
        "early_interruption_risk": round(mean(result.get("early_interruption_risk", 0) for result in successful), 4),
        "backup_line_success_rate": round(mean(result.get("backup_line_success_rate", 0) for result in successful), 4),
        "graph_stop_rate": opponent_summary["graph_stop_rate"],
        "graph_pivot_rate": opponent_summary["graph_pivot_rate"],
        "graph_endboard_reduction_score": round(mean(result.get("graph_endboard_reduction_score", 0) for result in successful), 4),
        "graph_best_interruption_count": round(mean(result.get("graph_best_interruption_count", 0) for result in successful), 2),
        "graph_poor_interruption_count": round(mean(result.get("graph_poor_interruption_count", 0) for result in successful), 2),
        "graph_timing_precision_score": round(mean(result.get("graph_timing_precision_score", 0) for result in successful), 4),
        "opponent_resource_valid_rate": opponent_summary["opponent_resource_valid_rate"],
        "opponent_resource_failure_rate": opponent_summary["opponent_resource_failure_rate"],
        "opponent_pivot_success_rate": round(mean(result.get("opponent_pivot_success_rate", 0) for result in successful), 4),
        "opponent_backup_success_rate": round(mean(result.get("opponent_backup_success_rate", 0) for result in successful), 4),
        "opponent_starter_open_rate": opponent_summary["opponent_starter_open_rate"],
        "opponent_extender_open_rate": opponent_summary["opponent_extender_open_rate"],
        "opponent_interruption_open_rate": opponent_summary["opponent_interruption_open_rate"],
        "opponent_brick_rate": opponent_summary["opponent_brick_rate"],
        "probability_weighted_resource_valid_rate": opponent_summary["probability_weighted_resource_valid_rate"],
        "probability_weighted_stop_rate": opponent_summary["probability_weighted_stop_rate"],
        "probability_weighted_pivot_rate": opponent_summary["probability_weighted_pivot_rate"],
        "probability_weighted_backup_rate": opponent_summary["probability_weighted_backup_rate"],
        "opponent_signal_sentinel_counts": opponent_summary["opponent_signal_sentinel_counts"],
        "opponent_signal_provenance_counts": opponent_summary["opponent_signal_provenance_counts"],
        "going_first_side_score": round(mean(result["going_first_side_score"] for result in successful), 2),
        "going_second_side_score": round(mean(result["going_second_side_score"] for result in successful), 2),
        "blocked_card_violations": blocked,
        "best_deck": {"main_deck": best["main_deck"], "extra_deck": best["extra_deck"]},
        "recommended_side_deck": side_cards.most_common(15),
        "best_remembered_side_cards": successful[0].get("remembered_side_cards", []),
        "best_remembered_side_out_cards": successful[0].get("remembered_side_out_cards", []),
        "runs": results,
    }


def matchup_label(matchup: str | OpponentProfile) -> str:
    return matchup.name if isinstance(matchup, OpponentProfile) else str(matchup)


def load_opponent_profile_targets(folder: str | None, cards: list[dict[str, Any]]) -> list[OpponentProfile]:
    if not folder:
        return []
    root = Path(folder)
    profiles = []
    for path in sorted(root.glob("*.txt")):
        try:
            profiles.append(analyze_opponent_deck(parse_decklist_file(path), cards))
        except Exception:
            continue
    return profiles or []


def matrix_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [cell for cell in cells if cell.get("successful_runs", 0)]
    failed_cells = [cell for cell in cells if cell.get("failed_cell") or not cell.get("successful_runs", 0)]
    total_runs = sum(int(cell.get("successful_runs", 0) or 0) + int(cell.get("failed_runs", 0) or 0) for cell in cells)
    failed_runs = sum(int(cell.get("failed_runs", 0) or 0) for cell in cells)
    scores = [float(cell.get("average_final_score", 0) or 0) for cell in successful]
    opponent_summary = summarize_opponent_metrics(successful, prefix="average_", include_counts=False) if successful else {}
    opponent_counts = aggregate_opponent_count_reports(successful)

    return {
        "cell_count": len(cells),
        "successful_cells": len(successful),
        "failed_cells": len(failed_cells),
        "failed_cell_count": len(failed_cells),
        "failed_run_count": failed_runs,
        "total_run_count": total_runs,
        "failure_rate": round(failed_runs / max(total_runs, 1), 4),
        "average_score": round(mean(scores), 2) if scores else 0,
        "score_stddev": round(pstdev(scores), 2) if len(scores) > 1 else 0,
        "average_side_deck_score": round(mean(float(cell.get("side_deck_score", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_post_side_score": round(mean(float(cell.get("post_side_score", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_post_side_delta": round(mean(float(cell.get("post_side_delta", 0) or 0) for cell in successful), 2) if successful else 0,
        "post_side_valid_rate": round(mean(float(cell.get("post_side_valid_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_valid_candidate_rate": round(mean(float(cell.get("valid_candidate_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "side_optimization_success_rate": round(mean(float(cell.get("side_optimization_success_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "post_side_memory_used_rate": round(mean(float(cell.get("post_side_memory_used_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_memory_aided_post_side_delta": round(mean(float(cell.get("memory_aided_post_side_delta", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_matchup_coverage_score": round(mean(float(cell.get("matchup_coverage_score", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_resilience_score": round(mean(float(cell.get("resilience_score", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_choke_stop_rate": opponent_summary.get("average_choke_stop_rate", 0),
        "average_opponent_recovery_rate": opponent_summary.get("average_opponent_recovery_rate", 0),
        "average_choke_coverage_score": round(mean(float(cell.get("choke_coverage_score", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_poor_interruption_count": round(mean(float(cell.get("poor_interruption_count", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_timing_precision_score": round(mean(float(cell.get("timing_precision_score", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_pivot_risk_score": round(mean(float(cell.get("pivot_risk_score", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_backup_line_success_rate": round(mean(float(cell.get("backup_line_success_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_graph_stop_rate": opponent_summary.get("average_graph_stop_rate", 0),
        "average_graph_pivot_rate": opponent_summary.get("average_graph_pivot_rate", 0),
        "average_graph_endboard_reduction_score": round(mean(float(cell.get("graph_endboard_reduction_score", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_graph_poor_interruption_count": round(mean(float(cell.get("graph_poor_interruption_count", 0) or 0) for cell in successful), 2) if successful else 0,
        "average_graph_timing_precision_score": round(mean(float(cell.get("graph_timing_precision_score", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_opponent_resource_valid_rate": opponent_summary.get("average_opponent_resource_valid_rate", 0),
        "average_opponent_resource_failure_rate": opponent_summary.get("average_opponent_resource_failure_rate", 0),
        "average_opponent_pivot_success_rate": round(mean(float(cell.get("opponent_pivot_success_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_opponent_backup_success_rate": round(mean(float(cell.get("opponent_backup_success_rate", 0) or 0) for cell in successful), 4) if successful else 0,
        "average_opponent_starter_open_rate": opponent_summary.get("average_opponent_starter_open_rate", 0),
        "average_opponent_extender_open_rate": opponent_summary.get("average_opponent_extender_open_rate", 0),
        "average_opponent_interruption_open_rate": opponent_summary.get("average_opponent_interruption_open_rate", 0),
        "average_opponent_brick_rate": opponent_summary.get("average_opponent_brick_rate", 0),
        "average_probability_weighted_stop_rate": opponent_summary.get("average_probability_weighted_stop_rate", 0),
        "average_probability_weighted_pivot_rate": opponent_summary.get("average_probability_weighted_pivot_rate", 0),
        "average_probability_weighted_backup_rate": opponent_summary.get("average_probability_weighted_backup_rate", 0),
        **opponent_counts,
        "blocked_card_violation_count": sum(len(cell.get("blocked_card_violations", [])) for cell in successful),
    }


def rank_matrix(cells: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [cell for cell in cells if cell.get("successful_runs", 0)]
    if not successful:
        return {}
    engine_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matchup_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in successful:
        engine_groups[cell["engine_variant"]].append(cell)
        matchup_groups[cell["matchup"]].append(cell)

    engine_scores = {engine: mean(composite_score(cell) for cell in group) for engine, group in engine_groups.items()}
    engine_bricks = {engine: mean(float(cell.get("brick_rate", 0) or 0) for cell in group) for engine, group in engine_groups.items()}
    engine_side = {engine: mean(float(cell.get("side_deck_score", 0) or 0) for cell in group) for engine, group in engine_groups.items()}
    engine_resilience = {engine: mean(float(cell.get("resilience_score", 0) or 0) for cell in group) for engine, group in engine_groups.items()}
    engine_post_side = {engine: mean(float(cell.get("post_side_score", 0) or 0) for cell in group) for engine, group in engine_groups.items()}
    engine_valid_candidate = {engine: mean(float(cell.get("valid_candidate_rate", 0) or 0) for cell in group) for engine, group in engine_groups.items()}
    engine_delta = {engine: mean(float(cell.get("post_side_delta", 0) or 0) for cell in group) for engine, group in engine_groups.items()}

    best_by_matchup = {}
    for matchup, group in matchup_groups.items():
        by_engine: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cell in group:
            by_engine[cell["engine_variant"]].append(cell)
        best_by_matchup[matchup] = max(
            by_engine,
            key=lambda engine: mean(composite_score(cell) for cell in by_engine[engine]),
        )

    first_cells = [cell for cell in successful if cell["going"] == "first"]
    second_cells = [cell for cell in successful if cell["going"] == "second"]
    worst = min(successful, key=composite_score)
    return {
        "best_overall_engine": max(engine_scores, key=engine_scores.get),
        "best_engine_by_matchup": best_by_matchup,
        "best_going_first_engine": best_engine_for_cells(first_cells),
        "best_going_second_engine": best_engine_for_cells(second_cells),
        "safest_low_brick_engine": min(engine_bricks, key=engine_bricks.get),
        "best_side_deck_compatible_engine": max(engine_side, key=engine_side.get),
        "most_resilient_engine": max(engine_resilience, key=engine_resilience.get),
        "best_post_side_engine": max(engine_post_side, key=engine_post_side.get),
        "best_side_plan_engine": max(engine_valid_candidate, key=engine_valid_candidate.get),
        "highest_valid_candidate_rate_engine": max(engine_valid_candidate, key=engine_valid_candidate.get),
        "best_game1_to_post_side_improvement_engine": max(engine_delta, key=engine_delta.get),
        "worst_engine_matchup_pairing": {
            "engine_variant": worst["engine_variant"],
            "matchup": worst["matchup"],
            "going": worst["going"],
            "score": worst["average_final_score"],
        },
    }


def best_engine_for_cells(cells: list[dict[str, Any]]) -> str:
    if not cells:
        return "none"
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        groups[cell["engine_variant"]].append(cell)
    return max(groups, key=lambda engine: mean(composite_score(cell) for cell in groups[engine]))


def composite_score(cell: dict[str, Any]) -> float:
    return (
        float(cell.get("average_final_score", 0) or 0)
        + float(cell.get("package_quality", 0) or 0) * 0.2
        + float(cell.get("resilience_score", 0) or 0) * 1.5
        + float(cell.get("side_deck_score", 0) or 0) * 0.1
        + float(cell.get("post_side_score", 0) or 0) * 0.35
        + float(cell.get("post_side_delta", 0) or 0) * 0.2
        - float(cell.get("brick_rate", 0) or 0) * 20
    )


def build_matchup_engine_profile(report: dict[str, Any]) -> dict[str, Any]:
    cells = [cell for cell in report["cells"] if cell.get("successful_runs", 0)]
    by_matchup: dict[str, dict[str, str]] = defaultdict(dict)
    performance: dict[str, dict[str, Any]] = defaultdict(dict)
    avoid: dict[str, str] = {}
    for matchup in sorted({cell["matchup"] for cell in cells}):
        matchup_cells = [cell for cell in cells if cell["matchup"] == matchup]
        if not matchup_cells:
            continue
        for going in GOING_OPTIONS:
            going_cells = [cell for cell in matchup_cells if cell["going"] == going]
            if going_cells:
                by_matchup[matchup][going] = best_engine_for_cells(going_cells)
        worst = min(matchup_cells, key=composite_score)
        avoid[matchup] = worst["engine_variant"]
        performance[matchup] = {
            cell["engine_variant"]: {
                "going": cell["going"],
                "average_score": cell["average_final_score"],
                "side_deck_score": cell.get("side_deck_score", 0),
                "post_side_score": cell.get("post_side_score", 0),
                "post_side_delta": cell.get("post_side_delta", 0),
                "valid_candidate_rate": cell.get("valid_candidate_rate", 0),
                "memory_aided_post_side_delta": cell.get("memory_aided_post_side_delta", 0),
                "resilience_score": cell.get("resilience_score", 0),
                "brick_rate": cell.get("brick_rate", 0),
            }
            for cell in matchup_cells
        }
    return {
        "archetype": report["config"]["archetype"],
        "mode": report["config"]["mode"],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": report["summary"],
        "rankings": report["rankings"],
        "engine_performance_by_matchup": performance,
        "recommended_engine_by_matchup": dict(by_matchup),
        "matchup_specific_avoid_engines": avoid,
    }


def update_curated_memory_from_matrix(archetype: str, mode: str, report: dict[str, Any], provenance: dict[str, Any] | None = None) -> bool:
    memory_safety = report.get("memory_safety", {})
    if memory_safety and not memory_safety.get("safe", False):
        report["curated_opponent_memory_summary"] = {}
        return False
    updated = False
    for cell in report.get("cells", []):
        matchup = str(cell.get("matchup", ""))
        if not matchup.endswith(" curated profile"):
            continue
        runs = [run for run in cell.get("runs", []) if run.get("ok")]
        if not runs:
            continue
        update_curated_opponent_memory(archetype, mode, matchup, str(cell.get("going", "both")), runs, provenance=provenance)
        updated = True
    report["curated_opponent_memory_summary"] = curated_matrix_memory_summary(archetype, mode, report)
    return updated


def curated_matrix_memory_summary(archetype: str, mode: str, report: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for matchup in report.get("config", {}).get("matchup_profiles", []):
        matchup_name = str(matchup)
        if not matchup_name.endswith(" curated profile"):
            continue
        summary[matchup_name] = {
            going: curated_memory_summary(load_curated_opponent_memory(archetype, mode, matchup_name, going))
            for going in GOING_OPTIONS
        }
    return summary


def validate_matrix_memory_safety(report: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    checked_cells = 0
    for cell in report.get("cells", []):
        if not cell.get("successful_runs", 0):
            continue
        checked_cells += 1
        cell_label = f"{cell.get('engine_variant')} vs {cell.get('matchup')} going {cell.get('going')}"
        for blocked in cell.get("blocked_card_violations", []):
            issues.append(f"{cell_label}: blocked violation already reported: {blocked}")
        for location, names in matrix_cell_card_groups(cell).items():
            violations = blocked_name_violations(names)
            if violations:
                issues.append(f"{cell_label}: blocked cards in {location}: {', '.join(sorted(violations))}")
        side_count = len(extract_side_deck_names(cell.get("recommended_side_deck", [])))
        if side_count > 15:
            issues.append(f"{cell_label}: side deck recommendation exceeds 15 cards ({side_count})")
        for run in cell.get("runs", []):
            if not run.get("ok"):
                continue
            run_violations = blocked_name_violations(
                list(run.get("main_deck", []))
                + list(run.get("extra_deck", []))
                + list(run.get("recommended_side_deck", []))
                + list(run.get("side_cards_used", []))
            )
            if run_violations:
                issues.append(f"{cell_label}: blocked cards in run {run.get('run')}: {', '.join(sorted(run_violations))}")
    return {
        "safe": not issues,
        "checked_cells": checked_cells,
        "issue_count": len(issues),
        "issues": issues[:25],
    }


def matrix_cell_card_groups(cell: dict[str, Any]) -> dict[str, list[str]]:
    best_deck = cell.get("best_deck", {}) if isinstance(cell.get("best_deck"), dict) else {}
    return {
        "main_deck": [str(name) for name in best_deck.get("main_deck", [])],
        "extra_deck": [str(name) for name in best_deck.get("extra_deck", [])],
        "recommended_side_deck": extract_side_deck_names(cell.get("recommended_side_deck", [])),
    }


def extract_side_deck_names(cards: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(cards, list):
        return names
    for item in cards:
        if isinstance(item, (list, tuple)) and item:
            names.append(str(item[0]))
        elif isinstance(item, dict):
            names.append(str(item.get("name", "")))
        else:
            names.append(str(item))
    return [name for name in names if name]


def blocked_name_violations(names: list[str]) -> list[str]:
    return [name for name in names if get_card_limit({"name": name}) <= 0]


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archetype = report["config"]["archetype"].lower().replace(" ", "_")
    mode = report["config"]["mode"]
    json_path = MATRIX_DIR / f"{timestamp}_{archetype}_{mode}_matchup_matrix.json"
    markdown_path = MATRIX_DIR / "latest_matchup_matrix_report.md"
    normalized = normalize_report("matchup_matrix", report)
    atomic_write_json(json_path, normalized)
    atomic_write_text(markdown_path, render_markdown(normalized, json_path))
    return json_path, markdown_path


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    rankings = report.get("rankings", {})
    lines = [
        "# Matchup Matrix Report",
        "",
        f"- Archetype: {report['config']['archetype']}",
        f"- Mode: {report['config']['mode']}",
        f"- Runs per cell: {report['config']['runs_per_cell']}",
        f"- JSON report: `{json_path}`",
        f"- Matchup engine stats updated: {report.get('matchup_engine_stats_updated')}",
        f"- Curated opponent memory updated: {report.get('curated_opponent_memory_updated', False)}",
        f"- Memory safety: {report.get('memory_safety', {}).get('safe', False)}",
        "",
        "## Rankings",
        "",
        f"- Best overall engine: {rankings.get('best_overall_engine', 'none')}",
        f"- Best going-first engine: {rankings.get('best_going_first_engine', 'none')}",
        f"- Best going-second engine: {rankings.get('best_going_second_engine', 'none')}",
        f"- Safest low-brick engine: {rankings.get('safest_low_brick_engine', 'none')}",
        f"- Best side-deck-compatible engine: {rankings.get('best_side_deck_compatible_engine', 'none')}",
        f"- Most resilient engine: {rankings.get('most_resilient_engine', 'none')}",
        f"- Best post-side engine: {rankings.get('best_post_side_engine', 'none')}",
        f"- Best side-plan engine: {rankings.get('best_side_plan_engine', 'none')}",
        f"- Highest valid candidate rate engine: {rankings.get('highest_valid_candidate_rate_engine', 'none')}",
        f"- Best Game 1 to post-side improvement engine: {rankings.get('best_game1_to_post_side_improvement_engine', 'none')}",
        "",
        "## Best Engine By Matchup",
        "",
    ]
    for matchup, engine in sorted(rankings.get("best_engine_by_matchup", {}).items()):
        lines.append(f"- {matchup}: {engine}")
    worst = rankings.get("worst_engine_matchup_pairing", {})
    lines.extend(
        [
            "",
            "## Worst Pairing",
            "",
            f"- Engine: {worst.get('engine_variant', 'none')}",
            f"- Matchup: {worst.get('matchup', 'none')}",
            f"- Going: {worst.get('going', 'none')}",
            f"- Score: {worst.get('score', 0)}",
            "",
            "## Top Cells",
            "",
        ]
    )
    top_cells = sorted((cell for cell in report["cells"] if cell.get("successful_runs")), key=composite_score, reverse=True)[:15]
    for cell in top_cells:
        lines.append(
            f"- {cell['engine_variant']} vs {cell['matchup']} going {cell['going']}: "
            f"score {cell['average_final_score']}, post-side {cell.get('post_side_score', 0)}, delta {cell.get('post_side_delta', 0)}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    if args.smoke:
        args.runs_per_cell = MATRIX_SMOKE_RUNS_PER_CELL
    elif args.full and args.runs_per_cell < MATRIX_FULL_RUNS_PER_CELL:
        args.runs_per_cell = MATRIX_FULL_RUNS_PER_CELL
    if args.runs_per_cell < 1:
        raise SystemExit("--runs-per-cell must be 1 or greater.")
    cache = MatrixCache(enabled=False) if args.no_cache else DEFAULT_MATRIX_CACHE
    report = run_matrix(
        args.archetype,
        args.mode,
        args.runs_per_cell,
        args.opponent_profiles_folder,
        args.use_curated_opponents,
        matrix_cache=cache,
        seed=args.seed,
        update_memory=not args.no_memory_write,
    )
    json_path, markdown_path = save_reports(report)
    print("\nMatchup Matrix Complete")
    print(f"Cells tested: {report['summary']['cell_count']}")
    print(f"Failed cells: {report['summary'].get('failed_cell_count', 0)}")
    print(f"Failure rate: {report['summary'].get('failure_rate', 0)}")
    print(f"Best overall engine: {report['rankings'].get('best_overall_engine', 'none')}")
    print(f"Matchup engine stats updated: {report.get('matchup_engine_stats_updated')}")
    print(f"Curated opponent memory updated: {report.get('curated_opponent_memory_updated', False)}")
    if args.use_curated_opponents:
        for matchup, engine in sorted(report["rankings"].get("best_engine_by_matchup", {}).items()):
            print(f"- {matchup}: best engine {engine}")
    if not report["regression_gate"]["accepted"]:
        print("Regression gate rejected matchup engine stats:")
        for reason in report["regression_gate"]["reasons"]:
            print(f"- {reason}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if float(report["summary"].get("failure_rate", 0) or 0) > MATRIX_MAX_FAILURE_RATE:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
