from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from config.settings import (
    CACHE_VERSION,
    DATA_DIR,
    MATRIX_FULL_SIDE_CANDIDATES,
    MATRIX_SMOKE_ENGINE_LIMIT,
    MATRIX_SMOKE_MATCHUP_LIMIT,
    MATRIX_SMOKE_SIDE_CANDIDATES,
    REPORT_VERSION,
    PROJECT_ROOT,
)
from data.card_limits import CUSTOM_CARD_LIMITS
from deck.engine_variants import ENGINE_VARIANTS
from SystemAIYugioh.source_fingerprint import SCORE_AFFECTING_SOURCE_FILES, source_fingerprint


FINGERPRINT_VERSION = 2

def matrix_cache_fingerprint() -> dict[str, Any]:
    source = source_fingerprint()
    parts = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "cache_version": CACHE_VERSION,
        "report_version": REPORT_VERSION,
        "card_database": card_database_state(),
        "custom_card_limits": dict(sorted(CUSTOM_CARD_LIMITS.items())),
        "engine_variants": list(ENGINE_VARIANTS),
        "source_fingerprint": source,
        "source_dependencies": source_dependency_state(),
        "side_plan_settings": {
            "matrix_smoke_side_candidates": MATRIX_SMOKE_SIDE_CANDIDATES,
            "matrix_full_side_candidates": MATRIX_FULL_SIDE_CANDIDATES,
            "matrix_smoke_engine_limit": MATRIX_SMOKE_ENGINE_LIMIT,
            "matrix_smoke_matchup_limit": MATRIX_SMOKE_MATCHUP_LIMIT,
        },
    }
    return {"fingerprint": stable_hash(parts), "parts": parts, "source_fingerprint": source}


def card_database_state() -> dict[str, Any]:
    files = [DATA_DIR / "cards.json", DATA_DIR / "metadata.json", DATA_DIR / "latest_update_analysis.json"]
    return {path.name: file_state(path) for path in files}


def source_dependency_state(extra_files: list[str | Path] | None = None) -> dict[str, Any]:
    paths: set[Path] = {PROJECT_ROOT / relative for relative in SCORE_AFFECTING_SOURCE_FILES}
    paths.update(loaded_project_module_paths())
    if extra_files:
        paths.update(PROJECT_ROOT / Path(path) if not Path(path).is_absolute() else Path(path) for path in extra_files)
    files = {}
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if not should_hash_source(path):
            continue
        files[path.relative_to(PROJECT_ROOT).as_posix()] = file_state(path)
    return {"file_count": len(files), "files": files, "source_hash": stable_hash(files)}


def loaded_project_module_paths() -> set[Path]:
    paths: set[Path] = set()
    for module in list(sys.modules.values()):
        raw = getattr(module, "__file__", None)
        if not raw:
            continue
        path = Path(raw).resolve()
        if should_hash_source(path):
            paths.add(path)
    return paths


def should_hash_source(path: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved.relative_to(PROJECT_ROOT)
    except (OSError, ValueError):
        return False
    if resolved.suffix != ".py":
        return False
    relative = resolved.relative_to(PROJECT_ROOT)
    parts = set(relative.parts)
    if "__pycache__" in parts:
        return False
    if len(relative.parts) > 1 and relative.parts[0] == "SystemAIYugioh" and relative.parts[1] == "data":
        return False
    if relative.name.startswith("validate_"):
        return False
    allowed_roots = {"deck", "SystemAIYugioh", "data", "config"}
    if relative.parts[0] in allowed_roots:
        return True
    return relative.as_posix() in SCORE_AFFECTING_SOURCE_FILES


def file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": file_hash(path),
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
