from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from deck.filler_signal_gates import evaluate_filler_signal_eligibility
from deck.generic_filler_memory import load_generic_filler_memory
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text, safe_load_json


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "generic_benchmarks"
HOLDOUT_REPORT_PATH = Path("SystemAIYugioh") / "data" / "training_runs" / "filler_holdout" / "latest_filler_holdout_report.json"


def build_filler_signal_gate_report(memory: dict[str, Any] | None = None) -> dict[str, Any]:
    memory = memory or load_generic_filler_memory()
    holdout_by_card = load_latest_holdout_by_card()
    local_rows = []
    for archetype, modes in (memory.get("profiles", {}) or {}).items():
        if not isinstance(modes, dict):
            continue
        for mode, profile in modes.items():
            for card, entry in (profile.get("fillers", {}) or {}).items():
                evaluation = evaluate_filler_signal_eligibility(str(card), entry)
                evaluation["archetype"] = archetype
                evaluation["mode"] = mode
                evaluation["scope"] = "archetype_local"
                evaluation["times_used"] = entry.get("times_used", 0)
                evaluation["archetype_breadth"] = entry.get("archetype_breadth", 0)
                evaluation["near_eligible_score"] = len(evaluation.get("passed_gates", []))
                evaluation["missing_gate_count"] = len(evaluation.get("failed_gates", []))
                local_rows.append(evaluation)
    aggregate_rows = []
    for card, entry in aggregate_memory_by_card(memory).items():
        evaluation = evaluate_filler_signal_eligibility(str(card), entry)
        evaluation["archetype"] = "cross_archetype"
        evaluation["mode"] = "all"
        evaluation["scope"] = "cross_archetype_aggregate"
        evaluation["times_used"] = entry.get("times_used", 0)
        evaluation["archetype_breadth"] = entry.get("archetype_breadth", 0)
        evaluation["near_eligible_score"] = len(evaluation.get("passed_gates", []))
        evaluation["missing_gate_count"] = len(evaluation.get("failed_gates", []))
        aggregate_rows.append(evaluation)
    rows = aggregate_rows or local_rows
    apply_holdout_status(rows, holdout_by_card)
    apply_holdout_status(aggregate_rows, holdout_by_card)
    apply_holdout_status(local_rows, holdout_by_card)
    eligible = [row for row in rows if row.get("eligible")]
    failed = [row for row in rows if not row.get("eligible")]
    near = sorted(failed, key=lambda row: (row.get("near_eligible_score", 0), -row.get("missing_gate_count", 0)), reverse=True)[:10]
    failure_counter = Counter(failure for row in failed for failure in row.get("failed_gates", []))
    concentration_blocked = [row for row in failed if "concentration_clearance" in row.get("failed_gates", [])]
    support_blocked = [row for row in failed if "observation_floor" in row.get("failed_gates", [])]
    breadth_blocked = [row for row in failed if "archetype_breadth" in row.get("failed_gates", [])]
    attribution_blocked = [
        row
        for row in failed
        if "attribution_majority" in row.get("failed_gates", []) or "indeterminate_suppression" in row.get("failed_gates", [])
    ]
    activation_ready = [row for row in eligible if row.get("activation_ready")]
    report = {
        "report_type": "filler_signal_gate_report",
        "eligible_signals": eligible,
        "near_eligible_signals": near,
        "failed_signals": failed,
        "aggregate_signals": aggregate_rows,
        "local_signals": local_rows,
        "concentration_warnings": memory.get("concentration_warnings", []),
        "support_failures": support_blocked,
        "archetype_breadth_failures": breadth_blocked,
        "concentration_failures": concentration_blocked,
        "attribution_failures": attribution_blocked,
        "summary": {
            "eligible_count": len(eligible),
            "activation_ready_count": len(activation_ready),
            "activation_ready_fillers": unique_cards(row.get("card") for row in activation_ready),
            "near_eligible_count": len(near),
            "failed_count": len(failed),
            "failure_counts": dict(failure_counter),
            "cards_closest_to_eligibility": unique_cards(row.get("card") for row in near[:10])[:5],
            "cards_blocked_by_concentration": unique_cards(row.get("card") for row in concentration_blocked)[:10],
            "cards_blocked_by_support": unique_cards(row.get("card") for row in support_blocked)[:10],
            "cards_blocked_by_archetype_breadth": unique_cards(row.get("card") for row in breadth_blocked)[:10],
            "cards_blocked_by_attribution": unique_cards(row.get("card") for row in attribution_blocked)[:10],
            "aggregate_signal_count": len(aggregate_rows),
        },
    }
    return report


