from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from config.settings import CACHE_VERSION, MATRIX_CACHE_DIR, MATRIX_CACHE_MAX_AGE_SECONDS, MATRIX_CACHE_MAX_ENTRIES
from SystemAIYugioh.cache_fingerprint import matrix_cache_fingerprint
from SystemAIYugioh.json_utils import atomic_write_json, safe_load_json
from SystemAIYugioh.report_schema import is_matrix_cell_like, normalize_json_shape, validate_matrix_cell_schema


class MatrixCache:
    def __init__(
        self,
        cache_dir: str | Path = MATRIX_CACHE_DIR,
        enabled: bool = True,
        fingerprint: dict[str, Any] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.fingerprint = fingerprint or matrix_cache_fingerprint()
        self._cells: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "disk_hits": 0,
            "writes": 0,
            "invalid": 0,
            "fingerprint_misses": 0,
            "schema_misses": 0,
            "skipped_failed": 0,
            "pruned": 0,
        }

    def reset(self) -> None:
        self._cells.clear()
        for key in self.stats:
            self.stats[key] = 0

    def key(self, **parts: Any) -> str:
        payload = json.dumps(
            {"cache_version": CACHE_VERSION, "fingerprint": self.fingerprint["fingerprint"], **parts},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if key in self._cells:
            self.stats["hits"] += 1
            self._cells.move_to_end(key)
            return copy.deepcopy(self._cells[key])
        if self.enabled:
            payload = safe_load_json(self.path_for(key), None)
            if isinstance(payload, dict):
                value = payload.get("value")
                if (
                    payload.get("cache_version") == CACHE_VERSION
                    and payload.get("fingerprint") == self.fingerprint["fingerprint"]
                    and isinstance(value, dict)
                    and validate_cached_cell_schema(value)
                    and is_authoritative_cell(value)
                ):
                    self.stats["hits"] += 1
                    self.stats["disk_hits"] += 1
                    self._remember_cell(key, copy.deepcopy(value))
                    return copy.deepcopy(value)
                if payload.get("fingerprint") != self.fingerprint["fingerprint"]:
                    self.stats["fingerprint_misses"] += 1
                elif isinstance(value, dict) and not validate_cached_cell_schema(value):
                    self.stats["schema_misses"] += 1
                self.stats["invalid"] += 1
        self.stats["misses"] += 1
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        if not is_authoritative_cell(value):
            self.stats["skipped_failed"] += 1
            return
        stored = normalize_json_shape(copy.deepcopy(value))
        self._remember_cell(key, stored)
        if self.enabled:
            atomic_write_json(
                self.path_for(key),
                {
                    "cache_version": CACHE_VERSION,
                    "fingerprint": self.fingerprint["fingerprint"],
                    "fingerprint_parts": self.fingerprint.get("parts", {}),
                    "source_fingerprint": self.fingerprint.get("source_fingerprint") or self.fingerprint.get("parts", {}).get("source_fingerprint", {}),
                    "cache_created_timestamp": datetime.now(timezone.utc).isoformat(),
                    "schema_version": 1,
                    "value": stored,
                },
            )
            self.stats["writes"] += 1

    def path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _remember_cell(self, key: str, value: dict[str, Any]) -> None:
        self._cells[key] = value
        self._cells.move_to_end(key)
        self._enforce_memory_bound()

    def _enforce_memory_bound(self, max_entries: int = MATRIX_CACHE_MAX_ENTRIES) -> None:
        if max_entries <= 0:
            return
        while len(self._cells) > max_entries:
            self._cells.popitem(last=False)

    def prune(self, max_age_seconds: int = MATRIX_CACHE_MAX_AGE_SECONDS, max_entries: int = MATRIX_CACHE_MAX_ENTRIES) -> dict[str, int]:
        removed = 0
        kept: list[Path] = []
        if not self.cache_dir.exists():
            return {"removed": 0, "kept": 0}
        now = time.time()
        for path in sorted(self.cache_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            payload = safe_load_json(path, None)
            stale_age = max_age_seconds > 0 and now - path.stat().st_mtime > max_age_seconds
            invalid = not self._valid_payload(payload)
            too_many = len(kept) >= max_entries
            if stale_age or invalid or too_many:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
            else:
                kept.append(path)
        self.stats["pruned"] += removed
        return {"removed": removed, "kept": len(kept)}

    def _valid_payload(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        value = payload.get("value")
        return (
            payload.get("cache_version") == CACHE_VERSION
            and payload.get("fingerprint") == self.fingerprint["fingerprint"]
            and isinstance(value, dict)
            and validate_cached_cell_schema(value)
            and is_authoritative_cell(value)
        )


def validate_cached_cell_schema(value: dict[str, Any]) -> bool:
    if not is_matrix_cell_like(value):
        return True
    return bool(validate_matrix_cell_schema(value)["valid"])


def is_authoritative_cell(value: dict[str, Any]) -> bool:
    if value.get("failed_cell") is True:
        return False
    if "successful_runs" in value and int(value.get("successful_runs") or 0) <= 0:
        return False
    if int(value.get("failed_runs") or 0) > 0:
        return False
    if "runs" in value and int(value.get("successful_runs") or 0) < len(value.get("runs") or []):
        return False
    if float(value.get("failure_rate") or 0) > 0:
        return False
    return True


DEFAULT_MATRIX_CACHE = MatrixCache()


def reset_matrix_cache() -> None:
    DEFAULT_MATRIX_CACHE.reset()
