from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.settings import REPORT_VERSION
from SystemAIYugioh.metric_registry import REPORT_REQUIRED_METRICS, missing_required_keys
from SystemAIYugioh.opponent_metric_builder import build_opponent_metric_bundle, opponent_metric_payload_metadata


def normalize_report(report_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = dict(payload)
    report.setdefault("report_version", REPORT_VERSION)
    report.setdefault("report_type", report_type)
    report.setdefault("created_at_utc", datetime.now(timezone.utc).isoformat())
    report.setdefault("config", {})
    report.setdefault("summary", {})
    if isinstance(report.get("summary"), dict):
        report["summary"].setdefault("opponent_metric_schema_version", opponent_metric_payload_metadata([])["opponent_metric_schema_version"])
        report["summary"].setdefault("sentinel_policy_version", opponent_metric_payload_metadata([])["sentinel_policy_version"])
    report.setdefault("regression_gate", {})
    return report


def validate_report(report_type: str, payload: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    required = ("report_version", "report_type", "created_at_utc", *REPORT_REQUIRED_METRICS.get(report_type, ()))
    missing = missing_required_keys(payload, required)
    mismatched_type = payload.get("report_type") not in (None, report_type)
    errors = []
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")
    if mismatched_type:
        errors.append(f"report_type mismatch: {payload.get('report_type')} != {report_type}")
    if strict and errors:
        raise ValueError("; ".join(errors))
    return {"valid": not errors, "errors": errors, "required_keys": list(required)}


def common_run_fields(result: dict[str, Any]) -> dict[str, Any]:
    opponent_metrics = build_opponent_metric_bundle(result)
    return {
        "ok": bool(result.get("ok", True)),
        "final_score": result.get("final_score", result.get("post_side_score", result.get("score", 0))),
        "playable_hand_rate": result.get("playable_hand_rate", 0),
        "brick_rate": result.get("brick_rate", 0),
        "package_quality_score": result.get("package_quality_score", 0),
        "resilience_score": result.get("resilience_score", 0),
        "side_deck_score": result.get("side_deck_score", 0),
        "post_side_score": result.get("post_side_score", 0),
        "post_side_delta": result.get("post_side_delta", 0),
        "opponent_resource_valid_rate": opponent_metrics["opponent_resource_valid_rate"],
        "probability_weighted_stop_rate": opponent_metrics["probability_weighted_stop_rate"],
    }


def report_schema_fields() -> tuple[str, ...]:
    return (
        "report_version",
        "report_type",
        "created_at_utc",
        "config",
        "summary",
        "regression_gate",
    )


MATRIX_CELL_REQUIRED_KEYS = {
    "engine_variant",
    "matchup",
    "going",
    "successful_runs",
    "failed_runs",
    "failed_cell",
    "failure_rate",
    "average_final_score",
    "best_score",
    "blocked_card_violations",
    "runs",
}

MATRIX_CELL_TYPE_CHECKS = {
    "engine_variant": str,
    "matchup": str,
    "going": str,
    "successful_runs": int,
    "failed_runs": int,
    "failed_cell": bool,
    "blocked_card_violations": list,
    "runs": list,
}


def validate_matrix_cell_schema(cell: dict[str, Any]) -> dict[str, Any]:
    errors = []
    missing = sorted(MATRIX_CELL_REQUIRED_KEYS - set(cell))
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")
    for key, expected_type in MATRIX_CELL_TYPE_CHECKS.items():
        if key in cell and not isinstance(cell.get(key), expected_type):
            errors.append(f"{key} expected {expected_type.__name__}")
    for numeric_key in ("failure_rate", "average_final_score", "best_score"):
        if numeric_key in cell:
            try:
                float(cell.get(numeric_key))
            except (TypeError, ValueError):
                errors.append(f"{numeric_key} expected number")
    return {"valid": not errors, "errors": errors, "required_keys": sorted(MATRIX_CELL_REQUIRED_KEYS)}


def is_matrix_cell_like(value: dict[str, Any]) -> bool:
    return any(key in value for key in ("failed_cell", "successful_runs", "runs", "engine_variant"))


def normalize_json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_json_shape(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_json_shape(item) for item in value]
    if isinstance(value, list):
        return [normalize_json_shape(item) for item in value]
    return value
