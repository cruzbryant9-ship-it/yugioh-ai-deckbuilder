from __future__ import annotations

from collections import Counter, OrderedDict
from typing import Any

from deck.opponent_choke_model import OpponentLine, get_opponent_lines
from deck.opponent_profiles import OpponentProfile
from deck.opponent_branch_graph import get_opponent_graph
from deck.opponent_graph_simulator import simulate_opponent_graph
from deck.timing_windows import best_timing_for_interruption, get_timing_window, is_poor_timing

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
CHOKE_CACHE_MAX_ENTRIES = 2048
CHOKE_CACHE: OrderedDict[tuple[str, tuple[str, ...], tuple[tuple[str, float], ...]], dict[str, Any]] = OrderedDict()
CHOKE_CACHE_STATS = {"hits": 0, "misses": 0}


def simulate_choke_points(opponent_profile: str | OpponentProfile | None, available_interruptions: list[str], probability_estimates: dict[str, float] | None = None) -> dict[str, Any]:
    key = (
        opponent_label(opponent_profile),
        tuple(sorted(str(card) for card in available_interruptions)),
        tuple(sorted((str(k), float(v or 0)) for k, v in (probability_estimates or {}).items())),
    )
    if key in CHOKE_CACHE:
        CHOKE_CACHE_STATS["hits"] += 1
        CHOKE_CACHE.move_to_end(key)
        return dict(CHOKE_CACHE[key])
    CHOKE_CACHE_STATS["misses"] += 1
    graph = get_opponent_graph(opponent_profile)
    graph_report = simulate_opponent_graph(graph, available_interruptions, probability_estimates=probability_estimates) if graph else empty_graph_report()
    lines = get_opponent_lines(opponent_profile)
    normalized = [normalize_interruption(card) for card in available_interruptions]
    normalized = [card for card in normalized if card]
    if not lines:
        report = empty_report(opponent_label(opponent_profile), available_interruptions)
        report.update(graph_report)
        return report

    choke_results = []
    stop_rates = []
    recovery_rates = []
    interruption_scores: Counter[str] = Counter()
    timing_scores: Counter[str] = Counter()
    poor_counter: Counter[str] = Counter({card: 0 for card in normalized})
    bad_timing_counter: Counter[str] = Counter()
    timing_precision_scores = []
    pivot_risks = []
    backup_success_rates = []

    for line in lines:
        line_hits = []
        branch_hits = []
        best_stop = 0.0
        best_recovery = min(0.95, line.resilience_score / 10)
        best_timing = None
        poor_windows = []
        for interruption in normalized:
            result = evaluate_interruption(line, interruption)
            timed = evaluate_timing_window(line, interruption, result)
            if result["stop_rate"] > 0:
                result.update(timed)
                line_hits.append(result)
                branch_hits.append(timed)
                interruption_scores[interruption] += result["stop_rate"] * line.line_score
                if timed.get("best_timing_window"):
                    timing_scores[str(timed["best_timing_window"])] += result["stop_rate"] * line.line_score
                    best_timing = timed["best_timing_window"] if not best_timing else best_timing
                best_stop = max(best_stop, result["stop_rate"])
                best_recovery = min(best_recovery, result["recovery_rate"])
            else:
                poor_counter[interruption] += 1
            for window in timed.get("bad_timing_windows", []):
                bad_timing_counter[window] += 1
                poor_windows.append(window)
        status = "stopped" if best_stop >= 0.7 else "weakened" if best_stop >= 0.35 else "still_succeeds"
        pivot_risk = round(min(0.95, line.recovery_likelihood + (0.25 if status != "stopped" else 0.05)), 4)
        backup_success = round(min(0.95, line.recovery_likelihood * (1.0 - best_stop * 0.4)), 4)
        precision = round(best_stop * (1.0 - max(0.0, pivot_risk - 0.4) * 0.3), 4)
        choke_results.append(
            {
                "line_name": line.line_name,
                "branch_points": list(line.branch_points),
                "timing_windows": list(line.timing_windows),
                "choke_points": list(line.choke_points),
                "line_score": line.line_score,
                "status": status,
                "best_stop_rate": round(best_stop, 4),
                "recovery_rate": round(best_recovery, 4),
                "best_timing_window": best_timing,
                "bad_timing_windows": sorted(set(poor_windows)),
                "pivot_risk_score": pivot_risk,
                "backup_line_success_rate": backup_success,
                "endboard_if_uninterrupted": list(line.endboard_if_uninterrupted or line.endboard),
                "endboard_if_interrupted": list(line.endboard_if_interrupted),
                "hits": line_hits,
            }
        )
        stop_rates.append(best_stop)
        recovery_rates.append(best_recovery)
        timing_precision_scores.append(precision)
        pivot_risks.append(pivot_risk)
        backup_success_rates.append(backup_success)

    best_interruptions = [name for name, _score in interruption_scores.most_common()]
    best_timing_windows = [name for name, _score in timing_scores.most_common()]
    poor_interruptions = [name for name, misses in poor_counter.items() if misses >= len(lines) and name not in interruption_scores]
    report = {
        "opponent": opponent_label(opponent_profile),
        "available_interruptions": available_interruptions,
        "likely_lines": [line.line_name for line in lines],
        "best_interruptions": best_interruptions[:10],
        "best_timing_windows": best_timing_windows[:10],
        "bad_timing_windows": [name for name, _count in bad_timing_counter.most_common(10)],
        "line_branch_results": choke_results,
        "choke_results": choke_results,
        "average_stop_rate": round(sum(stop_rates) / max(len(stop_rates), 1), 4),
        "average_recovery_rate": round(sum(recovery_rates) / max(len(recovery_rates), 1), 4),
        "timing_precision_score": round(sum(timing_precision_scores) / max(len(timing_precision_scores), 1), 4),
        "pivot_risk_score": round(sum(pivot_risks) / max(len(pivot_risks), 1), 4),
        "backup_line_success_rate": round(sum(backup_success_rates) / max(len(backup_success_rates), 1), 4),
        "best_timing_window_count": len(best_timing_windows),
        "late_interruption_risk": late_interruption_risk(best_timing_windows),
        "early_interruption_risk": early_interruption_risk(best_timing_windows),
        "recommended_interruptions": best_interruptions[:6],
        "poor_interruptions": poor_interruptions[:10],
        "choke_coverage_score": round(sum(stop_rates) / max(len(stop_rates), 1) * 100, 2),
        "best_interruption_overlap": len(best_interruptions),
        "poor_interruption_count": len(poor_interruptions),
    }
    report.update(graph_report)
    if graph_report.get("best_interruptions"):
        report["best_interruptions"] = list(dict.fromkeys([*graph_report["best_interruptions"], *report["best_interruptions"]]))[:10]
        report["recommended_interruptions"] = report["best_interruptions"][:6]
    remember_choke_cache(key, dict(report))
    return report


