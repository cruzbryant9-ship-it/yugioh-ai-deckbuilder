from __future__ import annotations

import argparse
import copy
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
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
QUOTA_TARGETS = {
    "starters": 12,
    "starters_searchers": 12,
    "extenders": 7,
    "payoffs": 3,
    "interruptions": 9,
    "board_breakers": 3,
    "bricks_garnets": 0,
    "garnet_brick": 0,
    "generic_fill": 0,
}


def run_regression_gate(mode: str = "meta", runs: int = 10, seed: int = 12345, frozen_cards: bool = False) -> dict[str, Any]:
    cards = load_frozen_cards()
    rows = []
    run_count = max(1, int(runs or 1))
    for index in range(run_count):
        run_seed = int(seed) + index
        generic_deck, generic_report = run_builder(cards, mode, run_seed, experimental=False)
        experimental_deck, experimental_report = run_builder(cards, mode, run_seed, experimental=True)
        rows.append(
            {
                "run": index + 1,
                "seed": run_seed,
                "generic": deck_result(generic_deck, generic_report, mode),
                "experimental": deck_result(experimental_deck, experimental_report, mode),
            }
        )
    generic = summarize(rows, "generic")
    experimental = summarize(rows, "experimental")
    score_delta = round(float(experimental["average_score"]) - float(generic["average_score"]), 4)
    quota_delta = round(float(experimental["quota_balance"]) - float(generic["quota_balance"]), 4)
    legality_delta = round(float(experimental["legality_rate"]) - float(generic["legality_rate"]), 4)
    fallback_delta = round(float(experimental["fallback_rate"]) - float(generic["fallback_rate"]), 4)
    generic_dependency = generic["dependency_telemetry"]
    experimental_dependency = experimental["dependency_telemetry"]
    safety = promotion_safety_gates(generic_dependency, experimental_dependency)
    recommendation = recommend_regression_status(generic, experimental, run_count, safety)
    return {
        "report_type": "kashtira_experimental_regression_gate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archetype": "Kashtira",
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "frozen_cards": bool(frozen_cards),
        "live_refresh_used": False,
        "generic": generic,
        "experimental": experimental,
        "score_delta": score_delta,
        "quota_delta": quota_delta,
        "legality_delta": legality_delta,
        "fallback_delta": fallback_delta,
        "generic_dependency": generic_dependency,
        "experimental_dependency": experimental_dependency,
        "dependency_delta": compare_dependency_summaries(generic_dependency, experimental_dependency),
        "dependency_gate_status": dependency_gate_status(generic_dependency, experimental_dependency),
        "generic_fill_gate": safety["generic_fill_gate"],
        "interaction_loss_gate": safety["interaction_loss_gate"],
        "promotion_blocking_reasons": safety["promotion_blocking_reasons"],
        "lost_interaction_cards": safety["lost_interaction_cards"],
        "recommendation": recommendation,
        "promotion_blocked": recommendation == "promote_blocked",
        "run_results": rows,
    }


def load_frozen_cards() -> list[dict[str, Any]]:
    # Intentionally no refresh call here; Phase 8J uses the local snapshot only.
    return CardDatabase().load_cards()


