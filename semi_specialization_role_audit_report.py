from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.semi_specialized_role_audit import audit_specialized_roles
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def build_report(archetype: str, mode: str) -> dict[str, Any]:
    audit = audit_specialized_roles(archetype, mode)
    return {
        "report_type": "semi_specialization_role_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "semi_specialization_activated": False,
        "audit": audit,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_role_audit_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_role_audit_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    audit = report["audit"]
    lines = [
        f"# {report['archetype']} Role Classification Audit",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Not activated: {audit['not_activated']}",
        f"- Role agreement score: {audit['role_agreement_score']}",
        f"- Readiness classification: `{audit['readiness_classification']}`",
        "",
        "## Confirmed Roles",
        "",
    ]
    for role, names in audit.get("confirmed_roles", {}).items():
        lines.append(f"- `{role}`: {', '.join(names) if names else 'none'}")
    if not audit.get("confirmed_roles"):
        lines.append("- None")
    lines.extend(["", "## Role Conflicts", ""])
    conflicts = audit.get("role_conflicts", [])
    if conflicts:
        for row in conflicts:
            lines.append(f"- `{row.get('card')}` as `{row.get('profile_role')}` [{row.get('severity')}]: {row.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Low Confidence Assignments", ""])
    lows = audit.get("low_confidence_assignments", [])
    if lows:
        for row in lows:
            lines.append(f"- `{row.get('card')}` as `{row.get('profile_role')}`: {row.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Needs Manual Review", ""])
    review = audit.get("needs_manual_review", [])
    if review:
        for row in review:
            lines.append(f"- `{row.get('card', 'unknown')}` as `{row.get('profile_role', 'unknown')}`: {row.get('reason')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Risk Flags", ""])
    lines.extend(f"- {flag}" for flag in audit.get("risk_flags", [])) if audit.get("risk_flags") else lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit non-activated semi-specialization role classifications.")
    parser.add_argument("--archetype", default="Kashtira")
    parser.add_argument("--mode", default="meta")
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode)
    json_path, md_path = save_report(report)
    audit = report["audit"]
    print("Semi-Specialization Role Audit Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Not activated: {audit['not_activated']}")
    print(f"Role agreement score: {audit['role_agreement_score']}")
    print(f"Readiness classification: {audit['readiness_classification']}")
    print(f"Conflicts: {len(audit.get('role_conflicts', []))}")
    print(f"Low-confidence assignments: {len(audit.get('low_confidence_assignments', []))}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