def choke_cache_stats() -> dict[str, int]:
    return dict(CHOKE_CACHE_STATS)


def remember_choke_cache(key: tuple[str, tuple[str, ...], tuple[tuple[str, float], ...]], value: dict[str, Any]) -> None:
    CHOKE_CACHE[key] = value
    CHOKE_CACHE.move_to_end(key)
    while len(CHOKE_CACHE) > CHOKE_CACHE_MAX_ENTRIES:
        CHOKE_CACHE.popitem(last=False)


def evaluate_timing_window(line: OpponentLine, interruption: str, base_result: dict[str, Any]) -> dict[str, Any]:
    best_window = best_timing_for_interruption(interruption, line.timing_windows)
    bad_windows = [window for window in line.timing_windows if is_poor_timing(interruption, window)]
    if not best_window:
        return {
            "best_timing_window": None,
            "bad_timing_windows": bad_windows,
            "timing_precision": 0.0,
            "too_early": True,
            "too_late": True,
            "pivot_available": bool(line.recovery_routes),
        }
    window = get_timing_window(best_window)
    risk = window.risk_if_missed if window else 0.5
    precision = min(1.0, base_result.get("stop_rate", 0) * (1.0 + risk * 0.25))
    return {
        "best_timing_window": best_window,
        "bad_timing_windows": bad_windows,
        "timing_precision": round(precision, 4),
        "too_early": best_window in {"after search resolves", "before endboard established"},
        "too_late": best_window in {"after search resolves", "before endboard established", "after material committed"},
        "pivot_available": bool(line.recovery_routes),
        "timing_reason": f"Use {interruption} at {best_window}",
    }


def evaluate_interruption(line: OpponentLine, interruption: str) -> dict[str, Any]:
    weak_matches = any(interruption.casefold() in weak.casefold() or weak.casefold() in interruption.casefold() for weak in line.weak_to)
    choke = matching_choke(line, interruption)
    if not weak_matches and not choke:
        return {"interruption": interruption, "stop_rate": 0.0, "recovery_rate": line.resilience_score / 10, "reason": "does not hit this line"}
    base = 0.55 if weak_matches else 0.35
    if choke:
        base += 0.2
    if "Droll" in interruption and line.search_cards:
        base += 0.12
    if ("D.D. Crow" in interruption or "Ghost Belle" in interruption or "Bystial" in interruption) and line.graveyard_cards:
        base += 0.12
    if ("Infinite Impermanence" in interruption or "Effect Veiler" in interruption) and line.field_effect_cards:
        base += 0.1
    if "Nibiru" in interruption and line.line_score >= 8.5:
        base += 0.08
    recovery = max(0.05, min(0.9, line.resilience_score / 10 - base * 0.35 + len(line.recovery_cards) * 0.03))
    return {
        "interruption": interruption,
        "hit_choke_point": choke or "known weakness",
        "stop_rate": round(min(0.95, base), 4),
        "recovery_rate": round(recovery, 4),
        "reason": f"{interruption} hits {choke or line.line_name}",
    }