def run_builder(cards: list[dict[str, Any]], mode: str, seed: int, experimental: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    random.seed(seed)
    frozen_pool = copy.deepcopy(cards)
    deck, _pool = build_deck(
        frozen_pool,
        "Kashtira",
        mode=mode,
        experimental_semi_specialized=experimental,
        specialization_profile="Kashtira" if experimental else None,
    )
    return deck, get_last_build_report()


def deck_result(deck: list[dict[str, Any]], report: dict[str, Any], mode: str) -> dict[str, Any]:
    score = score_deck_breakdown(deck, "Kashtira", mode)
    package_counts = report.get("package_counts", {}) or {}
    blocked = blocked_card_violations(deck)
    main_count = int(report.get("main_deck_count", 0) or 0)
    extra_count = int(report.get("extra_deck_count", 0) or 0)
    return {
        "builder_used": report.get("builder_used"),
        "experimental": bool(report.get("experimental", False)),
        "not_default": bool(report.get("not_default", False)),
        "fallback_used": bool(report.get("fallback_used", False)),
        "score": float(score.get("final_score", 0) or 0),
        "package_quality": float(score.get("package_quality_score", 0) or 0),
        "package_counts": dict(package_counts),
        "quota_balance": quota_balance(package_counts),
        "legality_ok": main_count >= 40 and extra_count <= 15 and not blocked,
        "main_deck_count": main_count,
        "extra_deck_count": extra_count,
        "repair_dependency": float(report.get("repair_action_count", 0) or 0),
        "filler_dependency": float(report.get("safe_filler_used_count", 0) or 0),
        "dependency_telemetry": build_dependency_telemetry(deck, report, "Kashtira"),
        "blocked_card_violations": blocked,
        "quota_warnings": list(report.get("quota_warnings", []) or []),
        "metadata": {
            "chosen_engine_variant": report.get("chosen_engine_variant"),
            "experimental_profile": report.get("experimental_profile"),
            "fallback_used": report.get("fallback_used"),
        },
    }


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    selected = [row[key] for row in rows]
    scores = [float(row.get("score", 0) or 0) for row in selected]
    package_quality = [float(row.get("package_quality", 0) or 0) for row in selected]
    dependency_summary = summarize_dependency_telemetry(selected)
    package_totals: Counter[str] = Counter()
    for row in selected:
        package_totals.update({name: float(value or 0) for name, value in (row.get("package_counts", {}) or {}).items()})
    return {
        "average_score": round(mean(scores), 4),
        "best_score": round(max(scores), 4),
        "worst_score": round(min(scores), 4),
        "score_variance": round(pstdev(scores), 6),
        "average_package_quality": round(mean(package_quality), 4),
        "legality_rate": round(mean(1.0 if row.get("legality_ok") else 0.0 for row in selected), 4),
        "repair_dependency": round(mean(float(row.get("repair_dependency", 0) or 0) for row in selected), 4),
        "filler_dependency": round(mean(float(row.get("filler_dependency", 0) or 0) for row in selected), 4),
        "safe_filler_used_count": dependency_summary["safe_filler_used_count"],
        "repair_used": dependency_summary["repair_used"],
        "repair_success": dependency_summary["repair_success"],
        "repair_action_count": dependency_summary["repair_action_count"],
        "repair_dependency_score": dependency_summary["repair_dependency_score"],
        "filler_dependency_score": dependency_summary["filler_dependency_score"],
        "dependency_telemetry": dependency_summary,
        "quota_balance": round(mean(float(row.get("quota_balance", 0) or 0) for row in selected), 4),
        "blocked_card_violations": sorted(set(name for row in selected for name in row.get("blocked_card_violations", []))),
        "fallback_rate": round(mean(1.0 if row.get("fallback_used") else 0.0 for row in selected), 4),
        "average_package_counts": {name: round(total / max(1, len(selected)), 4) for name, total in sorted(package_totals.items())},
        "builders_used": sorted(set(str(row.get("builder_used")) for row in selected)),
        "builder_metadata": [row.get("metadata", {}) for row in selected],
    }


def quota_balance(package_counts: dict[str, Any]) -> float:
    if not package_counts:
        return 0.0
    total_gap = 0.0
    for key, target in QUOTA_TARGETS.items():
        if key in package_counts:
            total_gap += abs(float(package_counts.get(key, 0) or 0) - float(target))
    return round(total_gap, 4)


def recommend_regression_status(generic: dict[str, Any], experimental: dict[str, Any], runs: int, safety: dict[str, Any] | None = None) -> str:
    if safety and safety.get("promotion_blocked"):
        return "promote_blocked"
    score_regresses = float(experimental.get("average_score", 0) or 0) < float(generic.get("average_score", 0) or 0)
    quota_improves = float(experimental.get("quota_balance", 9999) or 9999) <= float(generic.get("quota_balance", 9999) or 9999)
    if score_regresses:
        return "promote_blocked"
    if float(experimental.get("legality_rate", 0) or 0) < 1.0:
        return "promote_blocked"
    if experimental.get("blocked_card_violations"):
        return "promote_blocked"
    if quota_improves and score_regresses:
        return "promote_blocked"
    if float(experimental.get("fallback_rate", 0) or 0) > 0.0:
        return "needs_retest"
    if variance_instability(generic, experimental):
        return "needs_retest"
    if runs < 5:
        return "needs_retest"
    if (
        not score_regresses
        and float(experimental.get("legality_rate", 0) or 0) == 1.0
        and not experimental.get("blocked_card_violations")
        and float(experimental.get("fallback_rate", 0) or 0) == 0.0
        and quota_improves
    ):
        return "eligible_for_more_testing"
    return "needs_retest"


def variance_instability(generic: dict[str, Any], experimental: dict[str, Any]) -> bool:
    generic_variance = float(generic.get("score_variance", 0) or 0)
    experimental_variance = float(experimental.get("score_variance", 0) or 0)
    return experimental_variance > max(1.5, generic_variance * 2.0)


def save_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_kashtira_experimental_regression_gate.json"
    md_path = REPORT_DIR / "latest_kashtira_experimental_regression_gate.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, render_markdown(report))
    return json_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    generic = report["generic"]
    experimental = report["experimental"]
    lines = [
        "# Kashtira Experimental Regression Gate",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Runs: {report['runs']}",
        f"- Seed: {report['seed']}",
        f"- Frozen cards: {report['frozen_cards']}",
        f"- Live refresh used: {report['live_refresh_used']}",
        f"- Recommendation: `{report['recommendation']}`",
        f"- Promotion blocked: {report['promotion_blocked']}",
        "",
        "## Generic",
        "",
        f"- Average score: {generic['average_score']}",
        f"- Best score: {generic['best_score']}",
        f"- Worst score: {generic['worst_score']}",
        f"- Score variance: {generic['score_variance']}",
        f"- Package quality: {generic['average_package_quality']}",
        f"- Legality rate: {generic['legality_rate']}",
        f"- Quota balance: {generic['quota_balance']}",
        f"- Filler dependency score: {generic['dependency_telemetry']['filler_dependency_score']}",
        f"- Repair dependency score: {generic['dependency_telemetry']['repair_dependency_score']}",
        "",
        "## Experimental",
        "",
        f"- Average score: {experimental['average_score']}",
        f"- Best score: {experimental['best_score']}",
        f"- Worst score: {experimental['worst_score']}",
        f"- Score variance: {experimental['score_variance']}",
        f"- Package quality: {experimental['average_package_quality']}",
        f"- Legality rate: {experimental['legality_rate']}",
        f"- Quota balance: {experimental['quota_balance']}",
        f"- Fallback rate: {experimental['fallback_rate']}",
        f"- Filler dependency score: {experimental['dependency_telemetry']['filler_dependency_score']}",
        f"- Repair dependency score: {experimental['dependency_telemetry']['repair_dependency_score']}",
        "",
        "## Deltas",
        "",
        f"- Score delta: {report['score_delta']}",
        f"- Quota delta: {report['quota_delta']}",
        f"- Legality delta: {report['legality_delta']}",
        f"- Fallback delta: {report['fallback_delta']}",
        "",
        "## Dependency Gate Status",
        "",
        f"- {report['dependency_gate_status']}",
        "",
        "## Promotion Safety Gates",
        "",
        f"- Generic-fill gate: {report['generic_fill_gate']}",
        f"- Interaction-loss gate: {report['interaction_loss_gate']}",
        f"- Promotion blocking reasons: {report['promotion_blocking_reasons']}",
        f"- Lost interaction cards: {report['lost_interaction_cards']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed-seed regression gate for generic vs explicit experimental Kashtira.")
    parser.add_argument("--mode", default="meta")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--frozen-cards", action="store_true")
    args = parser.parse_args()
    report = run_regression_gate(args.mode, args.runs, args.seed, frozen_cards=args.frozen_cards)
    json_path, md_path = save_report(report)
    print("Kashtira Experimental Regression Gate Complete")
    print(f"Mode: {args.mode}")
    print(f"Runs: {report['runs']}")
    print(f"Seed: {report['seed']}")
    print(f"Frozen cards: {report['frozen_cards']}")
    print(f"Generic average score: {report['generic']['average_score']}")
    print(f"Experimental average score: {report['experimental']['average_score']}")
    print(f"Score delta: {report['score_delta']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
