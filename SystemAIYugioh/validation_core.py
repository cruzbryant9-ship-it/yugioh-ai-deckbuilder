from __future__ import annotations

from pathlib import Path
from typing import Any

from SystemAIYugioh.json_utils import safe_load_json
from SystemAIYugioh.report_schema import validate_report


def check_report_schema(report_type: str, payload: dict[str, Any]) -> bool:
    validate_report(report_type, payload, strict=True)
    return True


def check_matrix_report(path: str | Path) -> dict[str, Any]:
    payload = safe_load_json(path, {})
    if not isinstance(payload, dict):
        raise AssertionError(f"matrix report is not a JSON object: {path}")
    check_report_schema("matchup_matrix", payload)
    summary = payload.get("summary", {})
    for key in ("failed_cell_count", "failed_run_count", "failure_rate"):
        if key not in summary:
            raise AssertionError(f"missing matrix failure field: {key}")
    return payload


def check_side_plan_result(result: dict[str, Any]) -> bool:
    required = ("post_side_valid", "valid_candidate_rate", "side_cards_used", "cards_sided_out")
    missing = [key for key in required if key not in result]
    if missing:
        raise AssertionError(f"missing side-plan fields: {missing}")
    return True


def check_runtime_stats(stats: dict[str, Any]) -> bool:
    if "hits" not in stats or "misses" not in stats:
        raise AssertionError(stats)
    return True
