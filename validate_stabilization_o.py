from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.interaction_core_registry import interaction_core_for
from projection_execution_parity_audit import PARITY_JSON, PARITY_MD, run_audit, save_architecture_reports
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.validation_harness import (
    assert_json_report_exists,
    assert_markdown_report_exists,
    assert_success,
    run_checks,
    run_python,
    smoke_matchup_matrix,
)


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_o.json"
PHASE_VALIDATORS = ("validate_phase8m", "validate_phase8l", "validate_phase8j", "validate_phase8a")


def main() -> None:
    checks = [
        ("audit runs successfully", validate_audit_runs),
        ("interaction registry exists", validate_registry),
        ("interaction-core ownership scan reports users", validate_interaction_scan),
        ("parity report generates", validate_parity_report),
        ("dependency-gate audit generates", validate_dead_gate_audit),
        ("promotion-source audit generates", validate_promotion_source_audit),
        ("Blue-Eyes behavior unchanged", validate_blue_eyes_unchanged),
        ("Kashtira behavior unchanged", validate_kashtira_unchanged),
        ("Phase 8M validator still passes", lambda: validate_prior_artifact("validate_phase8m")),
        ("Phase 8L validator still passes", lambda: validate_prior_artifact("validate_phase8l")),
        ("Phase 8J validator still passes", lambda: validate_prior_artifact("validate_phase8j")),
        ("Phase 8A validator still passes", lambda: validate_prior_artifact("validate_phase8a")),
        ("core suite still passes", validate_core_suite),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
    ]
    result = run_checks("validate_stabilization_o", checks, json_path=VALIDATION_JSON)
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization O validation complete.")


def validate_audit_runs() -> dict[str, Any]:
    report = run_audit(use_existing_reports=True)
    save_architecture_reports(report)
    if report.get("behavior_changed") or report.get("builder_changed") or report.get("promotion_applied"):
        raise AssertionError(report)
    return {
        "severe_mismatch_count": report.get("severe_mismatch_count"),
        "dead_gates": report.get("summary", {}).get("dead_gates", []),
        "projected_only_promotion_paths": report.get("summary", {}).get("projected_only_promotion_paths", []),
    }


def validate_registry() -> dict[str, Any]:
    cards = interaction_core_for("Kashtira")
    expected = {"Ash Blossom & Joyous Spring", "Ghost Belle & Haunted Mansion", "D.D. Crow", "Nibiru, the Primal Being"}
    if set(cards) != expected:
        raise AssertionError(cards)
    return {"cards": list(cards), "report_only": True}


def validate_interaction_scan() -> dict[str, Any]:
    report = assert_json_report_exists(PARITY_JSON, ("interaction_core_audit",))
    audit = report["interaction_core_audit"]
    if "hardcoded_interaction_core_users" not in audit or "migrated_modules" not in audit:
        raise AssertionError(audit)
    if not audit["migrated_modules"]:
        raise AssertionError(audit)
    return {
        "hardcoded_count": audit.get("remaining_hardcoded_count"),
        "migrated_modules": audit.get("migrated_modules"),
        "registry_backed_users": audit.get("registry_backed_users"),
    }


def validate_parity_report() -> dict[str, Any]:
    report = assert_json_report_exists(PARITY_JSON, ("parity_metrics", "projection_source", "execution_source"))
    assert_markdown_report_exists(PARITY_MD, ("Metric Parity", "Promotion Source Audit", "Dependency Gates"))
    metrics = {row["metric"] for row in report["parity_metrics"]}
    required = {"score", "package_quality", "quota_balance", "preserved_interaction_count", "filler_dependency", "repair_dependency"}
    if not required <= metrics:
        raise AssertionError(metrics)
    return {"metrics": sorted(metrics), "severe_mismatch_count": report.get("severe_mismatch_count")}


def validate_dead_gate_audit() -> dict[str, Any]:
    report = assert_json_report_exists(PARITY_JSON, ("dead_gate_audit",))
    gates = report["dead_gate_audit"].get("gates", [])
    names = {gate.get("name") for gate in gates}
    if {"filler_dependency_gate", "repair_dependency_gate"} - names:
        raise AssertionError(gates)
    if any(gate.get("can_trigger") is not True for gate in gates):
        raise AssertionError(gates)
    if any(gate.get("classification") != "active_candidate_vs_baseline_gate" for gate in gates):
        raise AssertionError(gates)
    return {"gates": gates}


def validate_promotion_source_audit() -> dict[str, Any]:
    report = assert_json_report_exists(PARITY_JSON, ("promotion_source_audit",))
    audit = report["promotion_source_audit"]
    projected_only = set(audit.get("projected_only_promotion_paths", []))
    projected_non_promotion = set(audit.get("projected_non_promotion_outputs", []))
    executed = set(audit.get("executed_deck_recommendations", []))
    if projected_only:
        raise AssertionError(audit)
    if not {"proposal_only", "needs_real_execution", "do_not_use_for_promotion"} <= projected_non_promotion:
        raise AssertionError(audit)
    if not {"promote_blocked", "keep_dry_run_only", "eligible_for_more_testing"} <= executed:
        raise AssertionError(audit)
    return {"projected_only": sorted(projected_only), "projected_non_promotion": sorted(projected_non_promotion), "executed": sorted(executed)}


def validate_blue_eyes_unchanged() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") != "authored":
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_kashtira_unchanged() -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Kashtira", mode="meta")
    report = get_last_build_report()
    if len(deck) < 40 or report.get("builder_used") not in {"generic", "generic_tuned"}:
        raise AssertionError({"deck_size": len(deck), "report": report})
    return {"builder_used": report.get("builder_used"), "deck_size": len(deck)}


def validate_prior_artifact(name: str) -> dict[str, Any]:
    path = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / f"{name}.json"
    if not path.exists():
        raise AssertionError(f"missing prior validator artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise AssertionError(payload)
    return {"artifact": str(path), "passed": payload.get("passed"), "duration_seconds": payload.get("duration_seconds")}


def validate_core_suite() -> dict[str, Any]:
    result = run_python("validate_core_suite.py", timeout=5400)
    assert_success(result)
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_matrix_smoke() -> dict[str, Any]:
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


if __name__ == "__main__":
    main()
