from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report, score_deck_breakdown
from deck.semi_specialized_package_planner import build_semi_specialized_package_plan
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization"


def run_pilot_report(archetype: str, mode: str = "meta", runs: int = 3) -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    plan = build_semi_specialized_package_plan(archetype, mode, cards)
    generic_runs = [run_generic_probe(cards, archetype, mode, index + 1) for index in range(max(1, runs))]
    comparison = compare_generic_to_plan(generic_runs, plan)
    return {
        "report_type": "semi_specialization_pilot",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": archetype,
        "mode": mode,
        "runs": runs,
        "semi_specialization_activated": False,
        "plan": plan,
        "generic_runs": generic_runs,
        "comparison": comparison,
    }


def run_generic_probe(cards: list[dict[str, Any]], archetype: str, mode: str, run_id: int) -> dict[str, Any]:
    deck, pool = build_deck(cards, archetype, mode=mode, use_learning=True, generic_tune_runs=0)
    build_report = dict(get_last_build_report())
    score = score_deck_breakdown(deck, archetype, mode) if deck else {"final_score": 0}
    return {
        "run": run_id,
        "builder_used": build_report.get("builder_used"),
        "deck_size": len(deck),
        "archetype_pool_size": len(pool),
        "final_score": score.get("final_score", 0),
        "generic_confidence_score": build_report.get("generic_confidence_score", 0),
        "package_counts": build_report.get("package_counts", {}),
        "ratio_profile": build_report.get("ratio_profile", {}),
        "quota_warnings": build_report.get("quota_warnings", []),
        "repair_used": build_report.get("repair_used", False),
        "repair_success": build_report.get("repair_success"),
        "repair_action_count": build_report.get("repair_action_count", 0),
        "safe_filler_used_count": build_report.get("safe_filler_used_count", 0),
        "contextual_filler_used": build_report.get("contextual_filler_used", False),
        "main_deck": [str(card.get("name", "")) for card in deck if not is_extra_deck_card(card)],
        "extra_deck": [str(card.get("name", "")) for card in deck if is_extra_deck_card(card)],
    }