def load_latest_holdout_by_card() -> dict[str, dict[str, Any]]:
    payload = safe_load_json(HOLDOUT_REPORT_PATH, {})
    if not isinstance(payload, dict):
        return {}
    return {
        str(row.get("filler")): row
        for row in payload.get("results", []) or []
        if isinstance(row, dict) and row.get("filler")
    }


def apply_holdout_status(rows: list[dict[str, Any]], holdout_by_card: dict[str, dict[str, Any]]) -> None:
    for row in rows:
        card = str(row.get("card", ""))
        holdout = holdout_by_card.get(card, {})
        required = bool(row.get("eligible"))
        passed = bool(holdout.get("holdout_passed")) if holdout else False
        row["holdout_required"] = required
        row["holdout_passed"] = passed
        row["holdout_average_delta"] = holdout.get("average_holdout_delta", 0.0) if holdout else 0.0
        row["holdout_support_count"] = int(holdout.get("positive_count", 0) or 0) + int(holdout.get("neutral_count", 0) or 0) if holdout else 0
        row["holdout_contradiction_count"] = int(holdout.get("negative_count", 0) or 0) if holdout else 0
        row["activation_ready"] = bool(row.get("eligible") and passed)


def aggregate_memory_by_card(memory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for archetype, modes in (memory.get("profiles", {}) or {}).items():
        if not isinstance(modes, dict):
            continue
        for _mode, profile in modes.items():
            if not isinstance(profile, dict):
                continue
            for card, entry in (profile.get("fillers", {}) or {}).items():
                target = aggregate.setdefault(str(card), empty_aggregate_entry())
                amount = safe_int(entry.get("times_used"))
                target["times_used"] += amount
                for key in (
                    "completion_only_count",
                    "performance_positive_count",
                    "performance_neutral_count",
                    "performance_negative_count",
                    "indeterminate_count",
                    "shared_attribution_count",
                    "single_card_attribution_count",
                    "legal_observation_count",
                    "illegal_observation_count",
                ):
                    target[key] += safe_int(entry.get(key))
                archetype_key = str(archetype).casefold()
                observations = target.setdefault("archetype_observations", {})
                observations[archetype_key] = safe_int(observations.get(archetype_key)) + amount
                target["affected_archetypes"] = sorted(set(target.get("affected_archetypes", [])) | {archetype_key})
                merge_weighted_average(target, entry, "average_score_delta", amount)
                merge_weighted_average(target, entry, "average_confidence_delta", amount)
                merge_weighted_average(target, entry, "average_attribution_confidence", safe_int(entry.get("average_attribution_confidence_count", amount)))
                provenance = entry.get("last_observation_provenance")
                if isinstance(provenance, dict):
                    target["last_observation_provenance"] = provenance
    for entry in aggregate.values():
        entry["archetype_breadth"] = len(entry.get("affected_archetypes", []) or [])
        entry["completion_bias_flag"] = completion_ratio(entry) >= 0.5
    return aggregate


def empty_aggregate_entry() -> dict[str, Any]:
    return {
        "times_used": 0,
        "completion_only_count": 0,
        "performance_positive_count": 0,
        "performance_neutral_count": 0,
        "performance_negative_count": 0,
        "indeterminate_count": 0,
        "shared_attribution_count": 0,
        "single_card_attribution_count": 0,
        "legal_observation_count": 0,
        "illegal_observation_count": 0,
        "average_score_delta": 0.0,
        "average_confidence_delta": 0.0,
        "average_attribution_confidence": 0.0,
        "archetype_observations": {},
        "affected_archetypes": [],
        "archetype_breadth": 0,
        "completion_bias_flag": False,
        "last_observation_provenance": {},
    }


def merge_weighted_average(target: dict[str, Any], entry: dict[str, Any], key: str, fallback_count: int) -> None:
    count = safe_int(entry.get(f"{key}_count"), fallback_count)
    total = safe_float(entry.get(f"{key}_total"), safe_float(entry.get(key)) * count)
    target[f"{key}_total"] = safe_float(target.get(f"{key}_total")) + total
    target[f"{key}_count"] = safe_int(target.get(f"{key}_count")) + count
    target[key] = round(target[f"{key}_total"] / max(1, target[f"{key}_count"]), 4)


def completion_ratio(entry: dict[str, Any]) -> float:
    times = max(1, safe_int(entry.get("times_used")))
    return safe_int(entry.get("completion_only_count")) / times


def unique_cards(cards: Any) -> list[str]:
    seen = set()
    unique = []
    for card in cards:
        if not card or card in seen:
            continue
        seen.add(card)
        unique.append(str(card))
    return unique


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Filler Signal Gate Report",
        "",
        f"- Eligible signals: {report.get('summary', {}).get('eligible_count', 0)}",
        f"- Activation-ready signals: {report.get('summary', {}).get('activation_ready_count', 0)}",
        f"- Activation-ready fillers: {', '.join(report.get('summary', {}).get('activation_ready_fillers', []) or ['none'])}",
        f"- Failed signals: {report.get('summary', {}).get('failed_count', 0)}",
        f"- Closest to eligibility: {', '.join(report.get('summary', {}).get('cards_closest_to_eligibility', []) or ['none'])}",
        f"- Failure counts: {report.get('summary', {}).get('failure_counts', {})}",
        f"- Blocked by concentration: {', '.join(report.get('summary', {}).get('cards_blocked_by_concentration', []) or ['none'])}",
        f"- Blocked by support: {', '.join(report.get('summary', {}).get('cards_blocked_by_support', []) or ['none'])}",
        f"- Blocked by attribution: {', '.join(report.get('summary', {}).get('cards_blocked_by_attribution', []) or ['none'])}",
        "",
        "## Eligible Signals",
        "",
    ]
    if report.get("eligible_signals"):
        for row in report["eligible_signals"]:
            lines.append(
                f"- {row.get('card')} ({row.get('archetype')} / {row.get('mode')}) "
                f"holdout_passed={row.get('holdout_passed')} activation_ready={row.get('activation_ready')} "
                f"avg_delta={row.get('holdout_average_delta')}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Near Eligible", ""])
    for row in report.get("near_eligible_signals", [])[:10]:
        lines.append(f"- {row.get('card')} ({row.get('archetype')}): failed {', '.join(row.get('failed_gates', []))}")
    if not report.get("near_eligible_signals"):
        lines.append("- None")
    lines.extend(["", "## Concentration Warnings", ""])
    for warning in report.get("concentration_warnings", [])[:10]:
        lines.append(
            f"- {warning.get('card')}: {warning.get('dominant_archetype')} "
            f"{warning.get('single_archetype_share')} over {warning.get('total_observations')} observations"
        )
    if not report.get("concentration_warnings"):
        lines.append("- None")
    return "\n".join(lines) + "\n"


def save_gate_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_filler_signal_gate_report.json"
    markdown_path = REPORT_DIR / "latest_filler_signal_gate_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(markdown_path, render_markdown(report))
    return json_path, markdown_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report filler-memory signal gate eligibility.")
    parser.add_argument("--save", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_filler_signal_gate_report()
    print("Filler Signal Gate Report")
    print(f"Eligible signals: {report['summary']['eligible_count']}")
    print(f"Failed signals: {report['summary']['failed_count']}")
    print(f"Closest to eligibility: {', '.join(report['summary']['cards_closest_to_eligibility']) or 'none'}")
    if args.save:
        json_path, markdown_path = save_gate_report(report)
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
