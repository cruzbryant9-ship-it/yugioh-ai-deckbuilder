from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from kashtira_interaction_preservation_trace import build_report, save_report
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python, smoke_matchup_matrix


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_s.json"
PHASE_REPORT = Path("STABILIZATION_S_INTERACTION_PRESERVATION_TRACE.md")


def main() -> None:
    checks = [
        ("trace module runs", validate_trace_module),
        ("adapter emits trace metadata", validate_adapter_trace_metadata),
        ("trace runner generates JSON/Markdown", validate_trace_runner),
        ("each registry interaction card has a trace", validate_all_registry_cards_traced),
        ("failure classification is present", validate_failure_classification),
        ("no selection behavior changed", validate_no_selection_behavior_changed),
        ("Stabilization R validator still passes", lambda: validate_prior_artifact("validate_stabilization_r")),
        ("Stabilization Q validator still passes", lambda: validate_prior_artifact("validate_stabilization_q")),
        ("Phase 8A validator still passes", validate_phase8a),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_s", checks, json_path=VALIDATION_JSON)
    write_phase_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization S validation complete.")


def validate_trace_module() -> dict[str, Any]:
    report = build_report("meta", 1, 12345, frozen_cards=True)
    if not report.get("card_traces") or report.get("selection_behavior_changed") is not False:
        raise AssertionError(report)
    return {"trace_count": len(report["card_traces"]), "not_activated": report.get("not_activated")}


def validate_adapter_trace_metadata() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    build_deck(
        cards,
        "Kashtira",
        mode="meta",
        experimental_semi_specialized=True,
        specialization_profile="Kashtira",
        experimental_variant="hybrid_generic_interaction_overlay",
    )
    report = get_last_build_report()
    metadata = report.get("interaction_trace_metadata", {})
    required = {
        "quota_stage_selected_names",
        "interaction_preservation_stage_selected_names",
        "interaction_preservation_stage_rejected_names",
        "interaction_preservation_stage_rejection_reasons",
        "generic_fill_stage_selected_names",
        "internal_generic_baseline_main_names",
        "final_main_names",
    }
    missing = required - set(metadata)
    if missing:
        raise AssertionError({"missing": sorted(missing), "metadata": metadata})
    return {key: len(metadata.get(key, [])) for key in sorted(required)}


def validate_trace_runner() -> dict[str, Any]:
    report = build_report("meta", 1, 12345, frozen_cards=True)
    json_path, md_path = save_report(report)
    if not json_path.exists() or not md_path.exists():
        raise AssertionError((json_path, md_path))
    return {"json": str(json_path), "markdown": str(md_path), "runs": report["runs"]}


def validate_all_registry_cards_traced() -> dict[str, Any]:
    report = build_report("meta", 1, 12345, frozen_cards=True)
    traced = {row["card"] for row in report["card_traces"]}
    expected = set(interaction_core_for("Kashtira"))
    if traced != expected:
        raise AssertionError({"traced": sorted(traced), "expected": sorted(expected)})
    return {"cards": sorted(traced)}


def validate_failure_classification() -> dict[str, Any]:
    report = build_report("meta", 1, 12345, frozen_cards=True)
    classifications = {row["card"]: row["failure_classification"] for row in report["card_traces"]}
    for card, values in classifications.items():
        if not values or "preservation_stage_noop" not in values:
            raise AssertionError(classifications)
    return classifications


def validate_no_selection_behavior_changed() -> dict[str, Any]:
    report = build_report("meta", 1, 12345, frozen_cards=True)
    cards = CardDatabase().load_cards()
    build_deck(cards, "Blue-Eyes", mode="meta")
    blue_report = get_last_build_report()
    build_deck(cards, "Kashtira", mode="meta")
    kashtira_report = get_last_build_report()
    if report.get("selection_behavior_changed") is not False or report.get("not_activated") is not True:
        raise AssertionError(report)
    if blue_report.get("builder_used") != "authored":
        raise AssertionError(blue_report)
    if kashtira_report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError(kashtira_report)
    return {
        "trace_selection_behavior_changed": report["selection_behavior_changed"],
        "blue_eyes_builder": blue_report.get("builder_used"),
        "kashtira_builder": kashtira_report.get("builder_used"),
    }


def validate_prior_artifact(name: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if not path.exists():
        raise AssertionError(f"missing prior validator artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise AssertionError(payload)
    return {"artifact": str(path), "passed": payload.get("passed"), "duration_seconds": payload.get("duration_seconds")}


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
    report = build_report("meta", 2, 12345, frozen_cards=True)
    save_report(report)
    lines = [
        "# Stabilization S: Interaction Preservation Failure Trace",
        "",
        "Trace/reporting only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.",
        "",
        "## Files Created",
        "",
        "- `deck/interaction_preservation_trace.py`",
        "- `kashtira_interaction_preservation_trace.py`",
        "- `validate_stabilization_s.py`",
        "- `STABILIZATION_S_INTERACTION_PRESERVATION_TRACE.md`",
        "",
        "## Files Changed",
        "",
        "- `deck/semi_specialized_builder_adapter.py`",
        "- `SystemAIYugioh/fingerprint_coverage_audit.py`",
        "",
        "## Trace Results",
        "",
    ]
    for row in report["card_traces"]:
        lines.extend(
            [
                f"- `{row['card']}`",
                f"  - Available/legal: `{row['available_in_pool']}` / `{row['legal']}`",
                f"  - Generic/experimental/hybrid counts: `{row['generic_count']}` / `{row['experimental_count']}` / `{row['hybrid_count']}`",
                f"  - Classification: `{', '.join(row['failure_classification'])}`",
                f"  - Rejection stage: `{row['rejection_stage']}`",
                f"  - Rejection reason: `{row['rejection_reason'] or 'none'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Failure Classification",
            "",
            "- Interaction cards are available in the card pool and legal.",
            "- The normal generic build contains the registry interaction cards.",
            "- The current experimental path does not select them in profile quota roles.",
            "- The hybrid path attempts preservation, but its internal generic baseline contains zero copies, so preservation is a no-op.",
            "- The cards are skipped, not unavailable, illegal, displaced after selection, or truncated after final selection.",
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
            "- Stabilization T should design a report-only candidate fix that compares using the public generic baseline interaction set, then test it behind an explicit non-default dry-run path before any adapter behavior changes.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
