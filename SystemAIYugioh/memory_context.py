from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator


PRODUCTION_MEMORY_ROOT = Path("SystemAIYugioh") / "data" / "deck_profiles"
MEMORY_ROOT_ENV = "YUGIOH_AI_MEMORY_ROOT"
TEST_MODE_ENV = "YUGIOH_AI_TEST_MODE"


def memory_root() -> Path:
    override = os.environ.get(MEMORY_ROOT_ENV)
    if override:
        return Path(override)
    return PRODUCTION_MEMORY_ROOT


def memory_file(filename: str | Path) -> Path:
    return memory_root() / Path(filename).name


def is_test_mode() -> bool:
    return os.environ.get(TEST_MODE_ENV, "").strip().casefold() in {"1", "true", "yes", "on"}


def is_isolated_memory_root() -> bool:
    try:
        return memory_root().resolve() != PRODUCTION_MEMORY_ROOT.resolve()
    except OSError:
        return True


def provenance_metadata(
    *,
    source: str = "manual",
    validator_generated: bool | None = None,
    smoke: bool = False,
    legal: bool | None = None,
    confidence_score: Any = None,
    improvement: Any = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "validator_generated": is_test_mode() if validator_generated is None else bool(validator_generated),
        "smoke": bool(smoke),
        "legal": legal,
        "confidence_score": confidence_score,
        "improvement": improvement,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def normalize_provenance(provenance: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    base = provenance_metadata()
    if isinstance(provenance, dict):
        base.update(provenance)
    for key, value in overrides.items():
        if value is not None:
            base[key] = value
    if base.get("validator_generated") is None:
        base["validator_generated"] = is_test_mode()
    if not base.get("timestamp"):
        base["timestamp"] = datetime.now(timezone.utc).isoformat()
    return base


def result_provenance(result: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    provenance = result.get("provenance") if isinstance(result, dict) else None
    if isinstance(provenance, dict):
        return normalize_provenance(provenance)
    return normalize_provenance(fallback)


def is_validator_generated(provenance_or_result: dict[str, Any] | None) -> bool:
    if not isinstance(provenance_or_result, dict):
        return False
    if "provenance" in provenance_or_result and isinstance(provenance_or_result.get("provenance"), dict):
        provenance_or_result = provenance_or_result["provenance"]
    return bool(provenance_or_result.get("validator_generated"))


def should_skip_production_update(provenance: dict[str, Any] | None) -> bool:
    return is_validator_generated(provenance) and not is_isolated_memory_root()


def append_provenance_entry(payload: dict[str, Any], provenance: dict[str, Any], *, limit: int = 100) -> None:
    payload.setdefault("provenance_log", []).append(normalize_provenance(provenance))
    payload["provenance_log"] = payload["provenance_log"][-limit:]


@contextmanager
def isolated_memory_root(root: str | Path) -> Iterator[Path]:
    previous_root = os.environ.get(MEMORY_ROOT_ENV)
    previous_test = os.environ.get(TEST_MODE_ENV)
    target = Path(root)
    target.mkdir(parents=True, exist_ok=True)
    os.environ[MEMORY_ROOT_ENV] = str(target)
    os.environ[TEST_MODE_ENV] = "1"
    try:
        yield target
    finally:
        if previous_root is None:
            os.environ.pop(MEMORY_ROOT_ENV, None)
        else:
            os.environ[MEMORY_ROOT_ENV] = previous_root
        if previous_test is None:
            os.environ.pop(TEST_MODE_ENV, None)
        else:
            os.environ[TEST_MODE_ENV] = previous_test


@contextmanager
def temporary_isolated_memory_root(prefix: str = "yugioh_ai_memory_") -> Iterator[Path]:
    with TemporaryDirectory(prefix=prefix) as folder:
        with isolated_memory_root(folder) as root:
            yield root
