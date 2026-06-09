from __future__ import annotations

import copy
import random
from collections import Counter
from statistics import mean
from typing import Any

from deck.builder import build_deck, get_last_build_report
from deck.deck_utils import split_deck
from deck.interaction_core_registry import interaction_core_for
from SystemAIYugioh.banlist import get_card_limit


def trace_interaction_preservation(
    cards: list[dict[str, Any]],
    archetype: str = "Kashtira",
    mode: str = "meta",
    runs: int = 10,
    seed: int = 12345,
) -> dict[str, Any]:
    run_count = max(1, int(runs or 1))
    run_rows = []
    for index in range(run_count):
        run_seed = int(seed) + index
        run_rows.append(run_trace(cards, archetype, mode, run_seed))
    return {
        "archetype": archetype,
        "mode": mode,
        "runs": run_count,
        "seed": int(seed),
        "interaction_core": list(interaction_core_for(archetype)),
        "card_traces": aggregate_card_traces(cards, archetype, run_rows),
        "run_traces": run_rows,
        "not_activated": True,
        "selection_behavior_changed": False,
    }


def run_trace(cards: list[dict[str, Any]], archetype: str, mode: str, seed: int) -> dict[str, Any]:
    generic = run_builder(cards, archetype, mode, seed, "generic")
    experimental = run_builder(cards, archetype, mode, seed, "current_experimental")
    hybrid = run_builder(cards, archetype, mode, seed, "hybrid_overlay")
    return {
        "seed": seed,
        "generic": generic,
        "current_experimental": experimental,
        "hybrid_overlay": hybrid,
    }


def run_builder(cards: list[dict[str, Any]], archetype: str, mode: str, seed: int, kind: str) -> dict[str, Any]:
    random.seed(seed)
    kwargs: dict[str, Any] = {}
    if kind == "current_experimental":
        kwargs = {"experimental_semi_specialized": True, "specialization_profile": archetype}
    elif kind == "hybrid_overlay":
        kwargs = {
            "experimental_semi_specialized": True,
            "specialization_profile": archetype,
            "experimental_variant": "hybrid_generic_interaction_overlay",
        }
    deck, _pool = build_deck(copy.deepcopy(cards), archetype, mode=mode, **kwargs)
    report = get_last_build_report()
    main, extra = split_deck(deck)
    return {
        "kind": kind,
        "builder_used": report.get("builder_used"),
        "variant": report.get("variant"),
        "fallback_used": report.get("fallback_used", False),
        "main_names": [str(card.get("name", "")) for card in main],
        "extra_names": [str(card.get("name", "")) for card in extra],
        "trace_metadata": report.get("interaction_trace_metadata", {}),
        "package_counts": report.get("package_counts", {}),
        "quota_warnings": report.get("quota_warnings", []),
    }


