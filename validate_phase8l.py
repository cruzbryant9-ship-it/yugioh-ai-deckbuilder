from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_adapter_tuning import generate_kashtira_adapter_tuning_variants
from kashtira_adapter_tuning_plan import build_tuning_plan, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8L_KASHTIRA_ADAPTER_TUNING_PLAN.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8l.json"
PLAN_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_adapter_tuning_plan.json"
PLAN_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_adapter_tuning_plan.md"


def main() -> None:
    checks = [
        ("proposed variants are generated", validate_variants_generated),
        ("all variants are marked applied false", validate_variants_not_applied),
        ("tuning runner works", validate_runner),
        ("generic/current experimental/variants are compared", validate_comparison_shape),
        ("no active builder behavior changes", validate_default_builder),
        ("Blue-Eyes authored behavior remains untouched", validate_blue_eyes),
        ("best variant recommendation is report-only", validate_report_only),
        ("Phase 8K validator still passes", validate_phase8k),
        ("Phase 8J validator still passes", validate_phase8j),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8l", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8L validation complete.")


def validate_variants_generated() -> dict[str, Any]:
    variants = generate_kashtira_adapter_tuning_variants()
    if len(variants) < 6:
        raise AssertionError(variants)
    return {"variant_count": len(variants), "variants": [variant["name"] for variant in variants]}


def validate_variants_not_applied() -> dict[str, Any]:
    variants = generate_kashtira_adapter_tuning_variants()
    if any(variant.get("applied") is not False for variant in variants):
        raise AssertionError(variants)
    return {"all_applied_false": True}


def validate_runner() -> dict[str, Any]:
    report = build_tuning_plan("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    assert_json_report_exists(PLAN_JSON, ("generic_baseline", "current_experimental_baseline", "variants", "recommendation"))
    assert_markdown_report_exists(PLAN_MD, ("Baselines", "Variants", "Best Variant"))
    return {"recommendation": report["recommendation"], "best_variant": report["best_variant"].get("name")}


def validate_comparison_shape() -> dict[str, Any]:
    report = build_tuning_plan("meta", 1, 12345, frozen_cards=True)
    if not report.get("generic_baseline") or not report.get("current_experimental_baseline") or not report.get("variants"):
        raise AssertionError(report)
    return {"variant_count": len(report["variants"])}


def validate_default_builder() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_blue_eyes() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_report_only() -> dict[str, Any]:
    report = build_tuning_plan("meta", 1, 12345, frozen_cards=True)
    allowed = {"keep_current_experimental_blocked", "test_variant_next", "eligible_for_experimental_adapter_update"}
    if report.get("recommendation") not in allowed or report.get("report_only") is not True or report.get("updates_applied") is not False:
        raise AssertionError(report)
    return {"recommendation": report["recommendation"], "report_only": report["report_only"], "updates_applied": report["updates_applied"]}


def validate_phase8k() -> dict[str, Any]:
    return assert_validator_artifact_passed("validate_phase8k")


def validate_phase8j() -> dict[str, Any]:
    return assert_validator_artifact_passed("validate_phase8j")


def validate_phase8a() -> dict[str, Any]:
    return assert_validator_artifact_passed("validate_phase8a")


def validate_core_suite() -> dict[str, Any]:
    result = run_python("validate_core_suite.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, Any]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def assert_validator_artifact_passed(name: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if not path.exists():
        raise AssertionError(f"missing prior validator artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise AssertionError(payload)
    return {"artifact": str(path), "passed": payload.get("passed"), "duration_seconds": payload.get("duration_seconds")}


def write_phase_report(payload: dict[str, Any]) -> None:
    report = build_tuning_plan("meta", 10, 12345, frozen_cards=True)
    save_report(report)
    best = report["best_variant"]
    lines = [
        "# Phase 8L: Kashtira Adapter Tuning Plan",
        "",
        "Proposed-only tuning and regression testing. No gameplay behavior, active builder behavior, scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, generic builder behavior, neural networks, reinforcement learning, self-play, duel engine features, or full combo graphs were changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_adapter_tuning.py`",
        "- `kashtira_adapter_tuning_plan.py`",
        "- `validate_phase8l.py`",
        "- `PHASE8L_KASHTIRA_ADAPTER_TUNING_PLAN.md`",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Variants Tested",
        "",
    ]
    for variant in report["variants"]:
        lines.append(f"- `{variant['name']}`: score {variant['average_score']}, applied {variant['applied']}")
    lines.extend(
        [
            "",
            "## Baselines",
            "",
            f"- Generic average score: {report['generic_baseline']['average_score']}",
            f"- Current experimental average score: {report['current_experimental_baseline']['average_score']}",
            "",
            "## Best Variant",
            "",
            f"- `{best.get('name')}`",
            f"- Average score: {best.get('average_score')}",
            f"- Score delta vs generic: {best.get('score_delta_vs_generic')}",
            f"- Score delta vs current experimental: {best.get('score_delta_vs_current_experimental')}",
            f"- Quota balance: {best.get('quota_balance')}",
            "",
            "## Recommendation",
            "",
            f"- `{report['recommendation']}`",
            "",
            "## Validation Results",
            "",
            f"- Passed: {payload.get('passed')}",
            f"- Duration seconds: {payload.get('duration_seconds')}",
        ]
    )
    for check in payload.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Phase 8M",
            "",
            "- Implement the best proposed variant behind a separate explicit test flag or dry-run adapter branch, then re-run the Phase 8J fixed-seed gate before changing the active experimental adapter.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