def compare_generic_to_plan(generic_runs: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    quota_targets = plan.get("quota_targets", {}) if isinstance(plan.get("quota_targets"), dict) else {}
    avg_package_counts = average_package_counts(generic_runs)
    quota_alignment = {}
    for role, target in quota_targets.items():
        observed = avg_package_counts.get(role, 0.0)
        quota_alignment[role] = {
            "target": target,
            "average_generic_observed": round(observed, 4),
            "delta_from_target": round(observed - float(target or 0), 4),
        }
    filler_counts = [float(run.get("safe_filler_used_count", 0) or 0) for run in generic_runs]
    repair_counts = [float(run.get("repair_action_count", 0) or 0) for run in generic_runs]
    warnings = [warning for run in generic_runs for warning in run.get("quota_warnings", []) or []]
    expected_risk_improvement = expected_risk_improvement_summary(quota_alignment, warnings, filler_counts, repair_counts)
    return {
        "generic_builder_still_used": all(run.get("builder_used") in {"generic", "generic_tuned"} for run in generic_runs),
        "average_generic_score": round(mean(float(run.get("final_score", 0) or 0) for run in generic_runs), 4),
        "average_generic_confidence": round(mean(float(run.get("generic_confidence_score", 0) or 0) for run in generic_runs), 4),
        "legality_readiness": {
            "average_deck_size": round(mean(float(run.get("deck_size", 0) or 0) for run in generic_runs), 4),
            "all_decks_40_plus": all(int(run.get("deck_size", 0) or 0) >= 40 for run in generic_runs),
            "repair_success_rate": round(mean(1.0 if run.get("repair_success", True) else 0.0 for run in generic_runs), 4),
        },
        "quota_stability": {
            "average_package_counts": avg_package_counts,
            "quota_alignment": quota_alignment,
            "quota_warning_count": len(warnings),
            "common_quota_warnings": Counter(warnings).most_common(10),
        },
        "filler_dependency": {
            "average_safe_filler_used_count": round(mean(filler_counts), 4),
            "contextual_filler_run_count": sum(1 for run in generic_runs if run.get("contextual_filler_used")),
        },
        "repair_dependency": {
            "average_repair_action_count": round(mean(repair_counts), 4),
            "repair_used_run_count": sum(1 for run in generic_runs if run.get("repair_used")),
        },
        "expected_risk_improvement": expected_risk_improvement,
        "not_activated": True,
    }


def average_package_counts(generic_runs: list[dict[str, Any]]) -> dict[str, float]:
    totals: Counter[str] = Counter()
    for run in generic_runs:
        for role, count in (run.get("package_counts", {}) or {}).items():
            totals[str(role)] += float(count or 0)
    return {role: round(total / max(1, len(generic_runs)), 4) for role, total in sorted(totals.items())}


def expected_risk_improvement_summary(
    quota_alignment: dict[str, dict[str, Any]],
    warnings: list[str],
    filler_counts: list[float],
    repair_counts: list[float],
) -> dict[str, Any]:
    improvement_flags = []
    if quota_alignment.get("max_bricks", {}).get("average_generic_observed", 0) > quota_alignment.get("max_bricks", {}).get("target", 99):
        improvement_flags.append("profile brick cap may reduce brick pressure")
    if quota_alignment.get("starters_searchers", {}).get("average_generic_observed", 0) < quota_alignment.get("starters_searchers", {}).get("target", 0):
        improvement_flags.append("starter/searcher target may improve opener consistency")
    if mean(filler_counts or [0]) > 0:
        improvement_flags.append("filler limits may reduce safe-filler dependency")
    if mean(repair_counts or [0]) > 3:
        improvement_flags.append("repair constraints may expose package issues earlier")
    if warnings:
        improvement_flags.append("quota warning review needed before any activation")
    return {
        "flags": improvement_flags,
        "summary": "No activation; profile is ready for manual review only." if not improvement_flags else "Potential improvements require manual pilot review before activation.",
    }


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = str(report["archetype"]).casefold().replace(" ", "_").replace("-", "_")
    json_path = REPORT_DIR / f"latest_{slug}_semi_specialization_report.json"
    md_path = REPORT_DIR / f"latest_{slug}_semi_specialization_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparison"]
    plan = report["plan"]
    lines = [
        f"# {report['archetype']} Semi-Specialization Pilot Report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Semi-specialization activated: {report['semi_specialization_activated']}",
        f"- Profile used: {plan.get('profile_used')}",
        f"- Not activated: {plan.get('not_activated')}",
        "",
        "## Package Plan",
        "",
    ]
    for role, names in plan.get("package_plan", {}).items():
        lines.append(f"- `{role}`: {', '.join(names)}")
    lines.extend(
        [
            "",
            "## Generic Comparison",
            "",
            f"- Average generic score: {comparison['average_generic_score']}",
            f"- Average generic confidence: {comparison['average_generic_confidence']}",
            f"- All generic decks 40+: {comparison['legality_readiness']['all_decks_40_plus']}",
            f"- Repair success rate: {comparison['legality_readiness']['repair_success_rate']}",
            f"- Average repair action count: {comparison['repair_dependency']['average_repair_action_count']}",
            f"- Average safe filler used count: {comparison['filler_dependency']['average_safe_filler_used_count']}",
            "",
            "## Quota Alignment",
            "",
        ]
    )
    for role, row in comparison["quota_stability"]["quota_alignment"].items():
        lines.append(f"- `{role}`: observed {row['average_generic_observed']} vs target {row['target']} (delta {row['delta_from_target']})")
    lines.extend(["", "## Risk Flags", ""])
    for flag in plan.get("risk_flags", []) or ["None"]:
        lines.append(f"- {flag}")
    lines.extend(["", "## Expected Risk Improvement", ""])
    flags = comparison["expected_risk_improvement"]["flags"]
    if flags:
        lines.extend(f"- {flag}" for flag in flags)
    else:
        lines.append("- No measurable improvement claim yet; manual review only.")
    return "\n".join(lines) + "\n"


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    return any(term in str(card.get("type", "")).casefold() for term in ("fusion", "synchro", "xyz", "link"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare generic builds against a non-activated semi-specialization pilot plan.")
    parser.add_argument("--archetype", required=True)
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    report = run_pilot_report(args.archetype, args.mode, args.runs)
    json_path, md_path = save_report(report)
    print("Semi-Specialization Pilot Report Complete")
    print(f"Archetype: {args.archetype}")
    print(f"Semi-specialization activated: {report['semi_specialization_activated']}")
    print(f"Average generic score: {report['comparison']['average_generic_score']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
