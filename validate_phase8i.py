from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from deck.archetype_specialization_profiles import load_specialization_profile
from deck.builder import build_deck, get_last_build_report
from deck.semi_specialized_builder_adapter import add_legal_copy, build_experimental_semi_specialized_deck
from semi_specialized_experimental_comparison import build_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_json_report_exists, assert_markdown_report_exists, assert_success, run_checks, run_python, smoke_matchup_matrix


PHASE_REPORT = Path("PHASE8I_EXPERIMENTAL_KASHTIRA_BUILDER.md")
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase8i.json"
COMPARISON_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_experimental_comparison_report.json"
COMPARISON_MD = Path("SystemAIYugioh") / "data" / "training_runs" / "semi_specialization" / "latest_kashtira_experimental_comparison_report.md"


def main() -> None:
    checks = [
        ("default Kashtira path remains generic", validate_default_kashtira_generic),
        ("explicit flag can call experimental adapter", validate_explicit_experimental),
        ("Blue-Eyes authored path remains unchanged", validate_blue_eyes_authored),
        ("unsupported archetype cannot use experimental path", validate_unsupported_archetype),
        ("failed gates fallback to generic", validate_failed_gate_fallback),
        ("blocked cards are rejected", validate_blocked_cards_rejected),
        ("output marks experimental/not_default", validate_output_markers),
        ("comparison report generates", validate_comparison_report),
        ("Phase 8H validator still passes", validate_phase8h),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_phase8i", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Phase 8I validation complete.")


def validate_default_kashtira_generic() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_explicit_experimental() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta", experimental_semi_specialized=True, specialization_profile="Kashtira")
    report = get_last_build_report()
    if report.get("builder_used") != "semi_specialized_experimental" or report.get("fallback_used") is not False:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used"), "fallback_used": report.get("fallback_used")}


def validate_blue_eyes_authored() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"deck_size": len(deck), "builder_used": report.get("builder_used")}


def validate_unsupported_archetype() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, report = build_experimental_semi_specialized_deck(cards, "Blue-Eyes", mode="meta", profile="Blue-Eyes")
    if report.get("builder_used") == "semi_specialized_experimental" or report.get("fallback_used") is not True:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "fallback_used": report.get("fallback_used"), "warnings": report.get("quota_warnings", [])}


def validate_failed_gate_fallback() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, report = build_experimental_semi_specialized_deck(cards, "Kashtira", mode="meta", profile="Blue-Eyes")
    if report.get("builder_used") == "semi_specialized_experimental" or report.get("fallback_used") is not True:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "fallback_used": report.get("fallback_used"), "warnings": report.get("quota_warnings", [])}


def validate_blocked_cards_rejected() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    blocked_card = {"name": "Strength in Unity", "type": "Spell Card", "desc": ""}
    added = add_legal_copy([], counts, blocked_card)
    if added:
        raise AssertionError("blocked card was accepted")
    return {"blocked_card_rejected": True}


def validate_output_markers() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, report = build_experimental_semi_specialized_deck(cards, "Kashtira", mode="meta", profile="Kashtira")
    if report.get("experimental") is not True or report.get("not_default") is not True:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"experimental": report.get("experimental"), "not_default": report.get("not_default")}


def validate_comparison_report() -> dict[str, Any]:
    report = build_report("Kashtira", "meta", 2)
    save_report(report)
    assert_json_report_exists(COMPARISON_JSON, ("comparison", "semi_specialization_default_active"))
    assert_markdown_report_exists(COMPARISON_MD, ("Generic Summary", "Experimental Summary", "Regression recommendation"))
    return {"regression_recommendation": report["comparison"]["regression_recommendation"]}


def validate_phase8h() -> dict[str, Any]:
    result = run_python("validate_phase8h.py", timeout=9000)
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
    report = build_report("Kashtira", "meta", 5)
    save_report(report)
    comparison = report["comparison"]
    generic = comparison["generic_summary"]
    experimental = comparison["experimental_summary"]
    active_profile = load_specialization_profile("Kashtira")
    lines = [
        "# Phase 8I: Experimental Kashtira Builder Flag",
        "",
        "Explicit opt-in only. Semi-specialized building was not made default, Blue-Eyes authored behavior was not changed, other archetypes remain unsupported, and scoring, regression thresholds, memory influence, neural networks, reinforcement learning, self-play, duel engine features, and full combo graphs were not changed.",
        "",
        "## Files Created",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `semi_specialized_experimental_comparison.py`",
        "- `validate_phase8i.py`",
        "- `PHASE8I_EXPERIMENTAL_KASHTIRA_BUILDER.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/builder.py`",
        "- `yugioh_ai_deckbuilder.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Experimental Flag Behavior",
        "",
        "- Default Kashtira CLI/build path remains generic.",
        "- Experimental path requires `--experimental-semi-specialized --specialization-profile Kashtira`.",
        "- Unsupported archetypes or failed gates fall back to generic.",
        f"- Active profile still has Riseheart as active payoff: {'Kashtira Riseheart' in (active_profile or {}).get('payoffs', [])}",
        "",
        "## Generic vs Experimental Comparison",
        "",
        f"- Generic average score: {generic.get('average_score')}",
        f"- Experimental average score: {experimental.get('average_score')}",
        f"- Generic builders used: {', '.join(generic.get('builders_used', []))}",
        f"- Experimental builders used: {', '.join(experimental.get('builders_used', []))}",
        f"- Experimental fallback rate: {comparison.get('fallback_rate')}",
        f"- Regression recommendation: `{comparison.get('regression_recommendation')}`",
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
            "## Recommended Phase 8J",
            "",
            "- Add experimental regression gates comparing generic and explicit Kashtira experimental outputs across fixed seeds and frozen card pools.",
            "- Keep the experimental flag opt-in until repeated reports show no score, legality, fallback, or package-balance regressions.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
