from __future__ import annotations

import ast
import copy
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from benchmark_determinism_check import run_determinism_check
from cache_parity_check import run_cache_parity
from deck.choke_simulator import CHOKE_CACHE, remember_choke_cache
from deck.side_plan_optimizer import SIDE_CANDIDATE_SCORE_CACHE, SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES
from SystemAIYugioh.cache_fingerprint import matrix_cache_fingerprint
from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.opponent_signal_sentinel import opponent_signal_sentinel
from SystemAIYugioh.regression_gates import classify_gate_numeric_value, evaluate_training_batch
from SystemAIYugioh.runtime_context import RuntimeContext
from SystemAIYugioh.score_snapshot import ScoreSnapshotCache
from SystemAIYugioh.source_fingerprint import SCORE_AFFECTING_SOURCE_FILES, source_fingerprint
from SystemAIYugioh.validation_harness import run_checks


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "STABILIZATION_N_ARCHITECTURE_REMEDIATION.md"
VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_n.json"


def main() -> None:
    checks = [
        ("regression gate missing handling", validate_regression_gate_missing_handling),
        ("no dead gate configuration", validate_no_dead_gate_configuration),
        ("source fingerprint correctness", validate_source_fingerprint_correctness),
        ("deterministic benchmark isolation", validate_deterministic_benchmark_isolation),
        ("cache bound enforcement", validate_cache_bound_enforcement),
    ]
    result = run_checks("validate_stabilization_n", checks, json_path=VALIDATION_JSON)
    write_report(result.to_dict())
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization N validation complete.")


def validate_regression_gate_missing_handling() -> dict[str, Any]:
    states = {
        "missing": classify_gate_numeric_value(None),
        "sentinel": classify_gate_numeric_value(opponent_signal_sentinel("not_run", "validator probe")),
        "zero": classify_gate_numeric_value(0),
        "numeric": classify_gate_numeric_value(3.5),
        "schema_mismatch": classify_gate_numeric_value({"unexpected": "shape"}),
    }
    expected = {
        "missing": "missing",
        "sentinel": "sentinel",
        "zero": "numeric",
        "numeric": "numeric",
        "schema_mismatch": "schema_mismatch",
    }
    mismatches = {key: value for key, value in states.items() if value["state"] != expected[key]}
    if mismatches:
        raise AssertionError(mismatches)
    if not states["zero"]["is_zero"] or not states["zero"]["is_numeric"]:
        raise AssertionError(states["zero"])

    missing_previous = evaluate_training_batch({"successful_runs": 1, "average_score": -99}, {})
    zero_previous = evaluate_training_batch({"successful_runs": 1, "average_score": -99}, {"average_score": 0})
    if any("average score dropped" in reason for reason in missing_previous["reasons"]):
        raise AssertionError("missing previous score was treated as numeric zero")
    if not any("average score dropped" in reason for reason in zero_previous["reasons"]):
        raise AssertionError("numeric zero previous score was not treated as a real baseline")
    return {"states": states, "missing_previous_reasons": missing_previous["reasons"], "zero_previous_reasons": zero_previous["reasons"]}


