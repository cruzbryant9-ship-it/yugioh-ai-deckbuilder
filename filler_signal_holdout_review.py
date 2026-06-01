from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filler_signal_gate_report import build_filler_signal_gate_report, save_gate_report
from single_filler_attribution_benchmark import (
    card_lookup,
    run_single_filler_test,
    score_snapshot,
)
from deck.builder import score_deck_breakdown
from deck.deck_utils import split_deck
from deck.generic_deck_builder import build_generic_deck
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.memory_context import normalize_provenance


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "filler_holdout"
REPORT_VERSION = "phase6s-v1"
POSITIVE_DELTA = 0.5
NEGATIVE_DELTA = -0.5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review eligible filler signals against holdout-style controlled comparisons.")
    parser.add_argument("--archetypes", nargs="+", default=["Branded", "Kashtira", "Runick", "Tearlaments"])
    parser.add_argument("--mode", default="meta", choices=("meta", "innovation"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fillers", nargs="*", default=None, help="Override eligible filler list for targeted testing.")
    return parser.parse_args()


def run_holdout_review(
    archetypes: list[str],
    mode: str = "meta",
    runs: int = 3,
    fillers: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = normalize_provenance(provenance, source="filler_signal_holdout_review", smoke=runs <= 1)
    gate_before = build_filler_signal_gate_report()
    eligible_fillers = fillers or [str(row.get("card")) for row in gate_before.get("eligible_signals", []) if row.get("card")]
    cards = CardDatabase().load_cards()
    lookup = card_lookup(cards)
    all_rows: list[dict[str, Any]] = []
    results = []

    for filler in eligible_fillers:
        filler_rows = []
        for archetype in archetypes:
            for run_index in range(max(1, int(runs or 1))):
                baseline_deck, baseline_report = build_generic_deck(archetype, cards, mode=mode, use_ratio_memory=False)
                baseline_score = score_deck_breakdown(baseline_deck, archetype, mode)
                baseline_main, baseline_extra = split_deck(baseline_deck)
                row = run_single_filler_test(
                    archetype,
                    mode,
                    run_index + 1,
                    filler,
                    lookup,
                    baseline_deck,
                    baseline_main,
                    baseline_extra,
                    baseline_report,
                    score_snapshot(baseline_score, baseline_report, baseline_main),
                )
                row["holdout_classification"] = classify_holdout_delta(row.get("score_delta", 0))
                row["supports_eligibility"] = row.get("holdout_classification") in {"positive", "neutral"} and row.get("clean_single_card_attribution")
                row["contradicts_eligibility"] = row.get("holdout_classification") == "negative" or not row.get("clean_single_card_attribution")
                filler_rows.append(row)
                all_rows.append(row)
        results.append(summarize_filler_holdout(filler, filler_rows, gate_before))

    report = {
        "report_type": "filler_signal_holdout_review",
        "report_version": REPORT_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {"archetypes": archetypes, "mode": mode, "runs": runs, "fillers": eligible_fillers},
        "provenance": provenance,
        "summary": summarize_holdout_report(results),
        "eligible_before_holdout": eligible_fillers,
        "results": results,
        "test_rows": strip_internal_impacts(all_rows),
        "gate_report_before": gate_before.get("summary", {}),
    }
    return report


def summarize_filler_holdout(filler: str, rows: list[dict[str, Any]], gate_before: dict[str, Any]) -> dict[str, Any]:
    positive = [row for row in rows if row.get("holdout_classification") == "positive"]
    neutral = [row for row in rows if row.get("holdout_classification") == "neutral"]
    negative = [row for row in rows if row.get("holdout_classification") == "negative"]
    clean_rows = [row for row in rows if row.get("clean_single_card_attribution")]
    deltas = [float(row.get("score_delta", 0) or 0) for row in rows]
    confidence_deltas = [float(row.get("confidence_delta", 0) or 0) for row in rows]
    contradictions = [
        {
            "archetype": row.get("archetype"),
            "run": row.get("run"),
            "score_delta": row.get("score_delta"),
            "reason": row.get("failure_reason") or row.get("holdout_classification"),
        }
        for row in rows
        if row.get("contradicts_eligibility")
    ]
    average_delta = round(sum(deltas) / max(1, len(deltas)), 4)
    negative_rate = len(negative) / max(1, len(rows))
    clean_rate = len(clean_rows) / max(1, len(rows))
    passed = bool(rows) and clean_rate >= 0.8 and average_delta >= 0.0 and negative_rate <= 0.4 and (len(positive) + len(neutral)) >= len(negative)
    return {
        "filler": filler,
        "eligible_before_holdout": filler in {str(row.get("card")) for row in gate_before.get("eligible_signals", [])},
        "holdout_tests": len(rows),
        "positive_count": len(positive),
        "neutral_count": len(neutral),
        "negative_count": len(negative),
        "clean_single_card_count": len(clean_rows),
        "average_holdout_delta": average_delta,
        "average_confidence_delta": round(sum(confidence_deltas) / max(1, len(confidence_deltas)), 4),
        "confidence_stability": confidence_stability(confidence_deltas),
        "holdout_passed": passed,
        "contradictions": contradictions[:20],
        "archetype_results": summarize_by_archetype(rows),
    }


def summarize_holdout_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    activation_ready = [row.get("filler") for row in results if row.get("eligible_before_holdout") and row.get("holdout_passed")]
    failed = [row.get("filler") for row in results if row.get("eligible_before_holdout") and not row.get("holdout_passed")]
    return {
        "eligible_signals_reviewed": len(results),
        "holdout_passed_count": len(activation_ready),
        "holdout_failed_count": len(failed),
        "activation_ready_count": len(activation_ready),
        "activation_ready_fillers": activation_ready,
        "holdout_failed_fillers": failed,
        "average_holdout_delta_by_filler": {row.get("filler"): row.get("average_holdout_delta", 0) for row in results},
    }


def summarize_by_archetype(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("archetype", "unknown")), []).append(row)
    summary = {}
    for archetype, group in grouped.items():
        deltas = [float(row.get("score_delta", 0) or 0) for row in group]
        summary[archetype] = {
            "tests": len(group),
            "average_delta": round(sum(deltas) / max(1, len(deltas)), 4),
            "positive": sum(1 for row in group if row.get("holdout_classification") == "positive"),
            "neutral": sum(1 for row in group if row.get("holdout_classification") == "neutral"),
            "negative": sum(1 for row in group if row.get("holdout_classification") == "negative"),
        }
    return summary


def classify_holdout_delta(value: Any) -> str:
    try:
        delta = float(value or 0)
    except (TypeError, ValueError):
        delta = 0.0
    if delta >= POSITIVE_DELTA:
        return "positive"
    if delta <= NEGATIVE_DELTA:
        return "negative"
    return "neutral"


def confidence_stability(values: list[float]) -> str:
    if not values:
        return "unknown"
    minimum = min(values)
    average = sum(values) / max(1, len(values))
    if minimum < -0.15:
        return "unstable"
    if average < -0.05:
        return "mixed"
    return "stable"


def strip_internal_impacts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped = []
    for row in rows:
        copy = dict(row)
        copy.pop("impact_report", None)
        stripped.append(copy)
    return stripped


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Filler Signal Holdout Review",
        "",
        f"- JSON report: `{json_path}`",
        f"- Mode: {report.get('config', {}).get('mode')}",
        f"- Archetypes: {', '.join(report.get('config', {}).get('archetypes', []))}",
        f"- Eligible signals reviewed: {summary.get('eligible_signals_reviewed', 0)}",
        f"- Holdout passed: {summary.get('holdout_passed_count', 0)}",
        f"- Activation-ready count: {summary.get('activation_ready_count', 0)}",
        f"- Activation-ready fillers: {', '.join(summary.get('activation_ready_fillers', []) or ['none'])}",
        "",
        "## Results",
        "",
        "| Filler | Tests | Positive | Neutral | Negative | Avg Delta | Confidence | Passed |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report.get("results", []):
        lines.append(
            f"| {row.get('filler')} | {row.get('holdout_tests', 0)} | {row.get('positive_count', 0)} | "
            f"{row.get('neutral_count', 0)} | {row.get('negative_count', 0)} | {row.get('average_holdout_delta', 0)} | "
            f"{row.get('confidence_stability')} | {'yes' if row.get('holdout_passed') else 'no'} |"
        )
    lines.extend(["", "## Contradictions", ""])
    any_contradictions = False
    for row in report.get("results", []):
        for item in row.get("contradictions", [])[:8]:
            any_contradictions = True
            lines.append(f"- {row.get('filler')} / {item.get('archetype')} run {item.get('run')}: {item.get('score_delta')} ({item.get('reason')})")
    if not any_contradictions:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_filler_holdout_report.json"
    markdown_path = REPORT_DIR / "latest_filler_holdout_report.md"
    timestamp_path = REPORT_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_filler_holdout_report.json"
    atomic_write_json(json_path, report)
    atomic_write_json(timestamp_path, report)
    atomic_write_text(markdown_path, render_markdown(report, json_path))
    save_gate_report(build_filler_signal_gate_report())
    return json_path, markdown_path


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")
    report = run_holdout_review(args.archetypes, mode=args.mode, runs=args.runs, fillers=args.fillers)
    json_path, markdown_path = save_reports(report)
    summary = report["summary"]
    print("\nFiller Signal Holdout Review Complete")
    print(f"Eligible signals reviewed: {summary.get('eligible_signals_reviewed', 0)}")
    print(f"Holdout passed: {summary.get('holdout_passed_count', 0)}")
    print(f"Activation-ready count: {summary.get('activation_ready_count', 0)}")
    print(f"Activation-ready fillers: {', '.join(summary.get('activation_ready_fillers', []) or ['none'])}")
    for result in report.get("results", []):
        print(
            f"- {result.get('filler')}: avg {result.get('average_holdout_delta')} "
            f"pos/neu/neg {result.get('positive_count')}/{result.get('neutral_count')}/{result.get('negative_count')} "
            f"passed={result.get('holdout_passed')}"
        )
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
