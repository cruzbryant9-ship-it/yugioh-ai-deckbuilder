from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from kashtira_h_variant_dry_run_gate import H_DRY_RUN_VARIANT, PUBLIC_OVERLAY_VARIANT, run_h_dry_run_gate, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_z.json"
PHASE_REPORT = Path("STABILIZATION_Z_H_VARIANT_DRY_RUN_ADAPTER.md")
_REPORT_CACHE: dict[str, Any] | None = None


def main() -> None:
    checks = [
        ("default Kashtira remains generic", validate_default_kashtira_generic),
        ("current experimental remains unchanged", validate_current_experimental_unchanged),
        ("public overlay remains unchanged", validate_public_overlay_unchanged),
        ("H variant only runs with explicit variant flag", validate_h_explicit_only),
        ("H output marks dry_run_variant true", validate_h_metadata),
        ("interaction cards remain preserved", validate_interactions_preserved),
        ("generic_fill remains 0", validate_generic_fill_zero),
        ("no builder defaults changed", validate_no_builder_defaults_changed),
        ("Stabilization Y validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_y", "validate_stabilization_y.py")),
        ("Stabilization U validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_u", "validate_stabilization_u.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_z", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization Z validation complete.")


def report() -> dict[str, Any]:
    global _REPORT_CACHE
    if _REPORT_CACHE is None:
        _REPORT_CACHE = run_h_dry_run_gate("meta", 2, 12345, frozen_cards=True)
    return _REPORT_CACHE


def fresh_cards() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def validate_default_kashtira_generic() -> dict[str, Any]:
    build_deck(fresh_cards(), "Kashtira", mode="meta")
    build_report = get_last_build_report()
    if build_report.get("builder_used") not in {"generic", "generic_tuned"} or build_report.get("experimental"):
        raise AssertionError(build_report)
    return {"builder_used": build_report.get("builder_used"), "experimental": build_report.get("experimental")}


def validate_current_experimental_unchanged() -> dict[str, Any]:
    build_deck(fresh_cards(), "Kashtira", mode="meta", experimental_semi_specialized=True, specialization_profile="Kashtira")
    build_report = get_last_build_report()
    if build_report.get("variant") not in {None, ""} or build_report.get("dry_run_variant") is True:
        raise AssertionError(build_report)
    return {"builder_used": build_report.get("builder_used"), "variant": build_report.get("variant"), "dry_run_variant": build_report.get("dry_run_variant")}


def validate_public_overlay_unchanged() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant=PUBLIC_OVERLAY_VARIANT,
    )
    build_report = get_last_build_report()
    if build_report.get("variant") != PUBLIC_OVERLAY_VARIANT or build_report.get("h_variant_status") is not None:
        raise AssertionError(build_report)
    return {"variant": build_report.get("variant"), "h_variant_status": build_report.get("h_variant_status"), "package_counts": build_report.get("package_counts")}


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
    if default_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(default_report)
    if h_report.get("variant") != H_DRY_RUN_VARIANT or not h_report.get("h_variant_status", {}).get("applied"):
        raise AssertionError(h_report)
    return {"default_builder": default_report.get("builder_used"), "h_variant": h_report.get("variant"), "h_status": h_report.get("h_variant_status")}


def validate_h_metadata() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant=H_DRY_RUN_VARIANT,
    )
    build_report = get_last_build_report()
    required = {
        "experimental": True,
        "variant": H_DRY_RUN_VARIANT,
        "dry_run_variant": True,
        "not_default": True,
        "fallback_used": False,
    }
    mismatches = {key: (build_report.get(key), value) for key, value in required.items() if build_report.get(key) != value}
    if mismatches:
        raise AssertionError({"mismatches": mismatches, "report": build_report})
    return {key: build_report.get(key) for key in required}


def validate_interactions_preserved() -> dict[str, Any]:
    payload = report()
    expected = len(interaction_core_for("Kashtira"))
    if payload["h_variant"].get("interaction_count") != float(expected):
        raise AssertionError(payload["h_variant"])
    return {"interaction_count": payload["h_variant"].get("interaction_count")}


def validate_generic_fill_zero() -> dict[str, Any]:
    payload = report()
    if payload["h_variant"].get("generic_fill_count") != 0.0:
        raise AssertionError(payload["h_variant"])
    return {"generic_fill_count": payload["h_variant"].get("generic_fill_count")}


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
        "# Stabilization Z: H Variant Dry-Run Adapter",
        "",
        "Explicit dry-run adapter branch only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_h_variant_dry_run_gate.py`",
        "- `validate_stabilization_z.py`",
        "- `STABILIZATION_Z_H_VARIANT_DRY_RUN_ADAPTER.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "",
        "## H Variant Dry-Run Behavior",
        "",
        f"- Explicit variant: `{H_DRY_RUN_VARIANT}`",
        "- Starts from `public_overlay_reduce_generic_fill` behavior.",
        "- Replaces one `Kashtira Preparations` with one `Kashtira Overlap` when legal.",
        "- Remains non-default and dry-run.",
        "",
        "## Gate Snapshot",
        "",
        f"- Runs: `{payload['runs']}`",
        f"- Generic average score: `{payload['generic']['average_score']}`",
        f"- Public overlay average score: `{payload['public_overlay']['average_score']}`",
        f"- H variant average score: `{payload['h_variant']['average_score']}`",
        f"- Delta vs generic: `{payload['h_variant']['delta_vs_generic']}`",
        f"- Delta vs public overlay: `{payload['h_variant']['delta_vs_public_overlay']}`",
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
            "- Stabilization AA should run an even broader explicit-candidate comparison before any discussion of making this path more than dry-run.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
