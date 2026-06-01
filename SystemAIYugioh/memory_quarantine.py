from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SystemAIYugioh.json_utils import atomic_write_json


DEFAULT_QUARANTINE_ROOT = Path("SystemAIYugioh") / "data" / "memory_quarantine"


def quarantine_memory_file(
    source_path: str | Path,
    reason: str,
    *,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    mark_inactive: bool = False,
) -> dict[str, Any]:
    """Copy a memory file into quarantine and write a manifest.

    This helper never deletes the original. If mark_inactive is requested, it
    writes a sidecar marker next to the original instead of editing memory data.
    """

    source = Path(source_path)
    if not source.exists():
        return {
            "success": False,
            "source": str(source),
            "reason": reason,
            "error": "source_missing",
        }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_dir = Path(quarantine_root) / stamp
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)

    stat = source.stat()
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "quarantined_copy": str(target),
        "reason": reason,
        "original_size_bytes": stat.st_size,
        "original_modified_at_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "original_deleted": False,
        "mark_inactive_requested": bool(mark_inactive),
        "inactive_sidecar": None,
    }
    if mark_inactive:
        sidecar = source.with_suffix(source.suffix + ".inactive.json")
        atomic_write_json(
            sidecar,
            {
                "inactive": True,
                "created_at_utc": manifest["created_at_utc"],
                "reason": reason,
                "quarantine_manifest": str(target_dir / "manifest.json"),
            },
        )
        manifest["inactive_sidecar"] = str(sidecar)
    manifest_path = target_dir / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    manifest["success"] = True
    return manifest


def quarantine_many(
    source_paths: list[str | Path],
    reason: str,
    *,
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    mark_inactive: bool = False,
) -> list[dict[str, Any]]:
    return [
        quarantine_memory_file(path, reason, quarantine_root=quarantine_root, mark_inactive=mark_inactive)
        for path in source_paths
    ]
