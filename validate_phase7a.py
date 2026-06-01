from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark_determinism_check import run_determinism_check
from cache_parity_check import run_cache_parity
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.source_fingerprint import SCORE_AFFECTING_SOURCE_FILES, source_fingerprint
from SystemAIYugioh.validation_harness import assert_success, in_core_suite, run_checks, run_python, smoke_matchup_matrix


ROOT = Path(__file__).resolve().parent
PHASE_REPORT = ROOT / "PHASE7A_BENCHMARK_AND_CACHE_TRUST.md"


def main() -> None:
    checks = [
        ("source fingerprint generation works", validate_source_fingerprint_generation),
        ("source edits invalidate cache", validate_source_edit_invalidates_cache),
        ("cold and warm cache parity passes", validate_cache_parity),
        ("determinism checks pass", validate_determinism),
        ("existing validators still pass", validate_existing_validators),
        ("matchup matrix smoke still passes", validate_matchup_matrix_smoke),
    ]
    result = run_checks(
        "validate_phase7a",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_phase7a.json",
    )
    write_phase_report({check.name: check.details if check.passed else {"ok": False, "error": check.error} for check in result.checks})
    if not result.passed:
        raise SystemExit(1)
    print("Phase 7A validation complete.")


def validate_source_fingerprint_generation() -> dict[str, object]:
    fingerprint = source_fingerprint()
    missing = [path for path in SCORE_AFFECTING_SOURCE_FILES if path not in fingerprint.get("files", {})]
    if missing:
        raise AssertionError(missing)
    if not fingerprint.get("source_hash") or fingerprint.get("file_count", 0) < len(SCORE_AFFECTING_SOURCE_FILES):
        raise AssertionError(fingerprint)
    return {"ok": True, "file_count": fingerprint["file_count"], "source_hash": fingerprint["source_hash"]}


def validate_source_edit_invalidates_cache() -> dict[str, object]:
    base = source_fingerprint()
    edited = copy.deepcopy(base)
    first_file = next(iter(edited["files"]))
    edited["files"][first_file]["sha256"] = "phase7a-edited-source-probe"
    edited["fingerprint"] = "phase7a-edited-fingerprint"
    with TemporaryDirectory(prefix="phase7a_cache_invalidation_") as folder:
        base_cache = MatrixCache(cache_dir=folder, enabled=True, fingerprint={"fingerprint": "base", "source_fingerprint": base, "parts": {"source_fingerprint": base}})
        edited_cache = MatrixCache(cache_dir=folder, enabled=True, fingerprint={"fingerprint": "edited", "source_fingerprint": edited, "parts": {"source_fingerprint": edited}})
        base_key = base_cache.key(archetype="Blue-Eyes", source_fingerprint=base["fingerprint"])
        edited_key = edited_cache.key(archetype="Blue-Eyes", source_fingerprint=edited["fingerprint"])
        if base_key == edited_key:
            raise AssertionError("cache key did not change after source fingerprint changed")
        base_cache.set(base_key, authoritative_probe_cell())
        if edited_cache.get(edited_key) is not None:
            raise AssertionError("edited fingerprint unexpectedly hit stale cache")
    return {"ok": True, "base_file": first_file, "base_key": base_key, "edited_key": edited_key}


def authoritative_probe_cell() -> dict[str, object]:
    return {
        "engine_variant": "pure",
        "matchup": "validator",
        "going": "both",
        "successful_runs": 1,
        "failed_runs": 0,
        "failed_cell": False,
        "failure_rate": 0,
        "average_final_score": 1,
        "best_score": 1,
        "blocked_card_violations": [],
        "runs": [{"ok": True}],
    }


def validate_cache_parity() -> dict[str, object]:
    report = run_cache_parity()
    if report.get("mismatched_cells"):
        raise AssertionError(report.get("mismatch_reasons"))
    return {"ok": True, "matched_cells": report.get("matched_cells"), "best_engine": report.get("best_engine_warm")}


def validate_determinism() -> dict[str, object]:
    report = run_determinism_check()
    if not report.get("same_seed_same_result"):
        raise AssertionError(report.get("unexpected_randomness"))
    return {"ok": True, "score_drift": report.get("score_drift"), "engine_drift": report.get("engine_drift"), "deck_drift": report.get("deck_drift")}


def validate_existing_validators() -> dict[str, object]:
    if in_core_suite():
        return {"ok": True, "skipped": "core suite runs migrated validators once"}
    result = run_python("validate_stabilization_m.py", timeout=3000)
    assert_success(result)
    return {"ok": True, "validator": "validate_stabilization_m.py"}


def validate_matchup_matrix_smoke() -> dict[str, object]:
    if in_core_suite():
        return {"ok": True, "skipped": "core suite runs matrix smoke once"}
    result = smoke_matchup_matrix(timeout=1800)
    assert_success(result, ("Failed cells: 0",))
    return {"ok": True, "failed_cells": 0}


def write_phase_report(results: dict[str, object]) -> None:
    source = source_fingerprint()
    parity = results.get("cold and warm cache parity passes", {})
    determinism = results.get("determinism checks pass", {})
    lines = [
        "# Phase 7A: Benchmark & Cache Trust",
        "",
        "Infrastructure-only phase. No gameplay, scoring, deck construction, Blue-Eyes authored behavior, memory influence, regression threshold, filler-memory, or opponent-influence changes were made.",
        "",
        "## Fingerprint Coverage",
        "",
        f"- Source fingerprint version: {source.get('version')}",
        f"- Source hash: `{source.get('source_hash')}`",
        f"- Covered files: {source.get('file_count')}",
    ]
    lines.extend(f"- `{path}`" for path in SCORE_AFFECTING_SOURCE_FILES)
    lines.extend(
        [
            "",
            "## Cache Invalidation Coverage",
            "",
            "- Matrix cache fingerprints now include deterministic content hashes for score-affecting source files.",
            "- Matrix cache keys also include the active source fingerprint and benchmark seed when provided.",
            "- Source-only changes invalidate stale matrix cache entries without requiring manual `CACHE_VERSION` bumps.",
            f"- Validation: {results.get('source edits invalidate cache', {})}",
            "",
            "## Parity Results",
            "",
            f"- Matched cells: {getattr(parity, 'get', lambda *_: 'unknown')('matched_cells')}",
            f"- Best warm engine: {getattr(parity, 'get', lambda *_: 'unknown')('best_engine')}",
            "- Detailed report: `CACHE_PARITY_REPORT.md`",
            "",
            "## Determinism Results",
            "",
            f"- Score drift: {getattr(determinism, 'get', lambda *_: 'unknown')('score_drift')}",
            f"- Engine drift: {getattr(determinism, 'get', lambda *_: 'unknown')('engine_drift')}",
            f"- Deck drift: {getattr(determinism, 'get', lambda *_: 'unknown')('deck_drift')}",
            "",
            "## Cache Provenance",
            "",
            "- Matrix reports include `cache_fingerprint` and `source_fingerprint`.",
            "- Matrix cells include `cache_hit`, `cache_generation_time`, `cache_created_timestamp`, `cache_fingerprint`, and `source_fingerprint`.",
            "",
            "## Remaining Risks",
            "",
            "- Determinism is guaranteed only when a seed is provided for benchmark trust checks.",
            "- Existing non-seeded CLI runs may still intentionally explore random weighted deck/package choices.",
            "- Persistent cache trust depends on all future score-affecting modules being added to `SCORE_AFFECTING_SOURCE_FILES`.",
        ]
    )
    atomic_write_text(PHASE_REPORT, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
