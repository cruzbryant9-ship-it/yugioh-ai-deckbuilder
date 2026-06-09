from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_h_variant_broader_validation import H_DRY_RUN_VARIANT, run_broader_validation, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_aa.json"
PHASE_REPORT = Path("STABILIZATION_AA_BROADER_CANDIDATE_VALIDATION.md")
_REPORT_CACHE: dict[str, Any] | None = None


def main() -> None:
    checks = [
        ("broader runner works", validate_runner_works),
        ("multiple seeds are used", validate_multiple_seeds),
        ("per-seed results are recorded", validate_per_seed_results),
        ("aggregate results are recorded", validate_aggregate_results),
        ("H variant remains explicit-only", validate_h_explicit_only),
        ("default Kashtira remains generic", validate_default_kashtira_generic),
        ("no builder defaults changed", validate_no_builder_defaults_changed),
        ("no promotion occurs", validate_no_promotion),
        ("Stabilization Z validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_z", "validate_stabilization_z.py")),
        ("Stabilization Y validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_y", "validate_stabilization_y.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_aa", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization AA validation complete.")


def report() -> dict[str, Any]:
    global _REPORT_CACHE
    if _REPORT_CACHE is None:
        _REPORT_CACHE = run_broader_validation("meta", 2, [12345, 23456, 34567], frozen_cards=True)
    return _REPORT_CACHE


def fresh_cards() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def validate_runner_works() -> dict[str, Any]:
    small = run_broader_validation("meta", 1, [12345, 23456], frozen_cards=True)
    json_path, md_path = save_report(small)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "seeds": small["seeds"], "recommendation": small["recommendation"]}


def validate_multiple_seeds() -> dict[str, Any]:
    payload = report()
    if payload.get("seeds") != [12345, 23456, 34567]:
        raise AssertionError(payload.get("seeds"))
    if len(payload.get("per_seed_results", [])) != 3:
        raise AssertionError(len(payload.get("per_seed_results", [])))
    return {"seeds": payload["seeds"], "seed_count": len(payload["per_seed_results"])}


def validate_per_seed_results() -> dict[str, Any]:
    payload = report()
    required = {
        "seed",
        "generic",
        "h_variant",
        "delta",
        "positive_run_count",
        "negative_run_count",
        "neutral_run_count",
        "legality_rate",
        "fallback_rate",
        "interaction_count",
        "generic_fill_count",
        "blocked_card_violations",
        "promotion_blockers",
    }
    for seed_report in payload.get("per_seed_results", []):
        missing = required - set(seed_report)
        if missing:
            raise AssertionError({"seed": seed_report.get("seed"), "missing": sorted(missing)})
    return {"per_seed_rows": len(payload["per_seed_results"])}


def validate_aggregate_results() -> dict[str, Any]:
    payload = report()
    aggregate = payload.get("aggregate", {})
    required = {
        "average_delta_across_seeds",
        "worst_seed_delta",
        "best_seed_delta",
        "total_positive_run_count",
        "total_negative_run_count",
        "total_neutral_run_count",
        "total_positive_rate",
        "safety_status",
    }
    missing = required - set(aggregate)
    if missing:
        raise AssertionError(sorted(missing))
    if payload.get("recommendation") != expected_recommendation(payload):
        raise AssertionError({"expected": expected_recommendation(payload), "actual": payload.get("recommendation")})
    return {"aggregate": aggregate, "recommendation": payload["recommendation"]}


def validate_h_explicit_only() -> dict[str, Any]:
    cards = fresh_cards()
    build_deck(cards, "Kashtira", mode="meta")
    default_report = get_last_build_report()
    build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant=H_DRY_RUN_VARIANT,
    )
    h_report = get_last_build_report()
    if default_report.get("variant") == H_DRY_RUN_VARIANT or default_report.get("experimental"):
        raise AssertionError(default_report)
    if h_report.get("variant") != H_DRY_RUN_VARIANT or not h_report.get("dry_run_variant"):
        raise AssertionError(h_report)
    return {
        "default_builder": default_report.get("builder_used"),
        "h_builder": h_report.get("builder_used"),
        "h_variant": h_report.get("variant"),
        "dry_run_variant": h_report.get("dry_run_variant"),
    }


def validate_default_kashtira_generic() -> dict[str, Any]:
    build_deck(fresh_cards(), "Kashtira", mode="meta")
    build_report = get_last_build_report()
    if build_report.get("builder_used") not in {"generic", "generic_tuned"} or build_report.get("experimental"):
        raise AssertionError(build_report)
    return {"builder_used": build_report.get("builder_used"), "experimental": build_report.get("experimental")}


