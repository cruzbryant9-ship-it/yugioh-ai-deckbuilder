from __future__ import annotations

from typing import Any


HARMFUL_LEARNING_CAUSES = {"score_negative"}


def classify_rejection_causes(row: dict[str, Any]) -> list[str]:
    causes: list[str] = []
    reason = str(row.get("rejection_reason") or row.get("reason") or "")
    warnings = [str(warning).casefold() for warning in row.get("quota_warnings", []) or []]
    improvement = safe_float(row.get("improvement"))
    legal_runs = int(row.get("legal_run_count", row.get("runs", 0)) or 0)
    runs = max(1, int(row.get("runs", 1) or 1))

    if row.get("blocked_card_violations") or "blocked" in reason:
        causes.append("blocked_card")
    if legal_runs < runs or reason in {"illegal_or_unrepaired_deck", "hard_legality_warning"}:
        causes.append("legality_failed")
    if any("copy limit" in warning for warning in warnings):
        causes.append("copy_limit_failed")
    if any("main deck below" in warning or "main deck above" in warning for warning in warnings) or reason == "illegal_or_unrepaired_deck":
        causes.append("incomplete_deck")
    if not row.get("repair_success", True) and row.get("repair_used"):
        causes.append("repair_failed")
    if row.get("confidence") is not None and safe_float(row.get("confidence")) < 0.15:
        causes.append("confidence_failed")
    if warnings:
        causes.append("quota_warning")
    if improvement < 0 and not any(cause in causes for cause in ("legality_failed", "blocked_card", "copy_limit_failed", "confidence_failed", "repair_failed", "incomplete_deck")):
        causes.append("score_negative")
    if not causes and reason == "no_safe_improvement":
        causes.append("score_flat")
    if not causes:
        causes.append(reason or "unknown")
    return sorted(dict.fromkeys(causes))


def harmful_learning_eligible(row: dict[str, Any]) -> bool:
    causes = set(row.get("rejection_causes") or classify_rejection_causes(row))
    if not causes & HARMFUL_LEARNING_CAUSES:
        return False
    disqualifying = {
        "legality_failed",
        "blocked_card",
        "copy_limit_failed",
        "confidence_failed",
        "repair_failed",
        "incomplete_deck",
    }
    return not bool(causes & disqualifying)


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
