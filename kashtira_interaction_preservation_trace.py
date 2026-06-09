from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.interaction_preservation_trace import trace_interaction_preservation
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"
TRACE_JSON = REPORT_DIR / "latest_kashtira_interaction_preservation_trace.json"
TRACE_MD = REPORT_DIR / "latest_kashtira_interaction_preservation_trace.md"


def build_report(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    trace = trace_interaction_preservation(cards, "Kashtira", mode, runs, seed)
    return {
        "report_type": "kashtira_interaction_preservation_trace",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "runs": max(1, int(runs or 1)),
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        **trace,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(TRACE_JSON, report)
    atomic_write_text(TRACE_MD, render_markdown(report))
    return TRACE_JSON, TRACE_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Kashtira Interaction Preservation Trace",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Not activated: {report['not_activated']}",
        f"- Selection behavior changed: {report['selection_behavior_changed']}",
        "",
        "## Card Traces",
        "",
        "| Card | Generic | Experimental | Hybrid | Selected Stage | Rejection Stage | Classification |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in report["card_traces"]:
        lines.append(
            f"| {row['card']} | {row['generic_count']} | {row['experimental_count']} | {row['hybrid_count']} | "
            f"{row['selected_stage']} | {row['rejection_stage']} | {', '.join(row['failure_classification'])} |"
        )
    lines.extend(["", "## Findings", ""])
    for row in report["card_traces"]:
        lines.extend(
            [
                f"### {row['card']}",
                "",
                f"- Available in pool: {row['available_in_pool']}",
                f"- Legal: {row['legal']}",
                f"- Experimental path: `{row['experimental_path']}`",
                f"- Hybrid path: `{row['hybrid_path']}`",
                f"- Rejection reason: {row['rejection_reason'] or 'none'}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace Kashtira interaction preservation through experimental builder stages.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = build_report(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Interaction Preservation Trace Complete")
    print(f"Runs: {report['runs']}")
    for row in report["card_traces"]:
        print(f"- {row['card']}: {', '.join(row['failure_classification'])}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
