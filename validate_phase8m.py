from __future__ import annotations

from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from kashtira_hybrid_overlay_regression_gate import run_hybrid_gate, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8M_HYBRID_OVERLAY_DRY_RUN.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8m.json"
HYBRID_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_hybrid_overlay_regression_gate.json"
HYBRID_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_hybrid_overlay_regression_gate.md"


def main() -> None:
    checks = [
        ("normal Kashtira remains generic", validate_normal_generic),
        ("default experimental Kashtira remains unchanged", validate_default_experimental),
        ("hybrid variant only runs with explicit variant flag", validate_hybrid_explicit),
        ("output marks dry_run_variant true", validate_dry_run_marker),
        ("Blue-Eyes authored behavior remains untouched", validate_blue_eyes),
        ("unsupported variants fallback or fail safely", validate_unsupported_variant),
        ("legality remains clean", validate_legality),
        ("hybrid report generates", validate_report),
        ("Phase 8L validator still passes", validate_phase8l),
        ("Phase 8J validator still passes", validate_phase8j),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8m", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8M validation complete.")


def validate_normal_generic() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_default_experimental() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta", experimental_semi_specialized=True, specialization_profile="Kashtira")
    report = get_last_build_report()
    if report.get("variant") is not None or report.get("dry_run_variant") is True:
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "variant": report.get("variant"), "deck_size": len(deck)}


def validate_hybrid_explicit() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="hybrid_generic_interaction_overlay",
    )
    report = get_last_build_report()
    if report.get("variant") != "hybrid_generic_interaction_overlay":
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "variant": report.get("variant"), "deck_size": len(deck)}


def validate_dry_run_marker() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(cards, "Kashtira", mode="meta", experimental_semi_specialized=True, specialization_profile="Kashtira", experimental_variant="hybrid_generic_interaction_overlay")
    report = get_last_build_report()
    if report.get("dry_run_variant") is not True or report.get("not_default") is not True:
        raise AssertionError(report)
    return {"dry_run_variant": report.get("dry_run_variant"), "not_default": report.get("not_default")}


def validate_blue_eyes() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if report.get("builder_used") != "authored":
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_unsupported_variant() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(cards, "Kashtira", mode="meta", experimental_semi_specialized=True, specialization_profile="Kashtira", experimental_variant="unknown_variant")
    report = get_last_build_report()
    if report.get("builder_used") == "semi_specialized_experimental" and report.get("fallback_used") is not True:
        raise AssertionError(report)
    return {"builder_used": report.get("builder_used"), "fallback_used": report.get("fallback_used"), "warnings": report.get("quota_warnings", [])}


def validate_legality() -> dict[str, Any]:
    report = run_hybrid_gate("meta", 2, 12345, frozen_cards=True)
    if report["hybrid_overlay"]["legality_rate"] != 1.0 or report["hybrid_overlay"]["blocked_card_violations"]:
        raise AssertionError(report["hybrid_overlay"])
    return {"legality_rate": report["hybrid_overlay"]["legality_rate"], "fallback_rate": report["hybrid_overlay"]["fallback_rate"]}


def validate_report() -> dict[str, Any]:
    report = run_hybrid_gate("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    assert_json_report_exists(HYBRID_JSON, ("generic", "current_experimental", "hybrid_overlay", "recommendation"))
    assert_markdown_report_exists(HYBRID_MD, ("Generic", "Current Experimental", "Hybrid Overlay"))
    return {"recommendation": report["recommendation"], "hybrid_delta": report["hybrid_score_delta_vs_generic"]}


def validate_phase8l() -> dict[str, Any]:
    result = run_python("validate_phase8l.py", timeout=1800)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_phase8j() -> dict[str, Any]:
    result = run_python("validate_phase8j.py", timeout=9000)
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
    report = run_hybrid_gate("meta", 10, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Phase 8M: Hybrid Overlay Dry-Run Adapter Branch",
        "",
        "Explicit dry-run branch only. No default behavior, current experimental behavior, generic builder behavior, scoring weights, regression thresholds, Blue-Eyes authored behavior, memory influence, neural networks, reinforcement learning, self-play, duel engine features, or full combo graphs were changed.",
        "",
        "## Files Created",
        "",
        "- `kashtira_hybrid_overlay_regression_gate.py`",
        "- `validate_phase8m.py`",
        "- `PHASE8M_HYBRID_OVERLAY_DRY_RUN.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `deck/builder.py`",
        "- `yugioh_ai_deckbuilder.py`",
        "",
        "## Dry-Run Branch Behavior",
        "",
        "- Normal Kashtira remains generic.",
        "- Current explicit experimental Kashtira remains available without a variant.",
        "- Hybrid overlay requires `--experimental-variant hybrid_generic_interaction_overlay`.",
        "",
        "## Comparison",
        "",
        f"- Generic average score: {report['generic']['average_score']}",
        f"- Current experimental average score: {report['current_experimental']['average_score']}",
        f"- Hybrid average score: {report['hybrid_overlay']['average_score']}",
        f"- Hybrid delta vs generic: {report['hybrid_score_delta_vs_generic']}",
        f"- Hybrid delta vs current experimental: {report['hybrid_score_delta_vs_current_experimental']}",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "## Validation Results",
        "",
        f"- Passed: {payload.get('passed')}",
        f"- Duration seconds: {payload.get('duration_seconds')}",
    ]
    for check in payload.get("checks", []):
        lines.append(f"- {'PASS' if check.get('passed') else 'FAIL'}: {check.get('name')}")
    lines.extend([
        "",
        "## Recommended Phase 8N",
        "",
        "- Run a larger fixed-seed sample for the hybrid dry-run branch and inspect whether its score edge remains stable before touching the active experimental adapter.",
    ])
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
