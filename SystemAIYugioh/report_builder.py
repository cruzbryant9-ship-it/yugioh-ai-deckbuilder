from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from SystemAIYugioh.metric_registry import extract_metrics
from SystemAIYugioh.report_schema import normalize_report, validate_report


def build_report(report_type: str, config: dict[str, Any], summary: dict[str, Any], **sections: Any) -> dict[str, Any]:
    payload = {
        "config": config,
        "summary": summary,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        **sections,
    }
    return normalize_report(report_type, payload)


def merge_metric_sections(primary: dict[str, Any], fallback: dict[str, Any] | None, keys: tuple[str, ...], default: Any = 0) -> dict[str, Any]:
    return extract_metrics(primary, fallback, keys, default=default)


def validate_or_raise(report_type: str, payload: dict[str, Any]) -> None:
    validate_report(report_type, payload, strict=True)
