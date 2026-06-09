from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from kashtira_public_overlay_large_sample import VARIANT, run_large_sample, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_v.json"
PHASE_REPORT = Path("STABILIZATION_V_PUBLIC_OVERLAY_LARGE_SAMPLE.md")


def main() -> None:
    checks = [
        ("large sample runner works", validate_large_sample_runner),
        ("generic vs variant comparison exists", validate_comparison_shape),
        ("fixed seed/frozen card mode is enforced", validate_fixed_seed_frozen_mode),
        ("variant remains explicit-only", validate_variant_explicit_only),
        ("no default behavior changed", validate_no_default_behavior_changed),
        ("interaction cards remain preserved", validate_interactions_preserved),
        ("generic_fill remains measured", validate_generic_fill_measured),
        ("recommendation follows rules", validate_recommendation_rules),
        ("Stabilization U validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_u", "validate_stabilization_u.py")),
        ("Stabilization T validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_t", "validate_stabilization_t.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_v", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization V validation complete.")


def fresh_cards() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def validate_large_sample_runner() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    json_path, md_path = save_report(report)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "runs": report["runs"], "recommendation": report["recommendation"]}


def validate_comparison_shape() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    required = {"generic", "variant", "score_delta", "positive_run_count", "negative_run_count", "neutral_run_count", "run_results"}
    missing = required - set(report)
    if missing:
        raise AssertionError(missing)
    if report["variant_name"] != VARIANT or len(report["run_results"]) != 2:
        raise AssertionError(report)
    return {"variant_name": report["variant_name"], "score_delta": report["score_delta"], "runs": len(report["run_results"])}


def validate_fixed_seed_frozen_mode() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    seeds = [row["seed"] for row in report["run_results"]]
    if report.get("seed") != 12345 or seeds != [12345, 12346] or report.get("frozen_cards") is not True or report.get("live_refresh_used") is not False:
        raise AssertionError({"seed": report.get("seed"), "seeds": seeds, "frozen": report.get("frozen_cards"), "live": report.get("live_refresh_used")})
    return {"seed": report["seed"], "run_seeds": seeds, "frozen_cards": report["frozen_cards"], "live_refresh_used": report["live_refresh_used"]}


def validate_variant_explicit_only() -> dict[str, Any]:
    cards = fresh_cards()
    build_deck(cards, "Kashtira", mode="meta")
    default_report = get_last_build_report()
    build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant=VARIANT,
    )
    variant_report = get_last_build_report()
    if default_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(default_report)
    if variant_report.get("variant") != VARIANT or variant_report.get("dry_run_variant") is not True:
        raise AssertionError(variant_report)
    return {"default_builder": default_report.get("builder_used"), "variant": variant_report.get("variant"), "dry_run": variant_report.get("dry_run_variant")}


def validate_no_default_behavior_changed() -> dict[str, Any]:
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


def validate_interactions_preserved() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    expected = len(interaction_core_for("Kashtira"))
    if report["variant"].get("interaction_selected_average") != float(expected):
        raise AssertionError(report["variant"])
    if report.get("lost_interaction_cards"):
        raise AssertionError(report.get("lost_interaction_cards"))
    return {"interaction_selected_average": report["variant"].get("interaction_selected_average"), "lost_interaction_cards": report.get("lost_interaction_cards")}


def validate_generic_fill_measured() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    generic_fill = report["variant"].get("generic_fill_count", {})
    if generic_fill.get("status") != "measured" or report["variant"].get("generic_fill_average") is None:
        raise AssertionError(generic_fill)
    return {"generic_fill": generic_fill, "generic_fill_average": report["variant"].get("generic_fill_average")}


def validate_recommendation_rules() -> dict[str, Any]:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    expected = expected_recommendation(report)
    if report.get("recommendation") != expected:
        raise AssertionError({"expected": expected, "actual": report.get("recommendation"), "report": report})
    return {"recommendation": report["recommendation"], "score_delta": report["score_delta"]}


def expected_recommendation(report: dict[str, Any]) -> str:
    if float(report.get("score_delta", 0) or 0) <= 0:
        return "keep_dry_run_only"
    variant = report["variant"]
    if float(variant.get("legality_rate", 0) or 0) < 1.0 or float(variant.get("fallback_rate", 0) or 0) > 0.0:
        return "keep_dry_run_only"
    if variant.get("blocked_card_violations") or report.get("lost_interaction_cards"):
        return "keep_dry_run_only"
    if report.get("generic_fill_gate", {}).get("promotion_blocked"):
        return "keep_dry_run_only"
    if float(report.get("score_delta", 0) or 0) < 0.5:
        return "needs_more_data"
    return "eligible_for_experimental_update"


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


def write_phase_report(payload: dict[str, Any]) -> None:
    report = run_large_sample("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Stabilization V: Public Overlay Large Sample",
        "",
        "Larger-sample validation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_public_overlay_large_sample.py`",
        "- `validate_stabilization_v.py`",
        "- `STABILIZATION_V_PUBLIC_OVERLAY_LARGE_SAMPLE.md`",
        "",
        "## Files Changed",
        "",
        "- None; this phase adds validation/reporting files only.",
        "",
        "## Large Sample Results",
        "",
        f"- Runs: `{report['runs']}`",
        f"- Generic average score: `{report['generic']['average_score']}`",
        f"- Variant average score: `{report['variant']['average_score']}`",
        f"- Score delta: `{report['score_delta']}`",
        f"- Positive / negative / neutral runs: `{report['positive_run_count']}` / `{report['negative_run_count']}` / `{report['neutral_run_count']}`",
        f"- Variant generic-fill average: `{report['variant']['generic_fill_average']}`",
        f"- Variant interaction selected average: `{report['variant']['interaction_selected_average']}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Validation Results",
        "",
        f"- Passed: {payload.get('passed')}",
        f"- Duration seconds: {payload.get('duration_seconds')}",
    ]
    for check in payload.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "- If the 30-run sample remains positive but below threshold, Stabilization W should inspect seed-level score deltas and component deltas before considering any adapter change.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