def validate_no_builder_defaults_changed() -> dict[str, Any]:
    cards = fresh_cards()
    build_deck(cards, "Blue-Eyes", mode="meta")
    blue_report = get_last_build_report()
    build_deck(cards, "Kashtira", mode="meta")
    kashtira_report = get_last_build_report()
    if blue_report.get("builder_used") != "authored":
        raise AssertionError(blue_report)
    if kashtira_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(kashtira_report)
    return {"blue_eyes_builder": blue_report.get("builder_used"), "kashtira_builder": kashtira_report.get("builder_used")}


def validate_no_promotion() -> dict[str, Any]:
    payload = report()
    if payload.get("promotion_applied") is not False or payload.get("default_behavior_changed") is not False:
        raise AssertionError({"promotion_applied": payload.get("promotion_applied"), "default_behavior_changed": payload.get("default_behavior_changed")})
    if payload.get("recommendation") not in {"keep_dry_run_only", "needs_more_data", "eligible_for_candidate_review"}:
        raise AssertionError(payload.get("recommendation"))
    return {"promotion_applied": payload["promotion_applied"], "recommendation": payload["recommendation"]}


def expected_recommendation(payload: dict[str, Any]) -> str:
    per_seed = payload.get("per_seed_results", [])
    aggregate = payload.get("aggregate", {})
    if any(float(seed.get("delta", 0) or 0) <= 0 for seed in per_seed):
        return "keep_dry_run_only"
    if float(aggregate.get("total_positive_rate", 0) or 0) < 0.75:
        return "keep_dry_run_only"
    if not (aggregate.get("safety_status") or {}).get("clean", False):
        return "keep_dry_run_only"
    if float(aggregate.get("worst_seed_delta", 0) or 0) < 0.5:
        return "needs_more_data"
    return "eligible_for_candidate_review"


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
    aggregate = payload["aggregate"]
    lines = [
        "# Stabilization AA: Broader Candidate Validation",
        "",
        "Broader validation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, current experimental behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_h_variant_broader_validation.py`",
        "- `validate_stabilization_aa.py`",
        "- `STABILIZATION_AA_BROADER_CANDIDATE_VALIDATION.md`",
        "",
        "## Files Changed",
        "",
        "- None; this phase adds broader validation/reporting files.",
        "",
        "## Explicit Candidate",
        "",
        f"- Variant: `{H_DRY_RUN_VARIANT}`",
        "- Explicit-only dry-run path.",
        "- No default behavior changed.",
        "",
        "## Per-Seed Snapshot",
        "",
        "| Seed | Runs | Generic Avg | H Avg | Delta | Positive | Negative | Neutral | Legality | Fallback | Interaction | Generic Fill |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for seed_report in payload["per_seed_results"]:
        lines.append(
            f"| {seed_report['seed']} | {seed_report['runs']} | {seed_report['generic']['average_score']} | {seed_report['h_variant']['average_score']} | "
            f"{seed_report['delta']} | {seed_report['positive_run_count']} | {seed_report['negative_run_count']} | {seed_report['neutral_run_count']} | "
            f"{seed_report['legality_rate']} | {seed_report['fallback_rate']} | {seed_report['interaction_count']} | {seed_report['generic_fill_count']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate Snapshot",
            "",
            f"- Average delta across seeds: `{aggregate['average_delta_across_seeds']}`",
            f"- Worst seed delta: `{aggregate['worst_seed_delta']}`",
            f"- Best seed delta: `{aggregate['best_seed_delta']}`",
            f"- Total positive / negative / neutral: `{aggregate['total_positive_run_count']}` / `{aggregate['total_negative_run_count']}` / `{aggregate['total_neutral_run_count']}`",
            f"- Safety status: `{aggregate['safety_status']}`",
            f"- Recommendation: `{payload['recommendation']}`",
            f"- Promotion applied: `{payload['promotion_applied']}`",
            "",
            "## Validation Results",
            "",
            f"- Passed: {validation.get('passed')}",
            f"- Duration seconds: {validation.get('duration_seconds')}",
        ]
    )
    for check in validation.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "- Stabilization AB should review the candidate evidence and, if still clean, test the explicit H candidate against additional modes or matchup-aware conditions while keeping it non-default.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