def matching_choke(line: OpponentLine, interruption: str) -> str | None:
    lowered = interruption.casefold()
    for choke in line.choke_points:
        c = choke.casefold()
        if "Ash" in interruption and ("search" in c or "fusion" in c or "tip" in c):
            return choke
        if "Droll" in interruption and ("search" in c or "add" in c):
            return choke
        if ("Crow" in interruption or "Belle" in interruption or "Bystial" in interruption or "Shifter" in interruption) and ("gy" in c or "grave" in c or "revive" in c or "fusion trigger" in c):
            return choke
        if ("Impermanence" in interruption or "Veiler" in interruption) and ("summon" in c or "resolution" in c or "search" in c):
            return choke
        if ("Cosmic" in interruption or "Duster" in interruption or "Storm" in interruption) and ("fountain" in c or "welcome" in c or "sangen" in c or "map" in c):
            return choke
        if lowered and lowered in c:
            return choke
    return None


def normalize_interruption(card_name: str) -> str | None:
    lowered = str(card_name).casefold()
    for label, aliases in INTERRUPTION_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return label
    return None


def empty_report(opponent: str, available_interruptions: list[str]) -> dict[str, Any]:
    report = {
        "opponent": opponent,
        "available_interruptions": available_interruptions,
        "likely_lines": [],
        "best_interruptions": [],
        "choke_results": [],
        "best_timing_windows": [],
        "bad_timing_windows": [],
        "line_branch_results": [],
        "average_stop_rate": 0.0,
        "average_recovery_rate": 0.0,
        "timing_precision_score": 0.0,
        "pivot_risk_score": 0.0,
        "best_timing_window_count": 0,
        "late_interruption_risk": 0.0,
        "early_interruption_risk": 0.0,
        "backup_line_success_rate": 0.0,
        "recommended_interruptions": [],
        "poor_interruptions": [],
        "choke_coverage_score": 0.0,
        "best_interruption_overlap": 0,
        "poor_interruption_count": 0,
    }
    report.update(empty_graph_report())
    return report


def empty_graph_report() -> dict[str, Any]:
    return {
        "graph_name": None,
        "graph_route": [],
        "route_results": [],
        "graph_stop_rate": 0.0,
        "graph_pivot_rate": 0.0,
        "graph_endboard_reduction_score": 0.0,
        "graph_timing_precision_score": 0.0,
        "best_interruption_nodes": [],
        "poor_interruption_nodes": [],
        "graph_best_interruption_count": 0,
        "graph_poor_interruption_count": 0,
        "opponent_resource_valid_rate": 0.0,
        "opponent_resource_failure_rate": 0.0,
        "opponent_pivot_success_rate": 0.0,
        "opponent_backup_success_rate": 0.0,
        "opponent_missing_card_failures": {},
        "opponent_missing_extra_failures": {},
        "opponent_once_per_turn_failures": 0,
        "opponent_normal_summon_failures": 0,
        "opponent_starter_open_rate": 0.0,
        "opponent_extender_open_rate": 0.0,
        "opponent_interruption_open_rate": 0.0,
        "opponent_brick_rate": 0.0,
        "probability_weighted_resource_valid_rate": 0.0,
        "probability_weighted_stop_rate": 0.0,
        "probability_weighted_pivot_rate": 0.0,
        "probability_weighted_backup_rate": 0.0,
    }


def late_interruption_risk(windows: list[str]) -> float:
    if not windows:
        return 0.0
    late = sum(1 for window in windows if window in {"after search resolves", "after material committed", "before endboard established"})
    return round(late / len(windows), 4)


def early_interruption_risk(windows: list[str]) -> float:
    if not windows:
        return 0.0
    early = sum(1 for window in windows if window in {"on activation", "on summon"})
    return round(early / len(windows), 4)


def opponent_label(opponent_profile: str | OpponentProfile | None) -> str:
    if isinstance(opponent_profile, OpponentProfile):
        return opponent_profile.matched_curated_profile or opponent_profile.archetype or opponent_profile.name
    return str(opponent_profile or "unknown")
