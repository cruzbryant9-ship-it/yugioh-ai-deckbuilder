from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from kashtira_public_overlay_tuning_gate import TUNING_VARIANTS, run_tuning_gate, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_u.json"
PHASE_REPORT = Path("STABILIZATION_U_PUBLIC_OVERLAY_GENERIC_FILL_REDUCTION.md")


def main() -> None:
    checks = [
        ("all tuning variants are explicit-only", validate_variants_explicit_only),
        ("default Kashtira remains generic", validate_default_kashtira_generic),
        ("current experimental remains unchanged", validate_current_experimental_unchanged),
        ("public baseline overlay remains unchanged", validate_public_baseline_unchanged),
        ("tuning variants preserve legal interaction cards", validate_tuning_variants_preserve_interactions),
        ("tuning variants report generic-fill counts", validate_tuning_variants_report_generic_fill),
        ("no builder defaults changed", validate_no_builder_defaults_changed),
        ("Stabilization T validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_t", "validate_stabilization_t.py")),
        ("Stabilization R validator still passes", lambda: validate_prior_artifact_or_run("validate_stabilization_r", "validate_stabilization_r.py")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_u", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization U validation complete.")


def fresh_cards() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def deck_names(deck: list[dict[str, Any]]) -> set[str]:
    return {str(card.get("name", "")) for card in deck}


def validate_variants_explicit_only() -> dict[str, Any]:
    cards = fresh_cards()
    build_deck(cards, "Kashtira", mode="meta")
    default_report = get_last_build_report()
    if default_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(default_report)
    seen = {}
    for variant in TUNING_VARIANTS:
        build_deck(
            cards,
            "Kashtira",
            mode="meta",
            experimental_semi_specialized=True,
            specialization_profile="Kashtira",
            experimental_variant=variant,
        )
        report = get_last_build_report()
        if report.get("variant") != variant or report.get("dry_run_variant") is not True:
            raise AssertionError({"variant": variant, "report": report})
        seen[variant] = {
            "builder_used": report.get("builder_used"),
            "dry_run_variant": report.get("dry_run_variant"),
            "not_default": report.get("not_default"),
        }
    return {"default_builder": default_report.get("builder_used"), "variants": seen}


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
    if report.get("variant") not in {None, ""} or report.get("dry_run_variant") is True:
        raise AssertionError(report)
    if report.get("generic_report_used_for_fill", {}).get("public_overlay_tuning_variant"):
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "variant": report.get("variant"), "dry_run_variant": report.get("dry_run_variant")}


def validate_public_baseline_unchanged() -> dict[str, Any]:
    build_deck(
        fresh_cards(),
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="public_baseline_interaction_overlay",
    )
    report = get_last_build_report()
    counts = report.get("package_counts", {}) or {}
    if report.get("variant") != "public_baseline_interaction_overlay" or counts.get("archetype_fill"):
        raise AssertionError(report)
    return {
        "variant": report.get("variant"),
        "generic_fill_count": counts.get("generic_fill"),
        "archetype_fill_count": counts.get("archetype_fill", 0),
    }


def validate_tuning_variants_preserve_interactions() -> dict[str, Any]:
    expected = set(interaction_core_for("Kashtira"))
    details = {}
    for variant in TUNING_VARIANTS:
        deck, _pool = build_deck(
            fresh_cards(),
            "Kashtira",
            mode="meta",
            experimental_semi_specialized=True,
            specialization_profile="Kashtira",
            experimental_variant=variant,
        )
        report = get_last_build_report()
        selected = set((report.get("interaction_trace_metadata", {}) or {}).get("interaction_preservation_stage_selected_names", []))
        missing = sorted(expected - deck_names(deck))
        if missing or not expected <= selected:
            raise AssertionError({"variant": variant, "missing": missing, "selected": sorted(selected)})
        details[variant] = {"selected_count": len(selected), "final_missing": missing}
    return details


def validate_tuning_variants_report_generic_fill() -> dict[str, Any]:
    report = run_tuning_gate("meta", 1, 12345, frozen_cards=True)
    json_path, md_path = save_report(report)
    details = {}
    for variant in TUNING_VARIANTS:
        summary = report[variant]
        if "generic_fill_count" not in summary or summary.get("generic_fill_average") is None:
            raise AssertionError({"variant": variant, "summary": summary})
        if summary.get("interaction_selected_average", 0) < len(interaction_core_for("Kashtira")):
            raise AssertionError({"variant": variant, "summary": summary})
        details[variant] = {
            "generic_fill_average": summary.get("generic_fill_average"),
            "interaction_selected_average": summary.get("interaction_selected_average"),
            "recommendation": report["recommendations"].get(variant),
        }
    return {"json": str(json_path), "markdown": str(md_path), "variants": details}


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


def write_phase_report(payload: dict[str, Any]) -> None:
    report = run_tuning_gate("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    best = report["best_variant"]
    lines = [
        "# Stabilization U: Public Overlay Generic-Fill Pressure Reduction",
        "",
        "Dry-run/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `kashtira_public_overlay_tuning_gate.py`",
        "- `validate_stabilization_u.py`",
        "- `STABILIZATION_U_PUBLIC_OVERLAY_GENERIC_FILL_REDUCTION.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "",
        "## Variants Tested",
        "",
        "- `public_overlay_reduce_generic_fill`",
        "- `public_overlay_archetype_fill_priority`",
        "- `public_overlay_interaction_plus_archetype_core`",
        "",
        "## Results",
        "",
        f"- Generic average score: `{report['generic']['average_score']}`",
        f"- Best variant: `{best}`",
        f"- Best variant average score: `{report[best]['average_score']}`",
        f"- Best variant delta vs generic: `{report['score_delta_vs_generic'][best]}`",
        f"- Best variant generic-fill average: `{report[best]['generic_fill_average']}`",
        f"- Best variant interaction selected average: `{report[best]['interaction_selected_average']}`",
        f"- Best variant recommendation: `{report['recommendations'][best]}`",
        "",
        "## Variant Summary",
        "",
    ]
    for variant in TUNING_VARIANTS:
        lines.append(
            f"- `{variant}`: score `{report[variant]['average_score']}`, delta `{report['score_delta_vs_generic'][variant]}`, "
            f"generic fill `{report[variant]['generic_fill_average']}`, interaction `{report[variant]['interaction_selected_average']}`, "
            f"recommendation `{report['recommendations'][variant]}`"
        )
    lines.extend(
        [
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
            "## Recommended Next Step",
            "",
            "- Stabilization V should run a larger fixed-seed sample for `public_overlay_reduce_generic_fill` and inspect whether the score edge survives beyond the small dry-run gate.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
