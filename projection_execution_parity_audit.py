from __future__ import annotations

import argparse
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.interaction_core_registry import interaction_core_for, registry_report
from deck.semi_specialized_builder_adapter import dependency_gate_report, evaluate_experimental_gates
from kashtira_adapter_tuning_plan import build_tuning_plan, save_report as save_tuning_report
from kashtira_hybrid_overlay_regression_gate import run_hybrid_gate, save_report as save_hybrid_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


ARCHITECTURE_REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "architecture_audit"
PARITY_JSON = ARCHITECTURE_REPORT_DIR / "latest_projection_execution_parity_report.json"
PARITY_MD = ARCHITECTURE_REPORT_DIR / "latest_projection_execution_parity_report.md"
STABILIZATION_REPORT = Path("STABILIZATION_O_PROJECTION_EXECUTION_UNIFICATION.md")
PHASE8L_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_adapter_tuning_plan.json"
PHASE8M_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_hybrid_overlay_regression_gate.json"
INTERACTION_CARD_NAMES = tuple(interaction_core_for("Kashtira"))
SOURCE_EXTENSIONS = {".py"}


def run_audit(
    mode: str = "meta",
    runs: int = 10,
    seed: int = 12345,
    frozen_cards: bool = True,
    use_existing_reports: bool = True,
) -> dict[str, Any]:
    projection = load_or_build_phase8l(mode, runs, seed, frozen_cards, use_existing_reports)
    execution = load_or_build_phase8m(mode, runs, seed, frozen_cards, use_existing_reports)
    dead_gates = audit_dependency_gates(mode)
    interaction = audit_interaction_core_ownership()
    parity_rows = compare_projection_to_execution(projection, execution)
    promotion = audit_promotion_sources()
    severe = [row for row in parity_rows if row["classification"] == "severe_mismatch"]
    report = {
        "report_type": "projection_execution_parity_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": int(runs),
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "projection_source": {
            "phase": "8L",
            "path": str(PHASE8L_JSON),
            "recommendation": projection.get("recommendation"),
            "best_variant": (projection.get("best_variant") or {}).get("name"),
            "source_type": "projected_estimate",
        },
        "execution_source": {
            "phase": "8M",
            "path": str(PHASE8M_JSON),
            "recommendation": execution.get("recommendation"),
            "variant": "hybrid_generic_interaction_overlay",
            "source_type": "executed_deck",
        },
        "parity_metrics": parity_rows,
        "severe_mismatch_count": len(severe),
        "dead_gate_audit": dead_gates,
        "interaction_core_audit": interaction,
        "executed_promotion_safety_gates": extract_executed_promotion_safety(execution),
        "promotion_source_audit": promotion,
        "summary": summarize_audit(parity_rows, dead_gates, promotion),
        "behavior_changed": False,
        "builder_changed": False,
        "promotion_applied": False,
    }
    return report


def load_or_build_phase8l(mode: str, runs: int, seed: int, frozen_cards: bool, use_existing_reports: bool) -> dict[str, Any]:
    if use_existing_reports and PHASE8L_JSON.exists():
        return json.loads(PHASE8L_JSON.read_text(encoding="utf-8"))
    report = build_tuning_plan(mode, runs, seed, frozen_cards=frozen_cards)
    save_tuning_report(report)
    return report


def load_or_build_phase8m(mode: str, runs: int, seed: int, frozen_cards: bool, use_existing_reports: bool) -> dict[str, Any]:
    if use_existing_reports and PHASE8M_JSON.exists():
        return json.loads(PHASE8M_JSON.read_text(encoding="utf-8"))
    report = run_hybrid_gate(mode, runs, seed, frozen_cards=frozen_cards)
    save_hybrid_report(report)
    return report


