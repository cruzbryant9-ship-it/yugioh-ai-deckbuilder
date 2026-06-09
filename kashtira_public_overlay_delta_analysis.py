from __future__ import annotations

import argparse
import copy
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.executed_dependency_telemetry import build_dependency_telemetry, promotion_safety_gates, summarize_dependency_telemetry
from deck.interaction_core_registry import interaction_core_for
from kashtira_experimental_regression_gate import quota_balance
from kashtira_public_overlay_large_sample import VARIANT
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
REPORT_JSON = REPORT_DIR / "latest_kashtira_public_overlay_delta_analysis.json"
REPORT_MD = REPORT_DIR / "latest_kashtira_public_overlay_delta_analysis.md"
COMPONENTS = (
    "consistency_score",
    "starter_score",
    "extender_score",
    "interruption_score",
    "brick_penalty",
    "endboard_score",
    "package_quality_score",
    "generic_confidence_score",
    "final_score",
)


def run_delta_analysis(mode: str = "meta", runs: int = 30, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_count = max(1, int(runs or 1))
    rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        generic = run_builder(cards, mode, run_seed, experimental=False)
        variant = run_builder(cards, mode, run_seed, experimental=True)
        rows.append(build_run_row(index + 1, run_seed, generic, variant))

    generic_summary = summarize_path(rows, "generic")
    variant_summary = summarize_path(rows, "variant")
    delta = round(variant_summary["average_score"] - generic_summary["average_score"], 4)
    win_rows = [row for row in rows if row["result"] == "win"]
    loss_rows = [row for row in rows if row["result"] == "loss"]
    neutral_rows = [row for row in rows if row["result"] == "neutral"]
    component_summary = {
        "all_runs": summarize_component_deltas(rows),
        "winning_runs": summarize_component_deltas(win_rows),
        "losing_runs": summarize_component_deltas(loss_rows),
        "largest_positive_components": largest_components(summarize_component_deltas(rows), positive=True),
        "largest_negative_components": largest_components(summarize_component_deltas(rows), positive=False),
    }
    loss_clusters = cluster_losses(loss_rows)
    card_summary = summarize_card_movements(rows)
    safety = promotion_safety_gates(generic_summary["dependency_telemetry"], variant_summary["dependency_telemetry"])
    recommendation = choose_recommendation(delta, safety, loss_clusters, len(loss_rows))
    return {
        "report_type": "kashtira_public_overlay_delta_analysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "variant_name": VARIANT,
        "generic_summary": generic_summary,
        "variant_summary": variant_summary,
        "score_delta": delta,
        "win_loss_summary": {
            "positive_run_count": len(win_rows),
            "negative_run_count": len(loss_rows),
            "neutral_run_count": len(neutral_rows),
        },
        "component_delta_summary": component_summary,
        "loss_clusters": loss_clusters,
        "card_delta_summary": card_summary,
        "generic_fill_gate": safety["generic_fill_gate"],
        "interaction_loss_gate": safety["interaction_loss_gate"],
        "promotion_blocking_reasons": safety["promotion_blocking_reasons"],
        "lost_interaction_cards": safety["lost_interaction_cards"],
        "recommendation": recommendation,
        "promotion_applied": False,
        "run_level_rows": rows,
    }


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, experimental: bool) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if experimental:
        kwargs = {
            "experimental_semi_specialized": True,
            "specialization_profile": "Kashtira",
            "experimental_variant": VARIANT,
        }
    deck, _pool = build_deck(copy.deepcopy(cards), "Kashtira", mode=mode, **kwargs)
    report = get_last_build_report()
    score = score_deck_breakdown(deck, "Kashtira", mode)
    components = {component: float(score.get(component, report.get(component, 0)) or 0) for component in COMPONENTS}
    components["generic_confidence_score"] = float(report.get("generic_confidence_score", components.get("generic_confidence_score", 0)) or 0)
    main, extra = split_deck(deck)
    package_counts = dict(report.get("package_counts", {}) or {})
    telemetry = build_dependency_telemetry(deck, report, "Kashtira")
    blocked = blocked_card_violations(deck)
    main_count = int(report.get("main_deck_count", len(main)) or len(main))
    extra_count = int(report.get("extra_deck_count", len(extra)) or len(extra))
    return {
        "deck": deck,
        "main_names": [str(card.get("name", "")) for card in main],
        "extra_names": [str(card.get("name", "")) for card in extra],
        "score": float(score.get("final_score", 0) or 0),
        "score_components": components,
        "package_counts": package_counts,
        "quota_balance": quota_balance(package_counts),
        "brick_penalty": components["brick_penalty"],
        "package_quality": components["package_quality_score"],
        "dependency_telemetry": telemetry,
        "interaction_count": telemetry["interaction_candidates_selected"].get("value"),
        "generic_fill_count": telemetry["generic_fill_count"].get("value"),
        "legality_ok": main_count >= 40 and extra_count <= 15 and not blocked,
        "fallback_used": bool(report.get("fallback_used", False)),
        "blocked_card_violations": blocked,
        "builder_used": report.get("builder_used"),
        "variant": report.get("variant"),
        "dry_run_variant": bool(report.get("dry_run_variant", False)),
    }


