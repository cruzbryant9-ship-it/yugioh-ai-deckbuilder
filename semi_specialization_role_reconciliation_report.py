from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.semi_specialized_role_reconciliation import reconcile_specialization_roles
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def build_report(archetype: str, mode: str) -> dict[str, Any]:
    reconciliation = reconcile_specialization_roles(archetype, mode)
    return {
        "report_type": "semi_specialization_role_reconciliation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "semi_specialization_activated": False,
        "reconciliation": reconciliation,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_role_reconciliation_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_role_reconciliation_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    reconciliation = report["reconciliation"]
    lines = [
        f"# {report['archetype']} Role Map Reconciliation",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Not activated: {reconciliation['not_activated']}",
        f"- Proposed only: {reconciliation['proposed_only']}",
        f"- Current audit score: {reconciliation.get('current_audit_score')}",
        f"- Projected audit score: {reconciliation.get('expected_audit_score_after_reconciliation')}",
        f"- Readiness before: `{reconciliation.get('readiness_before')}`",
        f"- Projected readiness after: `{reconciliation.get('projected_readiness_after')}`",
        f"- Conflicts resolved: {reconciliation.get('conflicts_resolved')}",
        f"- Conflicts remaining: {reconciliation.get('projected_conflict_count')}",
        "",
        "## Proposed Role Updates",
        "",
    ]
    updates = reconciliation.get("proposed_role_updates", {})
    if updates:
        for card, update in updates.items():
            lines.append(
                f"- `{card}`: {', '.join(update.get('from', []))} -> {', '.join(update.get('to', []))}; "
                f"{update.get('recommendation')} (proposed only: {update.get('proposed_only')})"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Dual-Role Assignments", ""])
    duals = reconciliation.get("dual_role_assignments", {})
    if duals:
        for card, roles in duals.items():
            lines.append(f"- `{card}`: {', '.join(roles)}")
    else:
        lines.append("- None")
    lines.extend(["", "## Unresolved Conflicts", ""])
    conflicts = reconciliation.get("unresolved_conflicts", [])
    if conflicts:
        for row in conflicts:
            lines.append(f"- `{row.get('card', 'unknown')}` as `{row.get('profile_role', 'unknown')}` [{row.get('severity', 'unknown')}]: {row.get('reason')}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a proposed-only Kashtira role-map reconciliation report.")
    parser.add_argument("--archetype", default="Kashtira")
    parser.add_argument("--mode", default="meta")
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode)
    json_path, md_path = save_report(report)
    reconciliation = report["reconciliation"]
    print("Semi-Specialization Role Reconciliation Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Not activated: {reconciliation['not_activated']}")
    print(f"Proposed only: {reconciliation['proposed_only']}")
    print(f"Current audit score: {reconciliation.get('current_audit_score')}")
    print(f"Projected audit score: {reconciliation.get('expected_audit_score_after_reconciliation')}")
    print(f"Readiness before: {reconciliation.get('readiness_before')}")
    print(f"Projected readiness after: {reconciliation.get('projected_readiness_after')}")
    print(f"Conflicts resolved: {reconciliation.get('conflicts_resolved')}")
    print(f"Conflicts remaining: {reconciliation.get('projected_conflict_count')}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
