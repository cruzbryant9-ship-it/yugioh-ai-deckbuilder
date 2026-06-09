from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_targeted_swap_sensitivity import SWAP_VARIANTS, run_swap_sensitivity, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_x.json"
PHASE_REPORT = Path("STABILIZATION_X_TARGETED_SWAP_SENSITIVITY.md")
_REPORT_CACHE: dict[str, Any] | None = None


def main() -> None:
    checks = [
        ("targeted analyzer runs", validate_analyzer_runs),
        ("all swap variants are tested", validate_all_variants_tested),
        ("no builder behavior changes", validate_no_builder_behavior_changes),
        ("no active adapter behavior changes", validate_no_active_adapter_behavior_changes),
        ("generic builder remains unchanged", validate_generic_builder_unchanged),
        ("classification exists for each swap", validate_classifications),
        ("recommendation follows rules", validate_recommendation_rules),
        ("Stabilization W validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_w", "validate_stabilization_w.py")),
        ("Stabilization V validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_v", "validate_stabilization_v.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_x", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization X validation complete.")


def report() -> dict[str, Any]:
    global _REPORT_CACHE
    if _REPORT_CACHE is None:
        _REPORT_CACHE = run_swap_sensitivity("meta", 30, 12345, frozen_cards=True)
    return _REPORT_CACHE


def validate_analyzer_runs() -> dict[str, Any]:
    small = run_swap_sensitivity("meta", 2, 12345, frozen_cards=True)
    json_path, md_path = save_report(small)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "runs": small["runs"], "best_adjustment": small["best_adjustment"]}


def validate_all_variants_tested() -> dict[str, Any]:
    payload = report()
    expected = set(SWAP_VARIANTS)
    actual = set(payload.get("adjustment_summaries", {}))
    if actual != expected:
        raise AssertionError({"expected": sorted(expected), "actual": sorted(actual)})
    return {"variant_count": len(actual), "variants": sorted(actual)}


def validate_no_builder_behavior_changes() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(cards, "Blue-Eyes", mode="meta")
    blue_report = get_last_build_report()
    build_deck(cards, "Kashtira", mode="meta")
    kashtira_report = get_last_build_report()
    if blue_report.get("builder_used") != "authored":
        raise AssertionError(blue_report)
    if kashtira_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(kashtira_report)
    return {"blue_eyes_builder": blue_report.get("builder_used"), "kashtira_builder": kashtira_report.get("builder_used")}


def validate_no_active_adapter_behavior_changes() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_overlay_reduce_generic_fill",
    )
    active_report = get_last_build_report()
    if active_report.get("variant") != "public_overlay_reduce_generic_fill" or active_report.get("dry_run_variant") is not True:
        raise AssertionError(active_report)
    if active_report.get("proposed_swap_adjustment"):
        raise AssertionError(active_report)
    return {
        "variant": active_report.get("variant"),
        "dry_run_variant": active_report.get("dry_run_variant"),
        "fallback_used": active_report.get("fallback_used"),
    }


def validate_generic_builder_unchanged() -> dict[str, Any]:
    build_deck(CardDatabase().load_cards(), "Kashtira", mode="meta")
    generic_report = get_last_build_report()
    if generic_report.get("builder_used") not in {"generic", "generic_tuned"} or generic_report.get("experimental"):
        raise AssertionError(generic_report)
    return {"builder_used": generic_report.get("builder_used"), "experimental": generic_report.get("experimental")}


def validate_classifications() -> dict[str, Any]:
    payload = report()
    allowed = {"helpful", "neutral", "harmful", "inconclusive"}
    classifications = {name: summary.get("classification") for name, summary in payload["adjustment_summaries"].items()}
    bad = {name: value for name, value in classifications.items() if value not in allowed}
    if bad:
        raise AssertionError(bad)
    return classifications


def validate_recommendation_rules() -> dict[str, Any]:
    payload = report()
    expected = expected_recommendation(payload)
    if payload.get("recommendation") != expected:
        raise AssertionError({"expected": expected, "actual": payload.get("recommendation")})
    return {"recommendation": payload["recommendation"], "best_adjustment": payload["best_adjustment"]}


def expected_recommendation(payload: dict[str, Any]) -> str:
    summaries = payload["adjustment_summaries"]
    if all(summary["classification"] == "harmful" for summary in summaries.values()):
        return "abandon_public_overlay"
    best = payload["best_adjustment"]
    best_summary = summaries[best]
    if best_summary["classification"] == "helpful" and best_summary["score_delta_vs_public_overlay"] >= 0.25:
        return "test_adjusted_variant_next"
    if not any(summary["score_delta_vs_public_overlay"] > 0 for summary in summaries.values()):
        return "keep_current_public_overlay"
    return "needs_more_data"


def validate_prior_artifact_or_run(name: str, script: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("passed") is True:
            return {"artifact": str(path), "passed": True, "duration_seconds": payload.get("duration_seconds")}
    result = run_python(script, timeout=7200)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8a() -> dict[str, Any]:
    result = run_python("validate_phase8a.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_core_suite() -> dict[str, Any]:
    result = run_python("validate_core_suite.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, Any]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def write_phase_report(validation: dict[str, Any]) -> None:
    payload = report()
    save_report(payload)
    best = payload["best_adjustment"]
    lines = [
        "# Stabilization X: Targeted Swap Sensitivity",
        "",
        "Targeted sensitivity analysis only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, active adapter behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_targeted_swap_sensitivity.py`",
        "- `validate_stabilization_x.py`",
        "- `STABILIZATION_X_TARGETED_SWAP_SENSITIVITY.md`",
        "",
        "## Files Changed",
        "",
        "- None; this phase adds proposed-only analysis/reporting files.",
        "",
        "## Best Adjustment",
        "",
        f"- Best adjustment: `{best}`",
        f"- Classification: `{payload['adjustment_summaries'][best]['classification']}`",
        f"- Score delta vs public overlay: `{payload['adjustment_summaries'][best]['score_delta_vs_public_overlay']}`",
        f"- Recommendation: `{payload['recommendation']}`",
        "",
        "## Swap Variants Tested",
        "",
    ]
    for name, summary in payload["adjustment_summaries"].items():
        lines.append(
            f"- `{name}`: `{summary['classification']}`, score `{summary['average_score']}`, "
            f"vs generic `{summary['score_delta_vs_generic']}`, vs public overlay `{summary['score_delta_vs_public_overlay']}`"
        )
    lines.extend(["", "## Harmful Adjustments", "", f"- `{payload['harmful_adjustments']}`", "", "## Validation Results", ""])
    lines.append(f"- Passed: {validation.get('passed')}")
    lines.append(f"- Duration seconds: {validation.get('duration_seconds')}")
    for check in validation.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "- Stabilization Y should run a proposed-only larger sample for the best restoration adjustment before any adapter change is considered.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
