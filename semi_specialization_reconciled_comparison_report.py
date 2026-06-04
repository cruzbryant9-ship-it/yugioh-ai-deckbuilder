from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.semi_specialized_reconciled_comparison import compare_reconciled_profile
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def build_report(archetype: str, mode: str, runs: int) -> dict[str, Any]:
    comparison = compare_reconciled_profile(archetype, mode, runs)
    return {
        "report_type": "semi_specialization_reconciled_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "semi_specialization_activated": False,
        "comparison": comparison,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_reconciled_comparison_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_reconciled_comparison_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    generic = comparison["generic_summary"]
    active = comparison["active_profile_summary"]
    reconciled = comparison["reconciled_profile_summary"]
    lines = [
        f"# {report['archetype']} Reconciled Profile Comparison",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Not activated: {comparison['not_activated']}",
        f"- Activation recommendation: `{comparison['activation_recommendation']}`",
        f"- Reconciled improves balance: {comparison['reconciled_improves_balance']}",
        f"- Reconciled improves readiness: {comparison['reconciled_improves_readiness']}",
        "",
        "## Generic Summary",
        "",
        f"- Generic total gap: {generic.get('generic_total_gap')}",
        f"- Full movement projected gap: {generic.get('full_movement_projected_gap')}",
        f"- Filler dependency: {generic.get('filler_dependency')}",
        f"- Repair dependency: {generic.get('repair_dependency')}",
        f"- Blocked-card violations: {', '.join(generic.get('blocked_card_violations', [])) or 'none'}",
        "",
        "## Active Profile Summary",
        "",
        f"- Role audit score: {active.get('role_audit_score')}",
        f"- Readiness: `{active.get('readiness_classification')}`",
        f"- Role conflicts: {active.get('role_conflicts')}",
        f"- Quota gap: {active.get('quota_gap')}",
        "",
        "## Reconciled Profile Summary",
        "",
        f"- Role audit score: {reconciled.get('role_audit_score')}",
        f"- Readiness: `{reconciled.get('readiness_classification')}`",
        f"- Role conflicts: {reconciled.get('role_conflicts')}",
        f"- Quota gap: {reconciled.get('quota_gap')}",
        f"- Quota gap delta vs generic: {reconciled.get('quota_gap_delta_vs_generic')}",
        f"- Worsened core roles: {', '.join(reconciled.get('worsened_core_roles', [])) or 'none'}",
        "",
        "## Proposed Role Updates",
        "",
    ]
    updates = reconciled.get("proposed_role_updates", {})
    if updates:
        for card, update in updates.items():
            lines.append(f"- `{card}`: {', '.join(update.get('from', []))} -> {', '.join(update.get('to', []))}")
    else:
        lines.append("- None")
    lines.extend(["", "## Activation Safety Gates", ""])
    for gate, passed in comparison.get("activation_safety_gates", {}).items():
        lines.append(f"- `{gate}`: {passed}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare generic Kashtira builds against a non-activated reconciled role map.")
    parser.add_argument("--archetype", default="Kashtira")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode, args.runs)
    json_path, md_path = save_report(report)
    comparison = report["comparison"]
    print("Semi-Specialization Reconciled Comparison Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Not activated: {comparison['not_activated']}")
    print(f"Activation recommendation: {comparison['activation_recommendation']}")
    print(f"Generic gap: {comparison['generic_summary'].get('generic_total_gap')}")
    print(f"Reconciled projected gap: {comparison['reconciled_profile_summary'].get('quota_gap')}")
    print(f"Reconciled audit score: {comparison['reconciled_profile_summary'].get('role_audit_score')}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
