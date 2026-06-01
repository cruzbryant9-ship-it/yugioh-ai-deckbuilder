from __future__ import annotations

import copy
import json
import shutil
import time
from pathlib import Path
from typing import Any

from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.matrix_cache import MatrixCache
from matchup_matrix import run_cell, validate_matrix_memory_safety

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("cache fingerprint changes invalidate entries", validate_fingerprint_invalidation),
        ("failed cells are not cached as authoritative", validate_failed_cells_not_authoritative),
        ("cached cells validate schema and return defensive copies", validate_schema_and_defensive_copy),
        ("cold and warm matrix cell outputs are equivalent", validate_cold_warm_equivalence),
        ("cached illegal decks cannot update memory safely", validate_cached_deck_legality_gate),
        ("JSON helper path is atomic and cross-platform", validate_json_helpers),
    ]
    failures = []
    for label, check in checks:
        try:
            check()
            print(f"PASS: {label}")
        except Exception as exc:
            failures.append(label)
            print(f"FAIL: {label}: {exc}")
    if failures:
        raise SystemExit(1)
    print("Stabilization Pass E validation complete.")


def validate_fingerprint_invalidation() -> None:
    cache_dir = fresh_cache_dir("fingerprint")
    try:
        first = MatrixCache(cache_dir=cache_dir, fingerprint={"fingerprint": "one", "parts": {"x": 1}})
        key = first.key(cell="same")
        first.set(key, valid_cell())
        second = MatrixCache(cache_dir=cache_dir, fingerprint={"fingerprint": "two", "parts": {"x": 2}})
        if second.get(key) is not None:
            raise AssertionError("cache hit survived fingerprint change")
        if second.stats["fingerprint_misses"] < 1:
            raise AssertionError(second.stats)
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_failed_cells_not_authoritative() -> None:
    cache_dir = fresh_cache_dir("failed")
    try:
        cache = MatrixCache(cache_dir=cache_dir)
        key = cache.key(cell="failed")
        failed = valid_cell()
        failed.update({"successful_runs": 0, "failed_runs": 1, "failed_cell": True, "failure_rate": 1.0})
        cache.set(key, failed)
        if cache.path_for(key).exists():
            raise AssertionError("failed cell was persisted")
        if MatrixCache(cache_dir=cache_dir).get(key) is not None:
            raise AssertionError("failed cell became warm-cache hit")
        if cache.stats["skipped_failed"] < 1:
            raise AssertionError(cache.stats)
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_schema_and_defensive_copy() -> None:
    cache_dir = fresh_cache_dir("schema")
    try:
        cache = MatrixCache(cache_dir=cache_dir)
        key = cache.key(cell="schema")
        cache.set(key, valid_cell())
        loaded = MatrixCache(cache_dir=cache_dir).get(key)
        if not loaded:
            raise AssertionError("valid cell did not load")
        loaded["runs"][0]["main_deck"].append("Pot of Greed")
        loaded_again = MatrixCache(cache_dir=cache_dir).get(key)
        if "Pot of Greed" in loaded_again["runs"][0]["main_deck"]:
            raise AssertionError("cache returned mutable shared state")

        bad_key = cache.key(cell="bad_schema")
        atomic_write_json(
            cache.path_for(bad_key),
            {
                "cache_version": cache.fingerprint["parts"]["cache_version"],
                "fingerprint": cache.fingerprint["fingerprint"],
                "schema_version": 1,
                "value": {"engine_variant": "pure", "failed_cell": False},
            },
        )
        bad_reader = MatrixCache(cache_dir=cache_dir)
        if bad_reader.get(bad_key) is not None:
            raise AssertionError("invalid matrix-cell schema loaded")
        if bad_reader.stats["schema_misses"] < 1:
            raise AssertionError(bad_reader.stats)
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_cold_warm_equivalence() -> None:
    cache_dir = fresh_cache_dir("equivalence")
    try:
        cards = CardDatabase().load_cards()
        cold_cache = MatrixCache(cache_dir=cache_dir)
        cold = run_cell(cards, "Blue-Eyes", "meta", "pure", "combo", "second", 1, False, cold_cache)
        warm_cache = MatrixCache(cache_dir=cache_dir)
        warm = run_cell(cards, "Blue-Eyes", "meta", "pure", "combo", "second", 1, False, warm_cache)
        if warm_cache.stats["disk_hits"] < 1:
            raise AssertionError(warm_cache.stats)
        if strip_allowed_runtime_fields(cold) != strip_allowed_runtime_fields(warm):
            raise AssertionError("warm cached cell differs from cold cell")
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_cached_deck_legality_gate() -> None:
    report = {
        "cells": [
            {
                **valid_cell(),
                "best_deck": {"main_deck": ["Pot of Greed"], "extra_deck": []},
                "recommended_side_deck": [("Ash Blossom & Joyous Spring", 1)],
            }
        ]
    }
    safety = validate_matrix_memory_safety(report)
    if safety["safe"] or not safety["issues"]:
        raise AssertionError(safety)


def validate_json_helpers() -> None:
    path = fresh_cache_dir("json") / "nested" / "payload.json"
    try:
        atomic_write_json(path, {"ok": True})
        if safe_load_json(path, {}).get("ok") is not True:
            raise AssertionError(path)
        if path.with_suffix(path.suffix + ".tmp").exists():
            raise AssertionError("temporary JSON file was left behind")
    finally:
        shutil.rmtree(path.parents[1], ignore_errors=True)


def valid_cell() -> dict[str, Any]:
    return {
        "engine_variant": "pure",
        "matchup": "combo",
        "going": "second",
        "successful_runs": 1,
        "failed_runs": 0,
        "failed_cell": False,
        "failure_rate": 0.0,
        "average_final_score": 100.0,
        "best_score": 100.0,
        "blocked_card_violations": [],
        "best_deck": {"main_deck": ["Blue-Eyes White Dragon"], "extra_deck": []},
        "recommended_side_deck": [("Ash Blossom & Joyous Spring", 1)],
        "runs": [
            {
                "ok": True,
                "run": 1,
                "main_deck": ["Blue-Eyes White Dragon"],
                "extra_deck": [],
                "recommended_side_deck": ["Ash Blossom & Joyous Spring"],
                "side_cards_used": ["Ash Blossom & Joyous Spring"],
            }
        ],
    }


def strip_allowed_runtime_fields(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(payload)
    for key in ("cache_hit", "runtime_seconds", "created_at_utc"):
        cloned.pop(key, None)
    return json.loads(json.dumps(cloned, sort_keys=True, default=str))


def fresh_cache_dir(label: str) -> Path:
    path = ROOT / "SystemAIYugioh" / "data" / "runtime_cache" / f"_stabilization_e_{label}_{time.time_ns()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    main()