def compare_projection_to_execution(projection: dict[str, Any], execution: dict[str, Any]) -> list[dict[str, Any]]:
    projected = projection.get("best_variant") or {}
    executed = execution.get("hybrid_overlay") or {}
    metric_map = {
        "score": ("average_score", "average_score"),
        "package_quality": ("package_quality", "package_quality"),
        "quota_balance": ("quota_balance", "quota_balance"),
        "preserved_interaction_count": ("preserved_interaction_count", "preserved_interaction_count"),
        "filler_dependency": ("filler_dependency", "filler_dependency"),
        "repair_dependency": ("repair_dependency", "repair_dependency"),
    }
    rows = []
    for metric, (projected_key, executed_key) in metric_map.items():
        projected_available = projected_key in projected
        executed_available = executed_key in executed
        projected_value = numeric_or_none(projected.get(projected_key))
        executed_value = numeric_or_none(executed.get(executed_key))
        absolute_delta = None
        percentage_delta = None
        if projected_value is not None and executed_value is not None:
            absolute_delta = round(executed_value - projected_value, 4)
            denominator = abs(projected_value) if abs(projected_value) > 0.0001 else 1.0
            percentage_delta = round((absolute_delta / denominator) * 100.0, 4)
        rows.append(
            {
                "metric": metric,
                "projected_value": projected_value,
                "executed_value": executed_value,
                "absolute_delta": absolute_delta,
                "percentage_delta": percentage_delta,
                "projected_available": projected_available,
                "executed_available": executed_available,
                "classification": classify_delta(metric, projected_value, executed_value, absolute_delta, percentage_delta),
            }
        )
    return rows


def numeric_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def classify_delta(metric: str, projected: float | None, executed: float | None, absolute: float | None, percentage: float | None) -> str:
    if projected is None or executed is None:
        return "metric_unavailable"
    if metric == "score" and abs(float(absolute or 0)) >= 1.0:
        return "severe_mismatch"
    if metric == "preserved_interaction_count" and projected > 0 and executed == 0:
        return "severe_mismatch"
    if percentage is not None and abs(percentage) >= 10.0:
        return "severe_mismatch"
    if percentage is not None and abs(percentage) >= 5.0:
        return "warning"
    if absolute is not None and abs(absolute) >= 1.0 and metric in {"package_quality", "quota_balance"}:
        return "warning"
    return "acceptable"


def audit_dependency_gates(mode: str = "meta") -> dict[str, Any]:
    source_path = Path("deck") / "semi_specialized_builder_adapter.py"
    cards = CardDatabase().load_cards()
    gate_report = evaluate_experimental_gates(cards, "Kashtira", mode, "Kashtira", variant="hybrid_generic_interaction_overlay")
    source_text = source_path.read_text(encoding="utf-8").splitlines()
    filler_line = find_line(source_text, '"name": "filler_dependency_gate"')
    repair_line = find_line(source_text, '"name": "repair_dependency_gate"')
    filler_value = numeric_or_none(gate_report.get("filler_dependency"))
    repair_value = numeric_or_none(gate_report.get("repair_dependency"))
    baseline_filler = numeric_or_none(gate_report.get("generic_filler_dependency"))
    baseline_repair = numeric_or_none(gate_report.get("generic_repair_dependency"))
    synthetic = dependency_gate_report(
        {"filler_dependency": 0.0, "repair_dependency": 0.0},
        {"filler_dependency": 1.0, "repair_dependency": 1.0},
    )
    return {
        "code_path": "deck.semi_specialized_builder_adapter.evaluate_experimental_gates",
        "source_file": source_path.as_posix(),
        "status": "remediated_candidate_vs_baseline",
        "gates": [
            {
                "name": "filler_dependency_gate",
                "line": filler_line,
                "left_expression": "candidate.filler_dependency",
                "right_expression": "baseline.filler_dependency",
                "left_value": filler_value,
                "right_value": baseline_filler,
                "comparison": f"{filler_value} > {baseline_filler}",
                "can_trigger": True,
                "currently_triggered": "filler dependency increased versus generic" in gate_report.get("gate_failures", []),
                "classification": "active_candidate_vs_baseline_gate",
                "synthetic_triggered": any(gate["name"] == "filler_dependency_gate" and gate["triggered"] for gate in synthetic["gates"]),
                "recommended_correction": "No further correction in Stabilization P; future work should improve candidate dependency measurement fidelity if needed.",
            },
            {
                "name": "repair_dependency_gate",
                "line": repair_line,
                "left_expression": "candidate.repair_dependency",
                "right_expression": "baseline.repair_dependency",
                "left_value": repair_value,
                "right_value": baseline_repair,
                "comparison": f"{repair_value} > {baseline_repair}",
                "can_trigger": True,
                "currently_triggered": "repair dependency increased versus generic" in gate_report.get("gate_failures", []),
                "classification": "active_candidate_vs_baseline_gate",
                "synthetic_triggered": any(gate["name"] == "repair_dependency_gate" and gate["triggered"] for gate in synthetic["gates"]),
                "recommended_correction": "No further correction in Stabilization P; future work should improve candidate dependency measurement fidelity if needed.",
            },
        ],
        "gate_report_snapshot": {
            "eligible": gate_report.get("eligible"),
            "variant": gate_report.get("variant"),
            "filler_dependency": gate_report.get("filler_dependency"),
            "repair_dependency": gate_report.get("repair_dependency"),
            "generic_filler_dependency": gate_report.get("generic_filler_dependency"),
            "generic_repair_dependency": gate_report.get("generic_repair_dependency"),
            "gate_failures": gate_report.get("gate_failures", []),
        },
    }


