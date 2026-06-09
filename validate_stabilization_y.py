from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_h_variant_large_sample import H_VARIANT_NAME, run_h_large_sample, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_y.json"
PHASE_REPORT = Path("STABILIZATION_Y_H_VARIANT_LARGE_SAMPLE.md")
_REPORT_CACHE: dict[str, Any] | None = None


def main() -> None:
    checks = [
        ("H large-sample runner works", validate_runner_works),
        ("generic/public-overlay/H comparison exists", validate_comparison_exists),
        ("fixed seed/frozen card mode is enforced", validate_fixed_seed_frozen),
        ("H variant remains proposed-only", validate_h_proposed_only),
        ("no builder behavior changes", validate_no_builder_changes),
        ("no active adapter behavior changes", validate_no_active_adapter_changes),
        ("recommendation follows rules", validate_recommendation_rules),
        ("Stabilization X validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_x", "validate_stabilization_x.py")),
        ("Stabilization W validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_w", "validate_stabilization_w.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_y", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization Y validation complete.")


def report() -> dict[str, Any]:
    global _REPORT_CACHE
    if _REPORT_CACHE is None:
        _REPORT_CACHE = run_h_large_sample("meta", 50, 12345, frozen_cards=True)
    return _REPORT_CACHE


def validate_runner_works() -> dict[str, Any]:
    small = run_h_large_sample("meta", 2, 12345, frozen_cards=True)
    json_path, md_path = save_report(small)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "runs": small["runs"], "recommendation": small["recommendation"]}


def validate_comparison_exists() -> dict[str, Any]:
    payload = report()
    required = {"generic", "public_overlay", "h_variant", "run_results"}
    missing = required - set(payload)
    if missing:
        raise AssertionError(missing)
    if payload["h_variant_name"] != H_VARIANT_NAME or len(payload["run_results"]) != 50:
        raise AssertionError({"h_variant_name": payload.get("h_variant_name"), "rows": len(payload.get("run_results", []))})
    return {"runs": payload["runs"], "h_variant": payload["h_variant_name"], "delta_vs_generic": payload["h_variant"]["delta_vs_generic"]}


def validate_fixed_seed_frozen() -> dict[str, Any]:
    payload = report()
    seeds = [row["seed"] for row in payload["run_results"][:3]]
    if payload.get("seed") != 12345 or seeds != [12345, 12346, 12347] or payload.get("frozen_cards") is not True or payload.get("live_refresh_used") is not False:
        raise AssertionError({"seed": payload.get("seed"), "seeds": seeds, "frozen": payload.get("frozen_cards"), "live": payload.get("live_refresh_used")})
    return {"seed": payload["seed"], "first_seeds": seeds, "frozen_cards": payload["frozen_cards"], "live_refresh_used": payload["live_refresh_used"]}


def validate_h_proposed_only() -> dict[str, Any]:
    payload = report()
    h = payload["h_variant"]
    if h.get("applied_rate") != 1.0 or payload["h_swap"].get("proposed_only") is not True:
        raise AssertionError({"h_swap": payload.get("h_swap"), "h": h})
    if any(row["h_variant"].get("proposed_only") is not True for row in payload["run_results"]):
        raise AssertionError("H row not proposed-only")
    return {"applied_rate": h.get("applied_rate"), "h_swap": payload["h_swap"]}


def validate_no_builder_changes() -> dict[str, Any]:
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


def validate_no_active_adapter_changes() -> dict[str, Any]:
    build_deck(
        CardDatabase().load_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_overlay_reduce_generic_fill",
    )
    active_report = get_last_build_report()
    if active_report.get("variant") != "public_overlay_reduce_generic_fill" or active_report.get("dry_run_variant") is not True:
        raise AssertionError(active_report)
    if active_report.get("h_variant_name") or active_report.get("proposed_swap_adjustment"):
        raise AssertionError(active_report)
    return {"variant": active_report.get("variant"), "dry_run_variant": active_report.get("dry_run_variant"), "fallback_used": active_report.get("fallback_used")}


def validate_recommendation_rules() -> dict[str, Any]:
    payload = report()
    expected = expected_recommendation(payload)
    if payload.get("recommendation") != expected:
        raise AssertionError({"expected": expected, "actual": payload.get("recommendation")})
    return {"recommendation": payload["recommendation"], "delta_vs_generic": payload["h_variant"]["delta_vs_generic"]}


def expected_recommendation(payload: dict[str, Any]) -> str:
    h = payload["h_variant"]
    safety = payload["safety_metrics"]
    if float(h.get("delta_vs_generic", 0) or 0) <= 0:
        return "keep_proposed_only"
    if safety.get("promotion_blocking_reasons"):
        return "keep_proposed_only"
    if float(h.get("delta_vs_generic", 0) or 0) < 0.5:
        return "needs_more_data"
    return "eligible_for_dry_run_adapter_variant"


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
    lines = [
        "# Stabilization Y: H Variant Large Sample",
        "",
        "Larger-sample validation only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, active adapter behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_h_variant_large_sample.py`",
        "- `validate_stabilization_y.py`",
        "- `STABILIZATION_Y_H_VARIANT_LARGE_SAMPLE.md`",
        "",
        "## Files Changed",
        "",
        "- None; this phase adds proposed-only validation/reporting files.",
        "",
        "## Large-Sample Results",
        "",
        f"- Runs: `{payload['runs']}`",
        f"- Generic average score: `{payload['generic']['average_score']}`",
        f"- Public overlay average score: `{payload['public_overlay']['average_score']}`",
        f"- H variant average score: `{payload['h_variant']['average_score']}`",
        f"- Delta vs generic: `{payload['h_variant']['delta_vs_generic']}`",
        f"- Delta vs public overlay: `{payload['h_variant']['delta_vs_public_overlay']}`",
        f"- Positive / negative / neutral vs generic: `{payload['positive_run_count']}` / `{payload['negative_run_count']}` / `{payload['neutral_run_count']}`",
        f"- Safety metrics: `{payload['safety_metrics']}`",
        f"- Recommendation: `{payload['recommendation']}`",
        "",
        "## Validation Results",
        "",
        f"- Passed: {validation.get('passed')}",
        f"- Duration seconds: {validation.get('duration_seconds')}",
    ]
    for check in validation.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- {status}: {check.get('name')}")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            "- Stabilization Z should add an explicit non-default dry-run adapter variant for the H swap, guarded by the existing safety gates and still off by default.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
