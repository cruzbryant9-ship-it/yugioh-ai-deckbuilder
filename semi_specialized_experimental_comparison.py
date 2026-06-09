from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.deck_utils import blocked_card_violations
from deck.executed_dependency_telemetry import (
    build_dependency_telemetry,
    compare_dependency_summaries,
    dependency_gate_status,
    promotion_safety_gates,
    summarize_dependency_telemetry,
)
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def run_experimental_comparison(archetype: str = "Kashtira", mode: str = "meta", runs: int = 5) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    run_rows = []
    for index in range(max(1, int(runs or 1))):
        generic_deck, _pool = build_deck(cards, archetype, mode=mode)
        generic_report = get_last_build_report()
        experimental_deck, _pool = build_deck(
            cards,
            archetype,
            mode=mode,
            experimental_semi_specialized=True,
            specialization_profile=archetype,
        )
        experimental_report = get_last_build_report()
        run_rows.append(
            {
                "run": index + 1,
                "generic": deck_result(generic_deck, generic_report, archetype, mode),
                "experimental": deck_result(experimental_deck, experimental_report, archetype, mode),
            }
        )
    generic_summary = summarize_runs(run_rows, "generic")
    experimental_summary = summarize_runs(run_rows, "experimental")
    safety = promotion_safety_gates(generic_summary["dependency_telemetry"], experimental_summary["dependency_telemetry"])
    regression = regression_recommendation(generic_summary, experimental_summary, safety)
    return {
        "archetype": archetype,
        "mode": mode,
        "runs": max(1, int(runs or 1)),
        "generic_summary": generic_summary,
        "experimental_summary": experimental_summary,
        "generic_dependency": generic_summary["dependency_telemetry"],
        "experimental_dependency": experimental_summary["dependency_telemetry"],
        "dependency_delta": compare_dependency_summaries(generic_summary["dependency_telemetry"], experimental_summary["dependency_telemetry"]),
        "dependency_gate_status": dependency_gate_status(generic_summary["dependency_telemetry"], experimental_summary["dependency_telemetry"]),
        "generic_fill_gate": safety["generic_fill_gate"],
        "interaction_loss_gate": safety["interaction_loss_gate"],
        "promotion_blocking_reasons": safety["promotion_blocking_reasons"],
        "lost_interaction_cards": safety["lost_interaction_cards"],
        "fallback_rate": experimental_summary.get("fallback_rate", 0.0),
        "regression_recommendation": regression,
        "run_results": run_rows,
        "not_activated_default": True,
    }


def deck_result(deck: list[dict[str, Any]], report: dict[str, Any], archetype: str, mode: str) -> dict[str, Any]:
    score = score_deck_breakdown(deck, archetype, mode)
    return {
        "builder_used": report.get("builder_used"),
        "experimental": bool(report.get("experimental", False)),
        "not_default": bool(report.get("not_default", False)),
        "fallback_used": bool(report.get("fallback_used", False)),
        "score": score.get("final_score", 0),
        "package_counts": report.get("package_counts", {}),
        "main_deck_count": report.get("main_deck_count"),
        "extra_deck_count": report.get("extra_deck_count"),
        "filler_dependency": float(report.get("safe_filler_used_count", 0) or 0),
        "repair_dependency": float(report.get("repair_action_count", 0) or 0),
        "dependency_telemetry": build_dependency_telemetry(deck, report, archetype),
        "blocked_card_violations": blocked_card_violations(deck),
        "quota_warnings": report.get("quota_warnings", []),
        "legality_ok": len(blocked_card_violations(deck)) == 0 and int(report.get("main_deck_count", 0) or 0) >= 40,
    }


