from __future__ import annotations

from collections import Counter
from typing import Any

from deck.deck_utils import split_deck
from deck.generic_card_shift_explainer import explain_card_shifts, normalize_role


def build_package_replay_report(
    archetype: str,
    baseline_deck: list[Any],
    candidate_deck: list[Any],
    role_map: dict[str, str] | None,
    package_data: dict[str, Any] | None,
    score_delta: float,
) -> dict[str, Any]:
    lookup = build_role_lookup(role_map or {}, package_data or {})
    baseline_main, baseline_extra = split_deck_objects(baseline_deck)
    candidate_main, candidate_extra = split_deck_objects(candidate_deck)
    shift = explain_card_shifts(baseline_deck, candidate_deck, role_map or {}, package_data or {}, score_delta)
    before_counts = package_counts(baseline_main, lookup)
    after_counts = package_counts(candidate_main, lookup)
    package_delta = compute_package_delta(before_counts, after_counts)
    report = {
        "archetype": archetype,
        "score_delta": round(float(score_delta or 0), 4),
        "before_main_package_counts": before_counts,
        "after_main_package_counts": after_counts,
        "before_main_count": len(baseline_main),
        "after_main_count": len(candidate_main),
        "before_extra_count": len(baseline_extra),
        "after_extra_count": len(candidate_extra),
        "cards_added": shift["cards_added"],
        "cards_removed": shift["cards_removed"],
        "copy_increases": shift["copy_increases"],
        "copy_decreases": shift["copy_decreases"],
        "role_gains_losses": shift["role_delta"],
        "package_gains_losses": package_delta,
        "risk_flags": shift["risk_flags"],
        "short_explanation": shift["explanation"],
        "compact_card_delta_table": compact_card_delta_table(shift),
    }
    report["markdown_section"] = render_markdown_section(report)
    return report


def split_deck_objects(deck: list[Any]) -> tuple[list[Any], list[Any]]:
    if not deck:
        return [], []
    if all(isinstance(card, dict) for card in deck):
        main, extra = split_deck(deck)
        return main, extra
    return list(deck), []


def build_role_lookup(role_map: dict[str, str], package_data: dict[str, Any]) -> dict[str, str]:
    lookup = {str(name): normalize_role(role) for name, role in role_map.items()}
    analysis = package_data.get("analysis", {}) if isinstance(package_data, dict) else {}
    roles = analysis.get("roles", {}) if isinstance(analysis, dict) else {}
    if isinstance(roles, dict):
        for role, names in roles.items():
            for name in names or []:
                lookup.setdefault(str(name), normalize_role(str(role)))
    for package in package_data.get("packages", []) if isinstance(package_data, dict) else []:
        package_type = normalize_role(str(package.get("package_type", "unknown")))
        for name in package.get("card_names", []) or []:
            lookup.setdefault(str(name), package_type)
    return lookup


def package_counts(deck: list[Any], role_lookup: dict[str, str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for card in deck:
        name = card_name(card)
        role = role_lookup.get(name, infer_role_from_card(card))
        counts[role] += 1
    return dict(sorted(counts.items()))


def compute_package_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in keys if int(after.get(key, 0)) != int(before.get(key, 0))}


def compact_card_delta_table(shift: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    names = sorted(set(shift.get("copy_increases", {})) | set(shift.get("copy_decreases", {})))
    for name in names:
        increase = int(shift.get("copy_increases", {}).get(name, 0) or 0)
        decrease = int(shift.get("copy_decreases", {}).get(name, 0) or 0)
        rows.append({"card": name, "delta": increase - decrease, "change": "added/increased" if increase else "removed/decreased"})
    return rows


def render_markdown_section(report: dict[str, Any]) -> str:
    lines = [
        f"### {report.get('archetype', 'Unknown')} Package Replay",
        "",
        f"- Score delta: {report.get('score_delta', 0)}",
        f"- Main count: {report.get('before_main_count', 0)} -> {report.get('after_main_count', 0)}",
        f"- Extra count: {report.get('before_extra_count', 0)} -> {report.get('after_extra_count', 0)}",
        f"- Risk flags: {', '.join(report.get('risk_flags', []) or ['none'])}",
        f"- Explanation: {report.get('short_explanation', '')}",
        "",
        "| Package | Before | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    packages = sorted(set(report.get("before_main_package_counts", {})) | set(report.get("after_main_package_counts", {})))
    for package in packages:
        before = int(report.get("before_main_package_counts", {}).get(package, 0) or 0)
        after = int(report.get("after_main_package_counts", {}).get(package, 0) or 0)
        lines.append(f"| {package} | {before} | {after} | {after - before:+d} |")
    lines.extend(["", "| Card | Delta | Change |", "|---|---:|---|"])
    for row in report.get("compact_card_delta_table", [])[:12]:
        lines.append(f"| {row.get('card')} | {int(row.get('delta', 0)):+d} | {row.get('change')} |")
    if not report.get("compact_card_delta_table"):
        lines.append("| None | 0 | no change |")
    return "\n".join(lines)


def infer_role_from_card(card: Any) -> str:
    if not isinstance(card, dict):
        return "unknown"
    text = f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}".casefold()
    try:
        level = int(card.get("level") or 0)
    except (TypeError, ValueError):
        level = 0
    if level >= 7 and "special summon" not in text and "ritual" not in text:
        return "bricks"
    if "from your deck" in text or "add 1" in text or "search" in text:
        return "starters_searchers"
    if "special summon" in text:
        return "extenders"
    if "negate" in text or "quick effect" in text or "banish" in text or "destroy" in text:
        return "interruptions"
    if "from your gy" in text or "from your graveyard" in text or "in your gy" in text:
        return "recovery"
    return "core"


def card_name(card: Any) -> str:
    if isinstance(card, dict):
        return str(card.get("name", ""))
    return str(card or "")
