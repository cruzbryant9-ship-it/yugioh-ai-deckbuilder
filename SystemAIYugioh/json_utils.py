from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def safe_load_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    try:
        with target.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        backup_corrupt_json(target)
        return default
    except OSError:
        return default


def atomic_write_json(path: str | Path, payload: Any, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=indent, ensure_ascii=False)
        file.write("\n")
    replace_with_retry(temp, target)


atomic_json_write = atomic_write_json


def atomic_write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    replace_with_retry(temp, target)


def replace_with_retry(temp: Path, target: Path, attempts: int = 5, delay: float = 0.15) -> None:
    for attempt in range(attempts):
        try:
            temp.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def backup_corrupt_json(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".corrupt_{stamp}.bak")
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None