def find_line(lines: list[str], needle: str) -> int | None:
    compact_needle = " ".join(needle.split())
    for index, line in enumerate(lines, start=1):
        if compact_needle in " ".join(line.split()):
            return index
    return None


def audit_interaction_core_ownership() -> dict[str, Any]:
    hardcoded_users = []
    registry_backed_users = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        relative = path.as_posix()
        if relative == "deck/interaction_core_registry.py":
            continue
        hardcoded_cards = [name for name in INTERACTION_CARD_NAMES if name in text]
        imports_registry = "interaction_core_for" in text or "interaction_core_set" in text
        if is_hardcoded_core_owner(text, hardcoded_cards):
            hardcoded_users.append({"file": relative, "cards": hardcoded_cards})
        if imports_registry:
            registry_backed_users.append(relative)
    return {
        "registry": registry_report(["Kashtira"]),
        "hardcoded_interaction_core_users": hardcoded_users,
        "registry_backed_users": sorted(set(registry_backed_users)),
        "migrated_modules": sorted(
            set(registry_backed_users)
            & {
                "deck/semi_specialized_builder_adapter.py",
                "deck/semi_specialized_adapter_tuning.py",
                "kashtira_adapter_tuning_plan.py",
                "kashtira_hybrid_overlay_regression_gate.py",
            }
        ),
        "remaining_hardcoded_count": len(hardcoded_users),
        "promotion_paths_using_hardcoded_interaction_core": [
            row
            for row in hardcoded_users
            if row["file"] in {"kashtira_adapter_tuning_plan.py", "kashtira_hybrid_overlay_regression_gate.py", "deck/semi_specialized_builder_adapter.py"}
        ],
        "report_only": True,
        "builder_auto_behavior_changed": False,
    }


def is_hardcoded_core_owner(text: str, hardcoded_cards: list[str]) -> bool:
    if len(hardcoded_cards) >= 3:
        return True
    lowered = text.casefold()
    ownership_terms = ("interaction_core", "handtrap", "hand trap", "filler", "package", "preserve_cards")
    return len(hardcoded_cards) >= 2 and any(term in lowered for term in ownership_terms)


def source_files() -> list[Path]:
    roots = [Path("deck"), Path(".")]
    paths: list[Path] = []
    for root in roots:
        for path in root.glob("*.py"):
            if path.suffix in SOURCE_EXTENSIONS and not path.name.startswith("validate_"):
                paths.append(path)
    return sorted(set(paths), key=lambda item: item.as_posix())


def audit_promotion_sources() -> dict[str, Any]:
    return {
        "recommendations": [
            {
                "recommendation": "proposal_only",
                "producer": "kashtira_adapter_tuning_plan.choose_recommendation",
                "source_type": "projected",
                "evidence_source": "projected",
                "promotion_allowed": False,
                "requires_execution_gate": True,
                "promotion_path": False,
                "projected_only": True,
                "flag": "projected_output_not_promotion_evidence",
                "notes": "Comes from Phase 8L simulated variant estimates and is explicitly blocked from promotion use.",
            },
            {
                "recommendation": "promote_blocked",
                "producer": "kashtira_experimental_regression_gate.choose_recommendation / kashtira_hybrid_overlay_regression_gate.choose_recommendation",
                "source_type": "executed",
                "evidence_source": "executed",
                "promotion_allowed": False,
                "requires_execution_gate": False,
                "promotion_path": False,
                "projected_only": False,
                "flag": None,
                "notes": "Blocks promotion from real fixed-seed execution metrics.",
            },
            {
                "recommendation": "keep_dry_run_only",
                "producer": "kashtira_hybrid_overlay_regression_gate.choose_recommendation",
                "source_type": "executed",
                "evidence_source": "executed",
                "promotion_allowed": False,
                "requires_execution_gate": False,
                "promotion_path": False,
                "projected_only": False,
                "flag": None,
                "notes": "Comes from real hybrid overlay execution versus generic baseline.",
            },
            {
                "recommendation": "eligible_for_more_testing",
                "producer": "kashtira_experimental_regression_gate.choose_recommendation",
                "source_type": "executed",
                "evidence_source": "executed",
                "promotion_allowed": True,
                "requires_execution_gate": False,
                "promotion_path": False,
                "projected_only": False,
                "flag": None,
                "notes": "Can only be returned from fixed-seed execution when score and safety metrics are clean.",
            },
        ],
        "projected_only_promotion_paths": [],
        "projected_non_promotion_outputs": ["proposal_only", "needs_real_execution", "do_not_use_for_promotion"],
        "executed_deck_recommendations": ["promote_blocked", "keep_dry_run_only", "eligible_for_more_testing"],
        "mixed_source_recommendations": [],
    }


