from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from legacy_memory_review import (
    build_legacy_memory_review,
    scan_blocked_and_probe_terms,
    save_reports,
)
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.memory_quarantine import quarantine_memory_file
from SystemAIYugioh.validation_harness import assert_markdown_report_exists, assert_success, in_core_suite, run_checks, run_python, smoke_matchup_matrix


ROOT = Path(__file__).resolve().parent
PRODUCTION_MEMORY_DIR = ROOT / "SystemAIYugioh" / "data" / "deck_profiles"


def main() -> None:
    checks = [
        ("review tool runs", validate_review_runs),
        ("quarantine copies memory safely", validate_quarantine_copy),
        ("manifest is created", validate_quarantine_manifest),
        ("blocked-card scan works", validate_blocked_scan),
        ("recommendations are generated", validate_recommendations),
        ("no production memory is deleted automatically", validate_no_production_delete),
        ("learning_signal_audit.py still passes", validate_learning_signal_audit),
        ("Stabilization I validator still passes", validate_stabilization_i),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
        ("documentation exists", validate_documentation),
    ]
    result = run_checks(
        "validate_stabilization_j",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_j.json",
    )
    if not result.passed:
        raise SystemExit(1)
    print_sample()
    print("Stabilization J validation complete.")


def validate_review_runs() -> None:
    report = build_legacy_memory_review()
    if report.get("report_type") != "legacy_memory_review":
        raise AssertionError(report.get("report_type"))
    if len(report.get("memories", [])) < 10:
        raise AssertionError("expected all memory targets")


def validate_quarantine_copy() -> None:
    with TemporaryDirectory(prefix="stabilization_j_quarantine_") as folder:
        root = Path(folder)
        source = root / "memory.json"
        atomic_write_json(source, {"version": 1, "profiles": {"probe": {"meta": {"score": 1}}}})
        result = quarantine_memory_file(source, "validator copy test", quarantine_root=root / "quarantine")
        if not result.get("success"):
            raise AssertionError(result)
        copy_path = Path(result["quarantined_copy"])
        if not copy_path.exists():
            raise AssertionError(result)
        if safe_load_json(copy_path, {}) != safe_load_json(source, {}):
            raise AssertionError("quarantined copy differs from source")
        if not source.exists():
            raise AssertionError("source was deleted")


def validate_quarantine_manifest() -> None:
    with TemporaryDirectory(prefix="stabilization_j_manifest_") as folder:
        root = Path(folder)
        source = root / "memory.json"
        atomic_write_json(source, {"version": 1})
        result = quarantine_memory_file(source, "validator manifest test", quarantine_root=root / "quarantine")
        manifest = safe_load_json(result.get("manifest_path", ""), {})
        if manifest.get("source") != str(source) or manifest.get("original_deleted"):
            raise AssertionError(manifest)
        if not manifest.get("quarantined_copy"):
            raise AssertionError(manifest)


def validate_blocked_scan() -> None:
    scan = scan_blocked_and_probe_terms(
        {
            "profiles": {
                "Probe Archetype": {
                    "cards": ["Pot of Greed", "Helpful Add", {"name": "Strength in Unity"}]
                }
            }
        }
    )
    if scan["blocked"]["total_hits"] < 2:
        raise AssertionError(scan)
    if scan["probes"]["total_hits"] < 1:
        raise AssertionError(scan)


def validate_recommendations() -> None:
    report = build_legacy_memory_review()
    recommendations = [memory.get("recommendation") for memory in report.get("memories", [])]
    if not recommendations or any(not recommendation for recommendation in recommendations):
        raise AssertionError(recommendations)
    if not report.get("refresh_commands"):
        raise AssertionError("refresh commands missing")


def validate_no_production_delete() -> None:
    before = {path.name: path.exists() for path in PRODUCTION_MEMORY_DIR.glob("*.json")}
    build_legacy_memory_review()
    after = {path.name: path.exists() for path in PRODUCTION_MEMORY_DIR.glob("*.json")}
    missing = [name for name, existed in before.items() if existed and not after.get(name)]
    if missing:
        raise AssertionError(missing)


def validate_learning_signal_audit() -> None:
    if in_core_suite():
        return
    assert_success(run_python("learning_signal_audit.py", "--no-save"))


def validate_stabilization_i() -> None:
    if in_core_suite():
        return
    assert_success(run_python("validate_stabilization_i.py", timeout=900))


def validate_matrix_smoke() -> None:
    if in_core_suite():
        return
    assert_success(smoke_matchup_matrix(timeout=1800), ("Failed cells: 0",))


def validate_documentation() -> None:
    assert_markdown_report_exists(ROOT / "STABILIZATION_J_LEGACY_MEMORY_REVIEW.md", ("legacy_memory_review.py", "memory_quarantine", "refresh"))


def print_sample() -> None:
    report = build_legacy_memory_review()
    summary = report.get("summary", {})
    print("Sample refresh candidates:", summary.get("refresh_candidates", []))
    print("Sample quarantine candidates:", summary.get("quarantine_candidates", []))
    print("Sample stale memories:", summary.get("stale_memories", []))


if __name__ == "__main__":
    main()
