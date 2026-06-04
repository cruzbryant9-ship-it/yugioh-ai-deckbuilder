from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.semi_specialized_quota_replay import replay_quota_sensitivity
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def build_report(archetype: str, mode: str, runs: int) -> dict[str, Any]:
    sensitivity = replay_quota_sensitivity(archetype, mode, runs)
    return {
        "report_type": "semi_specialization_quota_sensitivity",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "semi_specialization_activated": False,
        "sensitivity": sensitivity,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_sensitivity_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_sensitivity_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    sensitivity = report["sensitivity"]
    lines = [
        f"# {report['archetype']} Quota Movement Sensitivity Report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Not activated: {sensitivity['not_activated']}",
        f"- Generic total gap: {sensitivity['generic_total_gap']}",
        f"- Stability classification: `{sensitivity['stability_classification']}`",
        "",
        "## Gap By Movement Strength",
        "",
    ]
    for result in sensitivity["sensitivity_results"]:
        lines.append(
            f"- `{result['movement_strength']}`: total gap {result['total_gap']}, "
            f"delta vs baseline {result['gap_delta_vs_baseline']}, "
            f"worsened roles {', '.join(result['worsened_roles']) or 'none'}"
        )
    lines.extend(["", "## Role Gaps", ""])
    for result in sensitivity["sensitivity_results"]:
        lines.append(f"### Movement {result['movement_strength']}")
        for role, row in result["role_gaps"].items():
            lines.append(f"- `{role}`: gap {row['gap']} ({row['gap_type']})")
        lines.append("")
    lines.extend(["## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in sensitivity["risk_flags"]) if sensitivity["risk_flags"] else lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Kashtira quota movement sensitivity without activating semi-specialization.")
    parser.add_argument("--archetype", required=True)
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode, args.runs)
    json_path, md_path = save_report(report)
    sensitivity = report["sensitivity"]
    print("Semi-Specialization Sensitivity Replay Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Not activated: {sensitivity['not_activated']}")
    print(f"Stability classification: {sensitivity['stability_classification']}")
    for result in sensitivity["sensitivity_results"]:
        print(
            f"Movement {result['movement_strength']}: gap {result['total_gap']}, "
            f"delta {result['gap_delta_vs_baseline']}, "
            f"worsened {', '.join(result['worsened_roles']) or 'none'}"
        )
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
