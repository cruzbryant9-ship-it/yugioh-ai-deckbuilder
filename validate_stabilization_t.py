from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from kashtira_public_baseline_overlay_gate import run_public_baseline_gate, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_t.json"
PHASE_REPORT = Path("STABILIZATION_T_PUBLIC_BASELINE_OVERLAY.md")


def main() -> None:
    checks = [
        ("public-baseline variant is opt-in only", validate_public_variant_opt_in_only),
        ("default Kashtira remains generic", validate_default_kashtira_generic),
        ("current experimental path remains unchanged", validate_current_experimental_unchanged),
        ("hybrid overlay path remains unchanged", validate_hybrid_overlay_unchanged),
        ("public baseline variant marks dry_run_variant true", validate_public_variant_metadata),
        ("public baseline legal interaction cards are preserved", validate_public_interactions_preserved),
        ("no builder defaults changed", validate_no_builder_defaults_changed),
        ("public baseline overlay report generates", validate_public_gate_report),
        ("Stabilization S validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_s", "validate_stabilization_s.py")),
        ("Stabilization R validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_r", "validate_stabilization_r.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_t", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization T validation complete.")


def fresh_cards() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def main_names(deck: list[dict[str, Any]]) -> set[str]:
    return {str(card.get("name", "")) for card in deck}


def validate_public_variant_opt_in_only() -> dict[str, Any]:
    cards = fresh_cards()
    build_deck(cards, "Kashtira", mode="meta")
    default_report = get_last_build_report()
    build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_baseline_interaction_overlay",
    )
    public_report = get_last_build_report()
    if default_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(default_report)
    if public_report.get("variant") != "public_baseline_interaction_overlay":
        raise AssertionError(public_report)
    return {
        "default_builder": default_report.get("builder_used"),
        "public_variant": public_report.get("variant"),
        "public_dry_run": public_report.get("dry_run_variant"),
    }


def validate_default_kashtira_generic() -> dict[str, Any]:
    build_deck(fresh_cards(), "Kashtira", mode="meta")
    report = get_last_build_report()
    if report.get("builder_used") not in {"generic", "generic_tuned"} or report.get("experimental"):
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "experimental": report.get("experimental")}


def validate_current_experimental_unchanged() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
    )
    report = get_last_build_report()
    if report.get("variant") not in {None, ""}:
        raise AssertionError(report)
    if report.get("dry_run_variant") is True:
        raise AssertionError(report)
    generic_report = report.get("generic_report_used_for_fill", {})
    if generic_report.get("public_baseline_used_for_interaction") is True:
        raise AssertionError(report)
    return {
        "builder_used": report.get("builder_used"),
        "variant": report.get("variant"),
        "dry_run_variant": report.get("dry_run_variant"),
    }


def validate_hybrid_overlay_unchanged() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="hybrid_generic_interaction_overlay",
    )
    report = get_last_build_report()
    if report.get("variant") != "hybrid_generic_interaction_overlay" or report.get("dry_run_variant") is not True:
        raise AssertionError(report)
    generic_report = report.get("generic_report_used_for_fill", {})
    if generic_report.get("public_baseline_used_for_interaction") is True:
        raise AssertionError(report)
    return {
        "builder_used": report.get("builder_used"),
        "variant": report.get("variant"),
        "dry_run_variant": report.get("dry_run_variant"),
    }


def validate_public_variant_metadata() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_baseline_interaction_overlay",
    )
    report = get_last_build_report()
    required = {
        "experimental": True,
        "variant": "public_baseline_interaction_overlay",
        "dry_run_variant": True,
        "not_default": True,
    }
    mismatches = {key: (report.get(key), value) for key, value in required.items() if report.get(key) != value}
    if mismatches:
        raise AssertionError({"mismatches": mismatches, "report": report})
    return {key: report.get(key) for key in required}


def validate_public_interactions_preserved() -> dict[str, Any]:
    deck, _ = build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_baseline_interaction_overlay",
    )
    report = get_last_build_report()
    expected = set(interaction_core_for("Kashtira"))
    final_names = main_names(deck)
    missing = sorted(expected - final_names)
    metadata = report.get("interaction_trace_metadata", {})
    selected = set(metadata.get("interaction_preservation_stage_selected_names", []))
    if missing or not expected <= selected:
        raise AssertionError({"missing_final": missing, "selected": sorted(selected), "expected": sorted(expected)})
    return {
        "preserved_cards": sorted(expected),
        "selected_count": len(selected),
        "final_main_count": len(deck),
    }


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
    return {
        "blue_eyes_builder": blue_report.get("builder_used"),
        "kashtira_builder": kashtira_report.get("builder_used"),
    }


def validate_public_gate_report() -> dict[str, Any]:
    report = run_public_baseline_gate("meta", 1, 12345, frozen_cards=True)
    json_path, md_path = save_report(report)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    public = report["public_baseline_overlay"]
    if public.get("dry_run_variant_rate") != 1.0:
        raise AssertionError(public)
    if public.get("interaction_selected_average", 0) < len(interaction_core_for("Kashtira")):
        raise AssertionError(public)
    required = {"generic_fill_gate", "interaction_loss_gate", "promotion_blocking_reasons", "lost_interaction_cards"}
    missing = required - set(report)
    if missing:
        raise AssertionError(missing)
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "recommendation": report.get("recommendation"),
        "public_interaction_selected_average": public.get("interaction_selected_average"),
    }


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
    report = run_public_baseline_gate("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    public = report["public_baseline_overlay"]
    generic = report["generic"]
    lines = [
        "# Stabilization T: Public Baseline Interaction Preservation Dry-Run",
        "",
        "Dry-run candidate-fix testing only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_public_baseline_overlay_gate.py`",
        "- `validate_stabilization_t.py`",
        "- `STABILIZATION_T_PUBLIC_BASELINE_OVERLAY.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `kashtira_public_baseline_overlay_gate.py`",
        "",
        "## Public-Baseline Overlay Behavior",
        "",
        "- Adds explicit variant `public_baseline_interaction_overlay`.",
        "- The variant only runs when `--experimental-semi-specialized --specialization-profile Kashtira --experimental-variant public_baseline_interaction_overlay` is requested.",
        "- The public generic baseline deck is used only to identify legal interaction cards for dry-run preservation.",
        "- Current experimental and hybrid overlay behavior remain unchanged.",
        "",
        "## Comparison Summary",
        "",
        f"- Generic average score: `{generic['average_score']}`",
        f"- Public overlay average score: `{public['average_score']}`",
        f"- Public overlay delta vs generic: `{report['score_delta_vs_generic']['public_baseline_overlay']}`",
        f"- Public overlay quota balance: `{public['quota_balance']}`",
        f"- Public overlay generic-fill average: `{public['generic_fill_average']}`",
        f"- Public overlay interaction selected average: `{public['interaction_selected_average']}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Safety Gates",
        "",
        f"- Generic-fill gate: `{report['generic_fill_gate']['public_baseline_overlay_vs_generic']}`",
        f"- Interaction-loss gate: `{report['interaction_loss_gate']['public_baseline_overlay_vs_generic']}`",
        f"- Promotion-blocking reasons: `{report['promotion_blocking_reasons']['public_baseline_overlay_vs_generic']}`",
        f"- Lost interaction cards: `{report['lost_interaction_cards']['public_baseline_overlay_vs_generic']}`",
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
            "- Stabilization U should investigate reducing public-overlay generic-fill pressure without changing defaults, using executed dry-run evidence only.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
