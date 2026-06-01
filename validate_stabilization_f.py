from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from SystemAIYugioh.cache_fingerprint import matrix_cache_fingerprint, source_dependency_state
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.memory_context import temporary_isolated_memory_root
from SystemAIYugioh.report_schema import normalize_json_shape, validate_matrix_cell_schema
from matchup_matrix import run_cell
from validate_stabilization_e import valid_cell

ROOT = Path(__file__).resolve().parent


def main() -> None:
    with temporary_isolated_memory_root("stabilization_f_memory_"):
        run_checks()


def run_checks() -> None:
    checks = [
        ("source fingerprint changes with source content", validate_source_fingerprint_changes),
        ("matrix cache fingerprint includes source dependencies", validate_cache_fingerprint_sources),
        ("partial-failure cells are not persisted", validate_partial_failures_not_persisted),
        ("invalid cached cells become misses", validate_invalid_cache_miss),
        ("cold and warm matrix outputs are structurally equivalent", validate_cold_warm_equivalence),
        ("cache pruning removes stale or invalid entries safely", validate_cache_pruning),
        ("shared matrix cell schema is enforced", validate_shared_schema),
        ("Stabilization E still passes", validate_stabilization_e_still_passes),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
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
    print("Stabilization Pass F validation complete.")


def validate_source_fingerprint_changes() -> None:
    temp_dir = ROOT / "deck" / "_stabilization_f_source_probe"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp = temp_dir / "score_affecting_probe.py"
    try:
        temp.write_text("VALUE = 1\n", encoding="utf-8")
        first = source_dependency_state([temp])["source_hash"]
        temp.write_text("VALUE = 2\n", encoding="utf-8")
        second = source_dependency_state([temp])["source_hash"]
        if first == second:
            raise AssertionError("source hash did not change after content update")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def validate_cache_fingerprint_sources() -> None:
    fingerprint = matrix_cache_fingerprint()
    sources = fingerprint.get("parts", {}).get("source_dependencies", {})
    files = sources.get("files", {}) if isinstance(sources, dict) else {}
    for required in ("deck/builder.py", "deck/side_plan_optimizer.py", "matchup_matrix.py"):
        if required not in files:
            raise AssertionError(f"missing source dependency: {required}")
    if not sources.get("source_hash"):
        raise AssertionError(sources)


def validate_partial_failures_not_persisted() -> None:
    cache_dir = fresh_dir("partial")
    try:
        cache = MatrixCache(cache_dir=cache_dir)
        key = cache.key(cell="partial")
        partial = valid_cell()
        partial["successful_runs"] = 1
        partial["failed_runs"] = 1
        partial["failure_rate"] = 0.5
        partial["runs"].append({"ok": False, "run": 2, "error": "simulated"})
        cache.set(key, partial)
        if cache.path_for(key).exists():
            raise AssertionError("partial-failure cell was persisted")
        if cache.stats["skipped_failed"] < 1:
            raise AssertionError(cache.stats)
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_invalid_cache_miss() -> None:
    cache_dir = fresh_dir("invalid")
    try:
        cache = MatrixCache(cache_dir=cache_dir)
        key = cache.key(cell="invalid")
        atomic_write_json(
            cache.path_for(key),
            {
                "cache_version": cache.fingerprint["parts"]["cache_version"],
                "fingerprint": cache.fingerprint["fingerprint"],
                "schema_version": 1,
                "value": {"engine_variant": "pure", "successful_runs": "one", "failed_cell": False},
            },
        )
        reader = MatrixCache(cache_dir=cache_dir)
        if reader.get(key) is not None:
            raise AssertionError("invalid cached cell loaded")
        if reader.stats["schema_misses"] < 1:
            raise AssertionError(reader.stats)
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_cold_warm_equivalence() -> None:
    cache_dir = fresh_dir("equivalence")
    try:
        cards = CardDatabase().load_cards()
        cold_cache = MatrixCache(cache_dir=cache_dir)
        cold = run_cell(cards, "Blue-Eyes", "meta", "pure", "combo", "second", 1, False, cold_cache)
        warm_cache = MatrixCache(cache_dir=cache_dir)
        warm = run_cell(cards, "Blue-Eyes", "meta", "pure", "combo", "second", 1, False, warm_cache)
        if warm_cache.stats["disk_hits"] < 1:
            raise AssertionError(warm_cache.stats)
        if comparable_cell(cold) != comparable_cell(warm):
            raise AssertionError("cold and warm cell structures differ")
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_cache_pruning() -> None:
    cache_dir = fresh_dir("prune")
    try:
        cache = MatrixCache(cache_dir=cache_dir)
        valid_key = cache.key(cell="valid")
        cache.set(valid_key, valid_cell())
        invalid_key = cache.key(cell="invalid_prune")
        atomic_write_json(cache.path_for(invalid_key), {"cache_version": "old", "fingerprint": "old", "value": valid_cell()})
        result = cache.prune(max_age_seconds=60 * 60, max_entries=100)
        if result["removed"] < 1:
            raise AssertionError(result)
        if not cache.path_for(valid_key).exists():
            raise AssertionError("prune removed current valid cache entry")
        if cache.path_for(invalid_key).exists():
            raise AssertionError("prune left stale invalid cache entry")
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def validate_shared_schema() -> None:
    cell = normalize_json_shape(valid_cell())
    schema = validate_matrix_cell_schema(cell)
    if not schema["valid"]:
        raise AssertionError(schema)
    bad = dict(cell)
    bad.pop("runs")
    if validate_matrix_cell_schema(bad)["valid"]:
        raise AssertionError("shared schema accepted missing runs")


def validate_stabilization_e_still_passes() -> None:
    run_command("validate_stabilization_e.py", timeout=900)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def comparable_cell(cell: dict[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(cell)
    for key in ("cache_hit", "runtime_seconds", "created_at_utc"):
        cloned.pop(key, None)
    return json.loads(json.dumps(cloned, sort_keys=True, default=str))


def fresh_dir(label: str) -> Path:
    path = ROOT / "SystemAIYugioh" / "data" / "runtime_cache" / f"_stabilization_f_{label}_{time.time_ns()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