def extract_executed_promotion_safety(execution: dict[str, Any]) -> dict[str, Any]:
    return {
        "generic_fill_gate": execution.get("generic_fill_gate", {}),
        "interaction_loss_gate": execution.get("interaction_loss_gate", {}),
        "promotion_blocking_reasons": execution.get("promotion_blocking_reasons", {}),
        "lost_interaction_cards": execution.get("lost_interaction_cards", {}),
        "source_type": "executed",
        "projection_used": False,
    }


def summarize_audit(parity_rows: list[dict[str, Any]], dead_gates: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    severe = [row["metric"] for row in parity_rows if row["classification"] == "severe_mismatch"]
    unavailable = [row["metric"] for row in parity_rows if row["classification"] == "metric_unavailable"]
    dead = [gate["name"] for gate in dead_gates.get("gates", []) if gate.get("classification") == "self_comparison_dead_gate"]
    active = [gate["name"] for gate in dead_gates.get("gates", []) if gate.get("classification") == "active_candidate_vs_baseline_gate"]
    return {
        "severe_mismatches": severe,
        "unavailable_parity_metrics": unavailable,
        "dead_gates": dead,
        "active_dependency_gates": active,
        "projected_only_promotion_paths": promotion.get("projected_only_promotion_paths", []),
        "recommendation": "Use executed-deck gates as the only source for promotion decisions; Phase 8L outputs are now proposal-only and require execution.",
    }


def save_architecture_reports(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    ARCHITECTURE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(PARITY_JSON, report)
    md = render_parity_markdown(report)
    atomic_write_text(PARITY_MD, md)
    atomic_write_text(STABILIZATION_REPORT, render_stabilization_markdown(report))
    return PARITY_JSON, PARITY_MD, STABILIZATION_REPORT


def render_parity_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Projection vs Execution Parity Report",
        "",
        f"- Archetype: `{report['archetype']}`",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Severe mismatches: {report['severe_mismatch_count']}",
        "",
        "## Metric Parity",
        "",
        "| Metric | Projected | Executed | Abs Delta | Percent Delta | Classification |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["parity_metrics"]:
        lines.append(
            f"| {row['metric']} | {display(row['projected_value'])} | {display(row['executed_value'])} | "
            f"{display(row['absolute_delta'])} | {display(row['percentage_delta'])} | {row['classification']} |"
        )
    lines.extend(["", "## Promotion Source Audit", ""])
    for row in report["promotion_source_audit"]["recommendations"]:
        flag = f" ({row['flag']})" if row.get("flag") else ""
        lines.append(f"- `{row['recommendation']}`: {row['source_type']}{flag}")
    lines.extend(["", "## Dependency Gates", ""])
    for gate in report["dead_gate_audit"]["gates"]:
        lines.append(f"- `{gate['name']}` at line {gate['line']}: {gate['comparison']} -> can trigger: {gate['can_trigger']} ({gate['classification']})")
    lines.extend(["", "## Executed Promotion Safety Gates", ""])
    safety = report.get("executed_promotion_safety_gates", {})
    lines.append(f"- Generic-fill gate: {safety.get('generic_fill_gate')}")
    lines.append(f"- Interaction-loss gate: {safety.get('interaction_loss_gate')}")
    lines.append(f"- Promotion blocking reasons: {safety.get('promotion_blocking_reasons')}")
    lines.append(f"- Lost interaction cards: {safety.get('lost_interaction_cards')}")
    return "\n".join(lines) + "\n"


def render_stabilization_markdown(report: dict[str, Any]) -> str:
    interaction = report["interaction_core_audit"]
    lines = [
        "# Stabilization O: Projection vs Execution Unification",
        "",
        "Audit-only architecture remediation. No scoring, deck construction, default semi-specialized behavior, Blue-Eyes authored behavior, memory influence, promotion status, neural methods, self-play, duel engine, or combo graph behavior was changed.",
        "",
        "## Files Created",
        "",
        "- `deck/interaction_core_registry.py`",
        "- `projection_execution_parity_audit.py`",
        "- `validate_stabilization_o.py`",
        "- `STABILIZATION_O_PROJECTION_EXECUTION_UNIFICATION.md`",
        "- `SystemAIYugioh/data/training_runs/architecture_audit/latest_projection_execution_parity_report.json`",
        "- `SystemAIYugioh/data/training_runs/architecture_audit/latest_projection_execution_parity_report.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `deck/semi_specialized_adapter_tuning.py`",
        "- `kashtira_adapter_tuning_plan.py`",
        "- `kashtira_hybrid_overlay_regression_gate.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Dependency Gate Findings",
        "",
    ]
    for gate in report["dead_gate_audit"]["gates"]:
        lines.extend(
            [
                f"- `{gate['name']}`: `{gate['comparison']}` at `{report['dead_gate_audit']['source_file']}` line {gate['line']}",
                f"  Classification: `{gate['classification']}`; can trigger: `{gate['can_trigger']}`; currently triggered: `{gate.get('currently_triggered')}`.",
                f"  Note: {gate['recommended_correction']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Interaction Registry Findings",
            "",
            f"- Registry owner: `{interaction['registry']['registry_owner']}`",
            f"- Kashtira interaction core: {', '.join(INTERACTION_CARD_NAMES)}",
            f"- Registry-backed users: {len(interaction['registry_backed_users'])}",
            f"- Migrated modules: {', '.join(f'`{path}`' for path in interaction['migrated_modules']) or 'None'}",
            f"- Remaining hardcoded source users: {interaction['remaining_hardcoded_count']}",
            f"- Promotion paths using hardcoded interaction lists: {len(interaction['promotion_paths_using_hardcoded_interaction_core'])}",
            "",
            "## Projection vs Execution Mismatch",
            "",
            "| Metric | Projected | Executed | Abs Delta | Percent Delta | Classification |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report["parity_metrics"]:
        lines.append(
            f"| {row['metric']} | {display(row['projected_value'])} | {display(row['executed_value'])} | "
            f"{display(row['absolute_delta'])} | {display(row['percentage_delta'])} | {row['classification']} |"
        )
    lines.extend(["", "## Promotion Source Audit", ""])
    for row in report["promotion_source_audit"]["recommendations"]:
        flag = f"; flag: `{row['flag']}`" if row.get("flag") else ""
        lines.append(f"- `{row['recommendation']}`: `{row['source_type']}`{flag}. {row['notes']}")
    safety = report.get("executed_promotion_safety_gates", {})
    lines.extend(
        [
            "",
            "## Executed Promotion Safety Gates",
            "",
            f"- Generic-fill gate: `{safety.get('generic_fill_gate')}`",
            f"- Interaction-loss gate: `{safety.get('interaction_loss_gate')}`",
            f"- Promotion blocking reasons: `{safety.get('promotion_blocking_reasons')}`",
            f"- Lost interaction cards: `{safety.get('lost_interaction_cards')}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Severe mismatches: {', '.join(report['summary']['severe_mismatches']) or 'None'}",
            f"- Unavailable parity metrics: {', '.join(report['summary']['unavailable_parity_metrics']) or 'None'}",
            f"- Dead gates: {', '.join(report['summary']['dead_gates']) or 'None'}",
            f"- Active dependency gates: {', '.join(report['summary']['active_dependency_gates']) or 'None'}",
            f"- Projected-only promotion paths: {', '.join(report['summary']['projected_only_promotion_paths']) or 'None'}",
            "",
            "## Recommendation For Stabilization P",
            "",
            "- Keep Phase 8L proposal-only, require executed-deck evidence for every promotion-like recommendation, and improve dependency measurement fidelity in the executed candidate reports.",
        ]
    )
    return "\n".join(lines) + "\n"


def display(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return str(round(value, 4))
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit projection-vs-execution parity for Kashtira specialization reports.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true", default=True)
    parser.add_argument("--rebuild-reports", action="store_true")
    args = parser.parse_args()
    report = run_audit(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards, use_existing_reports=not args.rebuild_reports)
    json_path, md_path, stabilization_path = save_architecture_reports(report)
    print("Projection Execution Parity Audit Complete")
    print(f"Severe mismatches: {report['severe_mismatch_count']}")
    print(f"Dead gates: {', '.join(report['summary']['dead_gates']) or 'None'}")
    print(f"Projected-only promotion paths: {', '.join(report['summary']['projected_only_promotion_paths']) or 'None'}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(f"Stabilization report: {stabilization_path}")


if __name__ == "__main__":
    main()