def aggregate_card_traces(cards: list[dict[str, Any]], archetype: str, run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    traces = []
    for name in interaction_core_for(archetype):
        card = lookup.get(name)
        available = card is not None
        legal = bool(card and get_card_limit(card) > 0)
        per_run = [card_run_trace(name, row, available, legal) for row in run_rows]
        generic_total = sum(row["generic_count"] for row in per_run)
        experimental_total = sum(row["experimental_count"] for row in per_run)
        hybrid_total = sum(row["hybrid_count"] for row in per_run)
        classifications = sorted(set(reason for row in per_run for reason in row["failure_classification"]))
        traces.append(
            {
                "card": name,
                "available_in_pool": available,
                "legal": legal,
                "generic_count": generic_total,
                "experimental_count": experimental_total,
                "hybrid_count": hybrid_total,
                "generic_average_count": round(generic_total / max(1, len(per_run)), 4),
                "experimental_average_count": round(experimental_total / max(1, len(per_run)), 4),
                "hybrid_average_count": round(hybrid_total / max(1, len(per_run)), 4),
                "selected_stage": summarize_selected_stage(per_run),
                "rejection_stage": summarize_rejection_stage(per_run),
                "rejection_reason": summarize_rejection_reason(per_run),
                "failure_classification": classifications or ["unknown"],
                "experimental_path": summarize_path(per_run, "experimental"),
                "hybrid_path": summarize_path(per_run, "hybrid"),
                "per_run": per_run,
            }
        )
    return traces


def card_run_trace(name: str, row: dict[str, Any], available: bool, legal: bool) -> dict[str, Any]:
    generic_main = row["generic"]["main_names"]
    experimental = path_card_trace(name, row["current_experimental"], generic_main, available, legal)
    hybrid = path_card_trace(name, row["hybrid_overlay"], generic_main, available, legal)
    generic_count = count_name(generic_main, name)
    experimental_count = count_name(row["current_experimental"]["main_names"], name)
    hybrid_count = count_name(row["hybrid_overlay"]["main_names"], name)
    classifications = sorted(set(experimental["failure_classification"] + hybrid["failure_classification"]))
    return {
        "seed": row["seed"],
        "generic_count": generic_count,
        "experimental_count": experimental_count,
        "hybrid_count": hybrid_count,
        "experimental": experimental,
        "hybrid": hybrid,
        "failure_classification": classifications,
    }


def path_card_trace(name: str, path: dict[str, Any], external_generic_names: list[str], available: bool, legal: bool) -> dict[str, Any]:
    metadata = path.get("trace_metadata", {}) or {}
    quota_names = metadata.get("quota_stage_selected_names", []) or []
    preservation_names = metadata.get("interaction_preservation_stage_selected_names", []) or []
    preservation_rejected = metadata.get("interaction_preservation_stage_rejected_names", []) or []
    preservation_reasons = metadata.get("interaction_preservation_stage_rejection_reasons", []) or []
    generic_fill_names = metadata.get("generic_fill_stage_selected_names", []) or []
    internal_generic_names = metadata.get("internal_generic_baseline_main_names", []) or []
    final_names = path.get("main_names", []) or []
    trace = {
        "available_in_pool": available,
        "legal": legal,
        "external_generic_count": count_name(external_generic_names, name),
        "internal_generic_count": count_name(internal_generic_names, name),
        "quota_stage_count": count_name(quota_names, name),
        "interaction_preservation_stage_count": count_name(preservation_names, name),
        "generic_fill_stage_count": count_name(generic_fill_names, name),
        "final_count": count_name(final_names, name),
        "selected_stage": selected_stage(name, quota_names, preservation_names, generic_fill_names, final_names),
        "rejection_stage": rejection_stage(name, preservation_rejected, quota_names, generic_fill_names, final_names),
        "rejection_reason": rejection_reason(name, preservation_rejected, preservation_reasons),
    }
    trace["removed_or_replaced_later"] = trace["selected_stage"] not in {"not_selected", "final_selection"} and trace["final_count"] == 0
    trace["failure_classification"] = classify_failure(name, trace, quota_names, preservation_names, generic_fill_names, preservation_rejected)
    return trace


def classify_failure(
    name: str,
    trace: dict[str, Any],
    quota_names: list[str],
    preservation_names: list[str],
    generic_fill_names: list[str],
    preservation_rejected: list[str],
) -> list[str]:
    if not trace["available_in_pool"]:
        return ["unavailable_in_pool"]
    if not trace["legal"]:
        return ["illegal_or_limited"]
    if trace["final_count"] > 0:
        return []
    reasons = []
    if trace["external_generic_count"] <= 0:
        reasons.append("not_in_generic_baseline")
    if trace["internal_generic_count"] <= 0:
        reasons.append("preservation_stage_noop")
    if trace["quota_stage_count"] <= 0:
        reasons.append("not_in_profile_roles")
    if name in preservation_rejected:
        reasons.append("preservation_stage_noop")
    if trace["generic_fill_stage_count"] <= 0 and trace["internal_generic_count"] > 0:
        reasons.append("generic_fill_displaced")
    if trace["quota_stage_count"] > 0 and trace["final_count"] <= 0:
        reasons.append("final_selection_truncated")
    if not reasons and exact_name_possible(name, quota_names, preservation_names, generic_fill_names):
        reasons.append("name_mismatch")
    if not reasons:
        reasons.append("quota_stage_crowded_out")
    return sorted(set(reasons))


def selected_stage(name: str, quota_names: list[str], preservation_names: list[str], generic_fill_names: list[str], final_names: list[str]) -> str:
    if count_name(final_names, name) > 0:
        return "final_selection"
    if count_name(preservation_names, name) > 0:
        return "interaction_preservation_stage"
    if count_name(quota_names, name) > 0:
        return "quota_stage"
    if count_name(generic_fill_names, name) > 0:
        return "generic_fill_stage"
    return "not_selected"


def rejection_stage(name: str, preservation_rejected: list[str], quota_names: list[str], generic_fill_names: list[str], final_names: list[str]) -> str:
    if count_name(final_names, name) > 0:
        return "none"
    if name in preservation_rejected:
        return "interaction_preservation_stage"
    if count_name(quota_names, name) <= 0:
        return "quota_stage"
    if count_name(generic_fill_names, name) <= 0:
        return "generic_fill_stage"
    return "final_selection_stage"


def rejection_reason(name: str, preservation_rejected: list[str], preservation_reasons: list[str]) -> str:
    if name in preservation_rejected:
        for reason in preservation_reasons:
            if str(reason).startswith(f"{name}:"):
                return str(reason)
        return "interaction preservation rejected card"
    return ""


def summarize_path(per_run: list[dict[str, Any]], key: str) -> dict[str, Any]:
    rows = [row[key] for row in per_run]
    return {
        "final_count_total": sum(row["final_count"] for row in rows),
        "external_generic_count_total": sum(row["external_generic_count"] for row in rows),
        "internal_generic_count_total": sum(row["internal_generic_count"] for row in rows),
        "quota_stage_count_total": sum(row["quota_stage_count"] for row in rows),
        "interaction_preservation_stage_count_total": sum(row["interaction_preservation_stage_count"] for row in rows),
        "generic_fill_stage_count_total": sum(row["generic_fill_stage_count"] for row in rows),
        "selected_stages": dict(Counter(row["selected_stage"] for row in rows)),
        "rejection_stages": dict(Counter(row["rejection_stage"] for row in rows)),
        "failure_classifications": dict(Counter(reason for row in rows for reason in row["failure_classification"])),
    }


def summarize_selected_stage(per_run: list[dict[str, Any]]) -> str:
    return most_common([row["hybrid"]["selected_stage"] for row in per_run] + [row["experimental"]["selected_stage"] for row in per_run])


def summarize_rejection_stage(per_run: list[dict[str, Any]]) -> str:
    return most_common([row["hybrid"]["rejection_stage"] for row in per_run] + [row["experimental"]["rejection_stage"] for row in per_run])


def summarize_rejection_reason(per_run: list[dict[str, Any]]) -> str:
    reasons = [row["hybrid"]["rejection_reason"] for row in per_run] + [row["experimental"]["rejection_reason"] for row in per_run]
    return most_common([reason for reason in reasons if reason])


def most_common(values: list[str]) -> str:
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]


def count_name(names: list[str], name: str) -> int:
    return sum(1 for item in names if item == name)


def exact_name_possible(name: str, *name_lists: list[str]) -> bool:
    lowered = name.casefold()
    return any(any(lowered in str(item).casefold() or str(item).casefold() in lowered for item in names) for names in name_lists)