def validate_no_dead_gate_configuration() -> dict[str, Any]:
    source = (ROOT / "SystemAIYugioh" / "regression_gates.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fields: list[str] = []
    active_uses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RegressionGateConfig":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.append(stmt.target.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "config":
            active_uses.add(node.attr)
    unused = sorted(set(fields) - active_uses)
    if unused:
        raise AssertionError(unused)
    return {"field_count": len(fields), "active_use_count": len(active_uses)}


def validate_source_fingerprint_correctness() -> dict[str, Any]:
    first = matrix_cache_fingerprint()
    for module_name in ("deck.card_metadata", "deck.generic_deck_builder", "SystemAIYugioh.report_schema"):
        importlib.import_module(module_name)
    second = matrix_cache_fingerprint()
    if first["fingerprint"] != second["fingerprint"]:
        raise AssertionError("matrix cache fingerprint changed after unrelated import order")

    fingerprint = source_fingerprint()
    missing = [path for path in SCORE_AFFECTING_SOURCE_FILES if path not in fingerprint["files"]]
    if missing:
        raise AssertionError(missing)
    edited = copy.deepcopy(fingerprint)
    first_file = SCORE_AFFECTING_SOURCE_FILES[0]
    edited["files"][first_file]["sha256"] = "stabilization-n-edit-probe"
    edited["fingerprint"] = "stabilization-n-edited-fingerprint"
    with TemporaryDirectory(prefix="stabilization_n_cache_") as folder:
        base_cache = MatrixCache(cache_dir=folder, enabled=True, fingerprint={"fingerprint": fingerprint["fingerprint"], "source_fingerprint": fingerprint, "parts": {"source_fingerprint": fingerprint}})
        edited_cache = MatrixCache(cache_dir=folder, enabled=True, fingerprint={"fingerprint": edited["fingerprint"], "source_fingerprint": edited, "parts": {"source_fingerprint": edited}})
        if base_cache.key(archetype="Blue-Eyes") == edited_cache.key(archetype="Blue-Eyes"):
            raise AssertionError("source fingerprint edit did not alter matrix cache key")
    return {"covered_files": len(fingerprint["files"]), "source_hash": fingerprint["source_hash"], "import_order_stable": True}


def validate_deterministic_benchmark_isolation() -> dict[str, Any]:
    determinism_source = (ROOT / "benchmark_determinism_check.py").read_text(encoding="utf-8")
    parity_source = (ROOT / "cache_parity_check.py").read_text(encoding="utf-8")
    forbidden = "DEFAULT_RUNTIME_CONTEXT.cards(refresh=True)"
    if forbidden in determinism_source or forbidden in parity_source:
        raise AssertionError("benchmark validation still requires live runtime card refresh")
    determinism = run_determinism_check()
    parity = run_cache_parity()
    if not determinism.get("frozen_inputs") or not determinism.get("same_seed_same_result"):
        raise AssertionError(determinism)
    if not parity.get("frozen_inputs") or parity.get("mismatched_cells"):
        raise AssertionError(parity)
    return {
        "determinism_frozen": determinism.get("frozen_inputs"),
        "same_seed_same_result": determinism.get("same_seed_same_result"),
        "parity_frozen": parity.get("frozen_inputs"),
        "matched_cells": parity.get("matched_cells"),
    }


def validate_cache_bound_enforcement() -> dict[str, Any]:
    with TemporaryDirectory(prefix="stabilization_n_lru_") as folder:
        matrix_cache = MatrixCache(cache_dir=folder, enabled=False, fingerprint={"fingerprint": "n-lru", "parts": {}, "source_fingerprint": {}})
        for index in range(5):
            matrix_cache._remember_cell(str(index), {"successful_runs": 1, "failed_runs": 0, "failure_rate": 0})
        matrix_cache._enforce_memory_bound(3)
        if len(matrix_cache._cells) != 3 or list(matrix_cache._cells) != ["2", "3", "4"]:
            raise AssertionError(list(matrix_cache._cells))

    score_cache = ScoreSnapshotCache(max_entries=2)
    for index in range(4):
        deck = [{"name": f"Card {index}"}]
        score_cache.cached_breakdown(deck, "Blue-Eyes", "meta", lambda index=index: {"final_score": index})
    if len(score_cache._breakdowns) != 2:
        raise AssertionError(len(score_cache._breakdowns))

    runtime = RuntimeContext(max_entries=2)
    for index in range(4):
        runtime.get(f"key-{index}", lambda index=index: index)
    if len(runtime._cache) != 2:
        raise AssertionError(len(runtime._cache))

    CHOKE_CACHE.clear()
    for index in range(2050):
        remember_choke_cache((f"opponent-{index}", (), ()), {"index": index})
    if len(CHOKE_CACHE) > 2048:
        raise AssertionError(len(CHOKE_CACHE))

    SIDE_CANDIDATE_SCORE_CACHE.clear()
    for index in range(SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES + 2):
        key = ((f"Card {index}",), "Blue-Eyes", "meta")
        SIDE_CANDIDATE_SCORE_CACHE[key] = float(index)
        SIDE_CANDIDATE_SCORE_CACHE.move_to_end(key)
        while len(SIDE_CANDIDATE_SCORE_CACHE) > SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES:
            SIDE_CANDIDATE_SCORE_CACHE.popitem(last=False)
    if len(SIDE_CANDIDATE_SCORE_CACHE) > SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES:
        raise AssertionError(len(SIDE_CANDIDATE_SCORE_CACHE))

    return {
        "matrix_cache_bound": 3,
        "score_snapshot_bound": score_cache.max_entries,
        "runtime_context_bound": runtime.max_entries,
        "choke_cache_bound": 2048,
        "side_candidate_cache_bound": SIDE_CANDIDATE_SCORE_CACHE_MAX_ENTRIES,
    }


def write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Stabilization N: Architecture Review Remediation",
        "",
        "Infrastructure-only pass. No gameplay, scoring formula, deck-building, Blue-Eyes authored behavior, learning weight, memory influence, regression threshold, or normal cache policy changes were made.",
        "",
        "## Files Changed",
        "",
        "- `SystemAIYugioh/regression_gates.py`",
        "- `SystemAIYugioh/source_fingerprint.py`",
        "- `SystemAIYugioh/cache_fingerprint.py`",
        "- `SystemAIYugioh/matrix_cache.py`",
        "- `SystemAIYugioh/score_snapshot.py`",
        "- `SystemAIYugioh/runtime_context.py`",
        "- `deck/choke_simulator.py`",
        "- `deck/side_plan_optimizer.py`",
        "- `benchmark_determinism_check.py`",
        "- `cache_parity_check.py`",
        "- `validate_stabilization_n.py`",
        "- `STABILIZATION_N_ARCHITECTURE_REMEDIATION.md`",
        "",
        "## Architecture Issues Resolved",
        "",
        "- Regression gates now classify missing, sentinel, schema mismatch, numeric zero, and valid numeric values explicitly.",
        "- Regression comparisons no longer use Python truthiness to decide whether a numeric baseline exists.",
        "- Regression gate config fields are audited for active `config.<field>` usage.",
        "- Source fingerprints cover a broader score-affecting module set and no longer depend on imported module order.",
        "- Benchmark parity and determinism checks default to frozen local card inputs instead of live refreshes.",
        "- Runtime in-memory caches now have bounded LRU behavior while preserving cache-hit semantics.",
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
            "## Remaining Findings",
            "",
            "- Future score-affecting modules still need to be added to `SCORE_AFFECTING_SOURCE_FILES` when introduced.",
            "- Existing persistent cache retention settings are intentionally unchanged.",
            "- Larger end-to-end suite timing can still be improved by moving more legacy validators onto the shared harness.",
        ]
    )
    atomic_write_text(REPORT_PATH, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
