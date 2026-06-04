from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.semi_specialized_quota_replay import replay_quota_plan
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def build_report(archetype: str, mode: str, runs: int) -> dict[str, Any]:
    replay = replay_quota_plan(archetype, mode, runs)
    return {
        "report_type": "semi_specialization_quota_replay",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "semi_specialization_activated": False,
        "replay": replay,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_quota_replay_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_quota_replay_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    replay = report["replay"]
    lines = [
        f"# {report['archetype']} Quota Replay Report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Not activated: {replay['not_activated']}",
        f"- Generic total gap: {replay['generic_total_gap']}",
        f"- Proposed total gap: {replay['proposed_total_gap']}",
        f"- Gap delta: {replay['gap_delta']}",
        "",
        "## Before/After Balance",
        "",
    ]
    for role, before in replay["generic_balance"].items():
        after = replay["proposed_balance"].get(role, {})
        lines.append(
            f"- `{role}`: generic gap {before['gap']} ({before['gap_type']}), "
            f"projected gap {after.get('gap')} ({after.get('gap_type')})"
        )
    lines.extend(
        [
            "",
            "## Improved Roles",
            "",
        ]
    )
    lines.extend(f"- `{role}`" for role in replay["improved_roles"]) if replay["improved_roles"] else lines.append("- None")
    lines.extend(["", "## Worsened Roles", ""])
    lines.extend(f"- `{role}`" for role in replay["worsened_roles"]) if replay["worsened_roles"] else lines.append("- None")
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in replay["risk_flags"]) if replay["risk_flags"] else lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay generic builds against a non-activated semi-specialized quota plan.")
    parser.add_argument("--archetype", required=True)
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode, args.runs)
    json_path, md_path = save_report(report)
    replay = report["replay"]
    print("Semi-Specialization Quota Replay Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Not activated: {replay['not_activated']}")
    print(f"Gap delta: {replay['gap_delta']}")
    print(f"Improved roles: {', '.join(replay['improved_roles']) or 'none'}")
    print(f"Worsened roles: {', '.join(replay['worsened_roles']) or 'none'}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