def summarize_runs(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    package_totals: Counter[str] = Counter()
    dependency_summary = summarize_dependency_telemetry(selected)
    for row in selected:
        package_totals.update({name: float(value or 0) for name, value in (row.get("package_counts", {}) or {}).items()})
    return {
        "average_score": round(mean(float(row.get("score", 0) or 0) for row in selected), 4),
        "best_score": max(float(row.get("score", 0) or 0) for row in selected),
        "average_package_counts": {name: round(value / max(1, len(selected)), 4) for name, value in sorted(package_totals.items())},
        "legality_ok_rate": round(mean(1.0 if row.get("legality_ok") else 0.0 for row in selected), 4),
        "fallback_rate": round(mean(1.0 if row.get("fallback_used") else 0.0 for row in selected), 4),
        "filler_dependency": round(mean(float(row.get("filler_dependency", 0) or 0) for row in selected), 4),
        "repair_dependency": round(mean(float(row.get("repair_dependency", 0) or 0) for row in selected), 4),
        "safe_filler_used_count": dependency_summary["safe_filler_used_count"],
        "repair_used": dependency_summary["repair_used"],
        "repair_success": dependency_summary["repair_success"],
        "repair_action_count": dependency_summary["repair_action_count"],
        "repair_dependency_score": dependency_summary["repair_dependency_score"],
        "filler_dependency_score": dependency_summary["filler_dependency_score"],
        "dependency_telemetry": dependency_summary,
        "blocked_card_violations": sorted(set(name for row in selected for name in row.get("blocked_card_violations", []))),
        "builders_used": sorted(set(str(row.get("builder_used")) for row in selected)),
    }


def regression_recommendation(generic: dict[str, Any], experimental: dict[str, Any], safety: dict[str, Any] | None = None) -> str:
    if safety and safety.get("promotion_blocked"):
        return "do_not_promote_safety_gate"
    if experimental.get("blocked_card_violations") or experimental.get("legality_ok_rate", 0) < 1.0:
        return "do_not_promote_legality_risk"
    if experimental.get("fallback_rate", 1) > 0:
        return "watch_fallbacks_before_promotion"
    if float(experimental.get("average_score", 0) or 0) + 0.001 < float(generic.get("average_score", 0) or 0):
        return "do_not_promote_score_regression"
    return "eligible_for_limited_experimental_testing"


def build_report(archetype: str, mode: str, runs: int) -> dict[str, Any]:
    comparison = run_experimental_comparison(archetype, mode, runs)
    return {
        "report_type": "semi_specialized_experimental_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "semi_specialization_default_active": False,
        "comparison": comparison,
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_experimental_comparison_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_experimental_comparison_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    generic = comparison["generic_summary"]
    experimental = comparison["experimental_summary"]
    lines = [
        f"# {report['archetype']} Experimental Semi-Specialized Comparison",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Default active: {report['semi_specialization_default_active']}",
        f"- Regression recommendation: `{comparison['regression_recommendation']}`",
        f"- Fallback rate: {comparison['fallback_rate']}",
        "",
        "## Generic Summary",
        "",
        f"- Average score: {generic['average_score']}",
        f"- Best score: {generic['best_score']}",
        f"- Legality OK rate: {generic['legality_ok_rate']}",
        f"- Filler dependency: {generic['filler_dependency']}",
        f"- Repair dependency: {generic['repair_dependency']}",
        f"- Filler dependency score: {generic['dependency_telemetry']['filler_dependency_score']}",
        f"- Repair dependency score: {generic['dependency_telemetry']['repair_dependency_score']}",
        "",
        "## Experimental Summary",
        "",
        f"- Average score: {experimental['average_score']}",
        f"- Best score: {experimental['best_score']}",
        f"- Legality OK rate: {experimental['legality_ok_rate']}",
        f"- Fallback rate: {experimental['fallback_rate']}",
        f"- Filler dependency: {experimental['filler_dependency']}",
        f"- Repair dependency: {experimental['repair_dependency']}",
        f"- Filler dependency score: {experimental['dependency_telemetry']['filler_dependency_score']}",
        f"- Repair dependency score: {experimental['dependency_telemetry']['repair_dependency_score']}",
        f"- Builders used: {', '.join(experimental['builders_used'])}",
        "",
        "## Dependency Gate Status",
        "",
        f"- {comparison['dependency_gate_status']}",
        "",
        "## Promotion Safety Gates",
        "",
        f"- Generic-fill gate: {comparison['generic_fill_gate']}",
        f"- Interaction-loss gate: {comparison['interaction_loss_gate']}",
        f"- Promotion blocking reasons: {comparison['promotion_blocking_reasons']}",
        f"- Lost interaction cards: {comparison['lost_interaction_cards']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare generic and explicit experimental Kashtira semi-specialized builds.")
    parser.add_argument("--archetype", default="Kashtira")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    report = build_report(args.archetype, args.mode, args.runs)
    json_path, md_path = save_report(report)
    comparison = report["comparison"]
    print("Experimental Semi-Specialized Comparison Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Default active: {report['semi_specialization_default_active']}")
    print(f"Generic average score: {comparison['generic_summary']['average_score']}")
    print(f"Experimental average score: {comparison['experimental_summary']['average_score']}")
    print(f"Fallback rate: {comparison['fallback_rate']}")
    print(f"Regression recommendation: {comparison['regression_recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
