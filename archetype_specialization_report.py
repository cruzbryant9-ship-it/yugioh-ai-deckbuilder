from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.archetype_specialization_detector import evaluate_specialization_candidate
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "archetype_specialization"
LATEST_JSON = REPORT_DIR / "latest_archetype_specialization_report.json"
LATEST_MD = REPORT_DIR / "latest_archetype_specialization_report.md"


def build_report(archetypes: list[str], mode: str) -> dict[str, Any]:
    results = [evaluate_specialization_candidate(archetype, mode) for archetype in archetypes]
    categories = {
        "ready": [row for row in results if row["candidate_status"] == "ready"],
        "watchlist": [row for row in results if row["candidate_status"] == "watchlist"],
        "not_ready": [row for row in results if row["candidate_status"] == "not_ready"],
    }
    return {
        "report_type": "archetype_specialization_candidates",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "archetypes": archetypes,
        "summary": {
            "ready_count": len(categories["ready"]),
            "watchlist_count": len(categories["watchlist"]),
            "not_ready_count": len(categories["not_ready"]),
            "failed_gates": Counter(gate for row in results for gate in row["failed_gates"]).most_common(),
        },
        "ready_candidates": categories["ready"],
        "watchlist_candidates": categories["watchlist"],
        "not_ready_candidates": categories["not_ready"],
        "results": results,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LATEST_JSON, report)
    atomic_write_text(LATEST_MD, render_markdown(report))
    return LATEST_JSON, LATEST_MD


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Archetype Specialization Candidate Report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Ready: {report['summary']['ready_count']}",
        f"- Watchlist: {report['summary']['watchlist_count']}",
        f"- Not ready: {report['summary']['not_ready_count']}",
        "",
        "## Ready Candidates",
        "",
    ]
    append_category(lines, report["ready_candidates"])
    lines.extend(["", "## Watchlist Candidates", ""])
    append_category(lines, report["watchlist_candidates"])
    lines.extend(["", "## Not-Ready Candidates", ""])
    append_category(lines, report["not_ready_candidates"])
    lines.extend(["", "## Failed Gates By Archetype", ""])
    for row in report["results"]:
        failed = ", ".join(row["failed_gates"]) or "none"
        lines.append(f"- `{row['archetype']}`: {failed}")
    lines.extend(["", "## Evidence Summary", ""])
    for row in report["results"]:
        evidence = row["evidence"]
        lines.append(
            f"- `{row['archetype']}`: score {row['readiness_score']}, "
            f"runs {evidence.get('benchmark_runs')}, improvement {evidence.get('average_tuned_improvement')}, "
            f"repair {evidence.get('repair_success_rate')}, rejected {evidence.get('rejected_deck_rate')}, "
            f"trend {evidence.get('benchmark_trend')}"
        )
    return "\n".join(lines) + "\n"


def append_category(lines: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        lines.append("- None")
        return
    for row in rows:
        lines.append(f"- `{row['archetype']}`: readiness {row['readiness_score']} - {row['recommended_next_action']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Report generic archetype specialization readiness.")
    parser.add_argument("--archetypes", nargs="+", required=True)
    parser.add_argument("--mode", default="meta")
    args = parser.parse_args()
    report = build_report(args.archetypes, args.mode)
    json_path, md_path = save_report(report)
    print("Archetype Specialization Report Complete")
    print(f"Ready: {report['summary']['ready_count']}")
    print(f"Watchlist: {report['summary']['watchlist_count']}")
    print(f"Not ready: {report['summary']['not_ready_count']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
