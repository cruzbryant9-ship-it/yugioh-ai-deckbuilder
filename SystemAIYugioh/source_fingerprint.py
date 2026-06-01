from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT


SOURCE_FINGERPRINT_VERSION = 1

SCORE_AFFECTING_SOURCE_FILES = (
    "deck/builder.py",
    "deck/package_builder.py",
    "deck/hand_simulator.py",
    "deck/line_validator.py",
    "deck/side_deck_planner.py",
    "deck/side_plan_optimizer.py",
    "deck/post_side_evaluation.py",
    "deck/choke_simulator.py",
    "deck/opponent_graph_simulator.py",
    "deck/opponent_probability_simulator.py",
    "matchup_matrix.py",
)


def source_fingerprint(extra_files: list[str | Path] | None = None) -> dict[str, Any]:
    files = list(SCORE_AFFECTING_SOURCE_FILES)
    if extra_files:
        files.extend(normalize_relative_path(path) for path in extra_files)
    file_payload = {
        relative: source_file_state(PROJECT_ROOT / relative)
        for relative in sorted(dict.fromkeys(files))
    }
    payload = {
        "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
        "files": file_payload,
    }
    return {
        "fingerprint": stable_hash(payload),
        "source_hash": stable_hash(file_payload),
        "file_count": len(file_payload),
        "files": file_payload,
        "version": SOURCE_FINGERPRINT_VERSION,
    }


def normalize_relative_path(path: str | Path) -> str:
    item = Path(path)
    if item.is_absolute():
        item = item.resolve().relative_to(PROJECT_ROOT)
    return item.as_posix()


def source_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "sha256": None, "size": 0}
    return {
        "exists": True,
        "sha256": file_hash(path),
        "size": path.stat().st_size,
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