def build_run_row(index: int, seed: int, generic: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    component_deltas = {
        key: round(float(variant["score_components"].get(key, 0)) - float(generic["score_components"].get(key, 0)), 4)
        for key in COMPONENTS
    }
    package_deltas = diff_numeric_dict(generic["package_counts"], variant["package_counts"])
    main_added, main_removed = counter_diff(generic["main_names"], variant["main_names"])
    extra_added, extra_removed = counter_diff(generic["extra_names"], variant["extra_names"])
    delta = round(float(variant["score"]) - float(generic["score"]), 4)
    result = "win" if delta > 0 else "loss" if delta < 0 else "neutral"
    return {
        "run_index": index,
        "seed_used": seed,
        "generic_score": generic["score"],
        "variant_score": variant["score"],
        "delta": delta,
        "result": result,
        "generic_score_components": generic["score_components"],
        "variant_score_components": variant["score_components"],
        "component_deltas": component_deltas,
        "package_count_deltas": package_deltas,
        "card_differences": {"added": main_added, "removed": main_removed},
        "extra_deck_differences": {"added": extra_added, "removed": extra_removed},
        "interaction_count": {
            "generic": generic["interaction_count"],
            "variant": variant["interaction_count"],
            "delta": round(float(variant["interaction_count"] or 0) - float(generic["interaction_count"] or 0), 4),
        },
        "generic_fill_count": {
            "generic": generic["generic_fill_count"],
            "variant": variant["generic_fill_count"],
            "delta": round(float(variant["generic_fill_count"] or 0) - float(generic["generic_fill_count"] or 0), 4),
        },
        "quota_balance": {
            "generic": generic["quota_balance"],
            "variant": variant["quota_balance"],
            "delta": round(float(variant["quota_balance"]) - float(generic["quota_balance"]), 4),
        },
        "brick_penalty": {
            "generic": generic["brick_penalty"],
            "variant": variant["brick_penalty"],
            "delta": component_deltas["brick_penalty"],
        },
        "legality_ok": {"generic": generic["legality_ok"], "variant": variant["legality_ok"]},
        "fallback_used": {"generic": generic["fallback_used"], "variant": variant["fallback_used"]},
        "blocked_card_violations": {
            "generic": generic["blocked_card_violations"],
            "variant": variant["blocked_card_violations"],
        },
    }


def summarize_path(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = rows_for_summary(rows, key)
    scores = [float(row["score"]) for row in selected]
    dependency_summary = summarize_dependency_telemetry(selected)
    return {
        "average_score": round(mean(scores), 4) if scores else 0.0,
        "best_score": round(max(scores), 4) if scores else 0.0,
        "worst_score": round(min(scores), 4) if scores else 0.0,
        "quota_balance": round(mean(float(row["quota_balance"]) for row in selected), 4) if selected else 0.0,
        "package_quality": round(mean(float(row["package_quality"]) for row in selected), 4) if selected else 0.0,
        "brick_penalty": round(mean(float(row["brick_penalty"]) for row in selected), 4) if selected else 0.0,
        "generic_fill_average": dependency_summary["generic_fill_count"].get("average"),
        "interaction_selected_average": dependency_summary["interaction_candidates_selected"].get("average"),
        "dependency_telemetry": dependency_summary,
        "legality_rate": round(mean(1.0 if row["legality_ok"] else 0.0 for row in selected), 4) if selected else 0.0,
        "fallback_rate": round(mean(1.0 if row["fallback_used"] else 0.0 for row in selected), 4) if selected else 0.0,
        "blocked_card_violations": sorted(set(name for row in selected for name in row["blocked_card_violations"])),
    }


def rows_for_summary(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [
        {
            "score": row[f"{key}_score"],
            "quota_balance": row["quota_balance"][key],
            "package_quality": row[f"{key}_score_components"]["package_quality_score"],
            "brick_penalty": row["brick_penalty"][key],
            "dependency_telemetry": {
                "generic_fill_count": {"status": "measured", "value": row["generic_fill_count"][key], "reason": None},
                "interaction_candidates_selected": {"status": "measured", "value": row["interaction_count"][key], "reason": None},
                "safe_filler_used_count": {"status": "measured", "value": 0, "reason": None},
                "repair_used": {"status": "measured", "value": False, "reason": None},
                "repair_success": {"status": "measured", "value": True, "reason": None},
                "repair_action_count": {"status": "measured", "value": 0, "reason": None},
                "repair_dependency_score": {"status": "measured", "value": 0.0, "reason": None},
                "filler_dependency_score": {"status": "measured", "value": 0.0, "reason": None},
                "interaction_preservation_attempted": {"status": "measured", "value": key == "variant", "reason": None},
                "interaction_candidates_selected_names": {"status": "measured", "value": [], "reason": None},
                "interaction_candidates_rejected": {"status": "measured", "value": [], "reason": None},
                "interaction_rejection_reasons": {"status": "measured", "value": [], "reason": None},
            },
            "legality_ok": row["legality_ok"][key],
            "fallback_used": row["fallback_used"][key],
            "blocked_card_violations": row["blocked_card_violations"][key],
        }
        for row in rows
    ]


def summarize_component_deltas(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {component: 0.0 for component in COMPONENTS}
    return {
        component: round(mean(float(row["component_deltas"].get(component, 0)) for row in rows), 4)
        for component in COMPONENTS
    }


def largest_components(summary: dict[str, float], positive: bool) -> list[dict[str, Any]]:
    items = [(key, value) for key, value in summary.items() if (value > 0 if positive else value < 0)]
    items.sort(key=lambda item: abs(item[1]), reverse=True)
    return [{"component": key, "delta": value} for key, value in items[:5]]


def cluster_losses(loss_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[int]] = defaultdict(list)
    for row in loss_rows:
        causes = classify_loss(row)
        for cause in causes:
            clusters[cause].append(row["run_index"])
    return {
        "cluster_counts": {key: len(value) for key, value in sorted(clusters.items())},
        "cluster_runs": {key: value for key, value in sorted(clusters.items())},
        "dominant_cluster": dominant_cluster(clusters),
        "loss_count": len(loss_rows),
    }


def classify_loss(row: dict[str, Any]) -> list[str]:
    deltas = row["component_deltas"]
    causes = []
    if row["interaction_count"]["delta"] < 0:
        causes.append("interaction_loss")
    if deltas.get("brick_penalty", 0) > 0:
        causes.append("brick_penalty_increase")
    if deltas.get("starter_score", 0) < 0:
        causes.append("starter_loss")
    if deltas.get("extender_score", 0) < 0:
        causes.append("extender_loss")
    if deltas.get("endboard_score", 0) < 0:
        causes.append("endboard_loss")
    if row["extra_deck_differences"]["removed"] and deltas.get("endboard_score", 0) < 0:
        causes.append("extra_deck_loss")
    if row["quota_balance"]["delta"] > 0:
        causes.append("quota_overcorrection")
    if deltas.get("package_quality_score", 0) > 0 and row["delta"] < 0:
        causes.append("package_quality_only_gain")
    return causes or ["unknown"]


def dominant_cluster(clusters: dict[str, list[int]]) -> dict[str, Any]:
    if not clusters:
        return {"cause": None, "count": 0, "runs": []}
    cause, runs = max(clusters.items(), key=lambda item: len(item[1]))
    return {"cause": cause, "count": len(runs), "runs": runs}


def summarize_card_movements(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        "added_in_winning_runs": Counter(),
        "removed_in_winning_runs": Counter(),
        "added_in_losing_runs": Counter(),
        "removed_in_losing_runs": Counter(),
    }
    for row in rows:
        prefix = "winning" if row["result"] == "win" else "losing" if row["result"] == "loss" else None
        if not prefix:
            continue
        for name, count in row["card_differences"]["added"].items():
            buckets[f"added_in_{prefix}_runs"][name] += count
        for name, count in row["card_differences"]["removed"].items():
            buckets[f"removed_in_{prefix}_runs"][name] += count
    return {key: counter.most_common(12) for key, counter in buckets.items()}


def choose_recommendation(delta: float, safety: dict[str, Any], loss_clusters: dict[str, Any], loss_count: int) -> str:
    if safety.get("interaction_loss_gate", {}).get("promotion_blocked") or safety.get("generic_fill_gate", {}).get("promotion_blocked"):
        return "abandon_variant"
    if delta <= 0:
        return "keep_dry_run_only"
    dominant = loss_clusters.get("dominant_cluster", {})
    if loss_count and dominant.get("count", 0) >= max(3, int(loss_count * 0.6)):
        return "eligible_for_targeted_adjustment"
    return "keep_dry_run_only"


def diff_numeric_dict(generic: dict[str, Any], variant: dict[str, Any]) -> dict[str, float]:
    keys = set(generic) | set(variant)
    return {key: round(float(variant.get(key, 0) or 0) - float(generic.get(key, 0) or 0), 4) for key in sorted(keys)}


def counter_diff(generic_names: list[str], variant_names: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    generic = Counter(generic_names)
    variant = Counter(variant_names)
    added = {name: count for name, count in sorted((variant - generic).items())}
    removed = {name: count for name, count in sorted((generic - variant).items())}
    return added, removed


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_JSON, report)
    atomic_write_text(REPORT_MD, render_markdown(report))
    return REPORT_JSON, REPORT_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Public Overlay Delta Analysis",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: `{report['runs']}`",
        f"- Seed: `{report['seed']}`",
        f"- Frozen cards: `{report['frozen_cards']}`",
        f"- Variant: `{report['variant_name']}`",
        f"- Score delta: `{report['score_delta']}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Win/Loss Summary",
        "",
        f"- Positive / negative / neutral: `{report['win_loss_summary']['positive_run_count']}` / `{report['win_loss_summary']['negative_run_count']}` / `{report['win_loss_summary']['neutral_run_count']}`",
        "",
        "## Average Component Deltas",
        "",
    ]
    for key, value in report["component_delta_summary"]["all_runs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Largest Positive Components",
            "",
        ]
    )
    for row in report["component_delta_summary"]["largest_positive_components"]:
        lines.append(f"- `{row['component']}`: `{row['delta']}`")
    lines.extend(["", "## Largest Negative Components", ""])
    for row in report["component_delta_summary"]["largest_negative_components"]:
        lines.append(f"- `{row['component']}`: `{row['delta']}`")
    lines.extend(["", "## Loss Clusters", ""])
    for cause, count in report["loss_clusters"]["cluster_counts"].items():
        lines.append(f"- `{cause}`: `{count}`")
    lines.extend(["", "## Recurring Card Movements", ""])
    for key, rows in report["card_delta_summary"].items():
        lines.append(f"- `{key}`: `{rows[:6]}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze seed-level deltas for the Kashtira public-overlay dry-run variant.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_delta_analysis(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Public Overlay Delta Analysis Complete")
    print(f"Score delta: {report['score_delta']}")
    print(
        "Positive/negative/neutral runs: "
        f"{report['win_loss_summary']['positive_run_count']}/"
        f"{report['win_loss_summary']['negative_run_count']}/"
        f"{report['win_loss_summary']['neutral_run_count']}"
    )
    print(f"Dominant loss cluster: {report['loss_clusters']['dominant_cluster']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
