from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deck.builder import score_deck_breakdown
from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_deck_builder import build_generic_deck, primary_role, recompute_package_counts
from deck.generic_filler_impact import analyze_filler_impact
from deck.generic_filler_memory import update_generic_filler_memory
from deck.generic_filler_selector import classify_filler_role
from filler_signal_gate_report import build_filler_signal_gate_report, save_gate_report
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.memory_context import normalize_provenance


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "filler_attribution"
REPORT_VERSION = "phase6r-v1"
DEFAULT_FILLER_CANDIDATES = [
    "Infinite Impermanence",
    "Ash Blossom & Joyous Spring",
    "Effect Veiler",
    "Droll & Lock Bird",
    "Nibiru, the Primal Being",
    "D.D. Crow",
    "Ghost Belle & Haunted Mansion",
    "Cosmic Cyclone",
    "Lightning Storm",
    "Evenly Matched",
]
EXTRA_ARCHETYPE_CANDIDATES = ["Tearlaments", "Labrynth", "Branded", "Kashtira", "Runick"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect clean single-card filler attribution evidence.")
    parser.add_argument("--archetypes", nargs="+", default=["Branded", "Kashtira", "Runick"])
    parser.add_argument("--mode", default="meta", choices=("meta", "innovation"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fillers", nargs="*", default=DEFAULT_FILLER_CANDIDATES)
    parser.add_argument("--no-auto-extra-archetype", action="store_true")
    return parser.parse_args()


def run_attribution_benchmark(
    archetypes: list[str],
    mode: str = "meta",
    runs: int = 3,
    fillers: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
    auto_extra_archetype: bool = True,
) -> dict[str, Any]:
    fillers = fillers or DEFAULT_FILLER_CANDIDATES
    provenance = normalize_provenance(provenance, source="filler_attribution_benchmark", smoke=runs <= 1)
    cards = CardDatabase().load_cards()
    archetypes = expand_archetypes(archetypes, cards, auto_extra_archetype=auto_extra_archetype)
    lookup = card_lookup(cards)
    results: list[dict[str, Any]] = []
    memory_updates: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for archetype in archetypes:
        for run_index in range(max(1, int(runs or 1))):
            baseline_deck, baseline_report = build_generic_deck(archetype, cards, mode=mode, use_ratio_memory=False)
            baseline_score = score_deck_breakdown(baseline_deck, archetype, mode)
            baseline_main, baseline_extra = split_deck(baseline_deck)
            baseline_snapshot = score_snapshot(baseline_score, baseline_report, baseline_main)
            for filler_name in fillers:
                row = run_single_filler_test(
                    archetype,
                    mode,
                    run_index + 1,
                    filler_name,
                    lookup,
                    baseline_deck,
                    baseline_main,
                    baseline_extra,
                    baseline_report,
                    baseline_snapshot,
                )
                results.append(row)
                impact = row.get("impact_report")
                if impact:
                    memory_updates[archetype].append(impact)

    memory_update_summary = {}
    for archetype, impacts in memory_updates.items():
        profile = update_generic_filler_memory(archetype, mode, impacts, provenance=provenance)
        memory_update_summary[archetype] = {
            "impact_events": len(impacts),
            "updated": bool(profile),
            "fillers": sorted((profile.get("fillers", {}) if isinstance(profile, dict) else {}).keys()),
        }

    gate_report = build_filler_signal_gate_report()
    report = {
        "report_type": "single_filler_attribution_benchmark",
        "report_version": REPORT_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {"archetypes": archetypes, "mode": mode, "runs": runs, "fillers": fillers},
        "provenance": provenance,
        "summary": summarize_results(results, gate_report),
        "memory_update_summary": memory_update_summary,
        "results": strip_internal_impacts(results),
        "gate_report": gate_report,
    }
    return report


def run_single_filler_test(
    archetype: str,
    mode: str,
    run_index: int,
    filler_name: str,
    lookup: dict[str, dict[str, Any]],
    baseline_deck: list[dict[str, Any]],
    baseline_main: list[dict[str, Any]],
    baseline_extra: list[dict[str, Any]],
    baseline_report: dict[str, Any],
    baseline_snapshot: dict[str, Any],
) -> dict[str, Any]:
    candidate_card = lookup.get(filler_name)
    if not candidate_card:
        return failed_row(archetype, mode, run_index, filler_name, "candidate_not_found")
    if get_card_limit(candidate_card) <= 0:
        return failed_row(archetype, mode, run_index, filler_name, "candidate_blocked_or_forbidden")
    candidate = build_candidate_deck_with_one_filler(baseline_main, baseline_extra, candidate_card, baseline_report)
    if not candidate.get("valid"):
        return failed_row(archetype, mode, run_index, filler_name, str(candidate.get("failure_reason", "candidate_build_failed")))

    candidate_deck = candidate["deck"]
    candidate_main, candidate_extra = split_deck(candidate_deck)
    blocked = blocked_card_violations(candidate_deck)
    legal = len(candidate_main) == 40 and len(candidate_extra) <= 15 and not blocked and not copy_limit_violations(candidate_deck)
    candidate_score = score_deck_breakdown(candidate_deck, archetype, mode)
    candidate_snapshot = {
        "score": candidate_score.get("final_score", 0),
        "confidence": baseline_snapshot.get("confidence", 0),
        "main_count": len(candidate_main),
        "package_counts": dict(recompute_package_counts(candidate_main)),
        "selected_fillers": [filler_name],
        "filler_roles": filler_roles_for([candidate_card]),
        "pre_contextual_filler_main_count": len(baseline_main),
        "quota_warnings": [],
        "remaining_warnings": [],
        "blocked_card_violations": blocked,
        "legal_observation": legal,
    }
    diff = deck_copy_delta(baseline_main, candidate_main)
    attribution = classify_attribution_event(filler_name, diff, legal)
    impact = make_impact_report(archetype, mode, baseline_snapshot, candidate_snapshot, attribution, [filler_name])
    return {
        "archetype": archetype,
        "mode": mode,
        "run": run_index,
        "candidate_filler": filler_name,
        "removed_card": candidate.get("removed_card"),
        "baseline_score": round(float(baseline_snapshot.get("score", 0) or 0), 4),
        "candidate_score": round(float(candidate_snapshot.get("score", 0) or 0), 4),
        "score_delta": impact.get("score_delta", 0),
        "confidence_delta": impact.get("confidence_delta", 0),
        "clean_single_card_attribution": attribution["clean"],
        "attribution_model": impact.get("attribution_model"),
        "attribution_confidence": impact.get("attribution_confidence"),
        "failure_reason": attribution.get("failure_reason"),
        "legal": legal,
        "blocked_card_violations": blocked,
        "copy_limit_violations": copy_limit_violations(candidate_deck),
        "deck_delta": diff,
        "impact_classification": impact.get("impact_classification", {}),
        "event_impact_classification": impact.get("event_impact_classification"),
        "impact_report": impact,
    }


def build_candidate_deck_with_one_filler(
    baseline_main: list[dict[str, Any]],
    baseline_extra: list[dict[str, Any]],
    candidate_card: dict[str, Any],
    baseline_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = Counter(card_name(card) for card in baseline_main + baseline_extra)
    candidate_name = card_name(candidate_card)
    if counts[candidate_name] >= get_card_limit(candidate_card):
        return {"valid": False, "failure_reason": "candidate_copy_limit_reached"}
    replacement_index = choose_replacement_index(baseline_main, candidate_name, baseline_report or {})
    if replacement_index is None:
        return {"valid": False, "failure_reason": "no_replacement_card_available"}
    candidate_main = list(baseline_main)
    removed = candidate_main[replacement_index]
    candidate_main[replacement_index] = candidate_card
    return {
        "valid": True,
        "deck": candidate_main + list(baseline_extra),
        "main": candidate_main,
        "extra": list(baseline_extra),
        "removed_card": card_name(removed),
    }


def choose_replacement_index(baseline_main: list[dict[str, Any]], candidate_name: str, baseline_report: dict[str, Any]) -> int | None:
    preferred_names = [name for name in baseline_report.get("selected_fillers", []) or [] if name != candidate_name]
    for preferred in preferred_names:
        for index, card in enumerate(baseline_main):
            if card_name(card) == preferred:
                return index
    filler_names = set(DEFAULT_FILLER_CANDIDATES) - {candidate_name}
    for index, card in enumerate(baseline_main):
        if card_name(card) in filler_names:
            return index
    role_priority = {
        "board_breakers": 0,
        "interruptions": 1,
        "recovery": 2,
        "core": 3,
        "extenders": 4,
        "starters_searchers": 5,
        "payoffs": 6,
        "garnet_brick": 7,
    }
    ordered = sorted(enumerate(baseline_main), key=lambda item: (role_priority.get(primary_role(item[1]), 4), card_name(item[1])))
    return ordered[0][0] if ordered else None


def classify_attribution_event(candidate_name: str, diff: dict[str, Any], legal: bool) -> dict[str, Any]:
    increases = diff.get("copy_increases", {})
    decreases = diff.get("copy_decreases", {})
    clean = (
        legal
        and increases == {candidate_name: 1}
        and sum(abs(int(value)) for value in decreases.values()) == 1
        and len(decreases) == 1
    )
    if clean:
        return {"clean": True, "failure_reason": None, "attribution_model": "single_card"}
    reasons = []
    if not legal:
        reasons.append("candidate_deck_illegal")
    if increases.get(candidate_name) != 1 or len(increases) != 1:
        reasons.append("candidate_not_unique_added_card")
    if sum(abs(int(value)) for value in decreases.values()) != 1 or len(decreases) != 1:
        reasons.append("replacement_not_single_card")
    return {"clean": False, "failure_reason": ",".join(reasons) or "not_clean_single_card", "attribution_model": "shared"}


def make_impact_report(
    archetype: str,
    mode: str,
    baseline_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    attribution: dict[str, Any],
    filler_cards: list[str],
) -> dict[str, Any]:
    impact = analyze_filler_impact(archetype, mode, baseline_snapshot, candidate_snapshot)
    if attribution.get("clean"):
        impact["attribution_model"] = "single_card"
        impact["attribution_shared"] = False
        impact["attribution_confidence"] = 1.0
        impact["attributed_score_delta"] = impact.get("score_delta", 0)
        impact["attributed_confidence_delta"] = impact.get("confidence_delta", 0)
    else:
        impact["filler_cards"] = filler_cards
        impact["attribution_model"] = "shared"
        impact["attribution_shared"] = True
        impact["attribution_confidence"] = round(1.0 / max(2, len(filler_cards)), 4)
        impact["attributed_score_delta"] = round(float(impact.get("score_delta", 0) or 0) * impact["attribution_confidence"], 4)
        impact["attributed_confidence_delta"] = round(float(impact.get("confidence_delta", 0) or 0) * impact["attribution_confidence"], 4)
        impact["impact_classification"] = {card: "indeterminate" for card in filler_cards}
        impact["event_impact_classification"] = "indeterminate"
        impact["indeterminate_fillers"] = list(filler_cards)
        impact.setdefault("risk_flags", []).append("unclean_single_card_attribution")
    impact["clean_single_card_attribution"] = bool(attribution.get("clean"))
    impact["clean_attribution_failure_reason"] = attribution.get("failure_reason")
    return impact


def deck_copy_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    before_counts = Counter(card_name(card) for card in before)
    after_counts = Counter(card_name(card) for card in after)
    names = sorted(set(before_counts) | set(after_counts))
    increases = {name: after_counts[name] - before_counts[name] for name in names if after_counts[name] > before_counts[name]}
    decreases = {name: before_counts[name] - after_counts[name] for name in names if before_counts[name] > after_counts[name]}
    return {
        "copy_increases": increases,
        "copy_decreases": decreases,
        "cards_added": sorted(increases),
        "cards_removed": sorted(decreases),
    }


def score_snapshot(score: dict[str, Any], build_report: dict[str, Any], main_deck: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "score": score.get("final_score", 0),
        "confidence": build_report.get("generic_confidence_score", 0),
        "main_count": len(main_deck),
        "package_counts": build_report.get("package_counts", dict(recompute_package_counts(main_deck))),
    }


def summarize_results(results: list[dict[str, Any]], gate_report: dict[str, Any]) -> dict[str, Any]:
    clean = [row for row in results if row.get("clean_single_card_attribution")]
    failed = [row for row in results if not row.get("clean_single_card_attribution")]
    deltas: dict[str, list[float]] = defaultdict(list)
    breadth: dict[str, set[str]] = defaultdict(set)
    for row in clean:
        name = str(row.get("candidate_filler"))
        deltas[name].append(float(row.get("score_delta", 0) or 0))
        breadth[name].add(str(row.get("archetype")))
    return {
        "total_tests": len(results),
        "clean_single_card_events": len(clean),
        "shared_or_failed_attribution_events": len(failed),
        "score_deltas_by_filler": {
            name: {
                "count": len(values),
                "average_delta": round(sum(values) / max(1, len(values)), 4),
                "min_delta": round(min(values), 4),
                "max_delta": round(max(values), 4),
            }
            for name, values in sorted(deltas.items())
        },
        "archetype_breadth_by_filler": {name: sorted(values) for name, values in sorted(breadth.items())},
        "gate_progress": gate_report.get("summary", {}),
        "cards_closest_to_eligibility": gate_report.get("summary", {}).get("cards_closest_to_eligibility", []),
        "eligible_signal_count": gate_report.get("summary", {}).get("eligible_count", 0),
    }


def expand_archetypes(archetypes: list[str], cards: list[dict[str, Any]], auto_extra_archetype: bool = True) -> list[str]:
    ordered = []
    seen = set()
    for archetype in archetypes:
        key = str(archetype).casefold()
        if key not in seen:
            ordered.append(str(archetype))
            seen.add(key)
    if not auto_extra_archetype or len(ordered) >= 4:
        return ordered
    for candidate in EXTRA_ARCHETYPE_CANDIDATES:
        if candidate.casefold() in seen:
            continue
        if any(candidate.casefold() in str(card.get("archetype", "")).casefold() for card in cards):
            ordered.append(candidate)
            break
    return ordered


def copy_limit_violations(deck: list[dict[str, Any]]) -> list[str]:
    counts = Counter(card_name(card) for card in deck)
    by_name = {card_name(card): card for card in deck}
    return [f"{name} {count}>{get_card_limit(by_name[name])}" for name, count in counts.items() if count > get_card_limit(by_name[name])]


def card_lookup(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {card_name(card): card for card in cards if card_name(card)}


def filler_roles_for(cards: list[dict[str, Any]]) -> dict[str, Any]:
    by_card = {card_name(card): classify_filler_role(card) for card in cards}
    return {"counts": dict(Counter(by_card.values())), "by_card": by_card}


def strip_internal_impacts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped = []
    for row in results:
        copy = dict(row)
        copy.pop("impact_report", None)
        stripped.append(copy)
    return stripped


def failed_row(archetype: str, mode: str, run_index: int, filler_name: str, reason: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "mode": mode,
        "run": run_index,
        "candidate_filler": filler_name,
        "clean_single_card_attribution": False,
        "attribution_model": "none",
        "attribution_confidence": 0.0,
        "failure_reason": reason,
        "legal": False,
        "score_delta": 0.0,
        "confidence_delta": 0.0,
        "impact_classification": {},
    }


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Single-Card Filler Attribution Benchmark",
        "",
        f"- JSON report: `{json_path}`",
        f"- Mode: {report.get('config', {}).get('mode')}",
        f"- Archetypes: {', '.join(report.get('config', {}).get('archetypes', []))}",
        f"- Clean single-card events: {summary.get('clean_single_card_events', 0)}",
        f"- Shared/failed attribution events: {summary.get('shared_or_failed_attribution_events', 0)}",
        f"- Eligible filler signals after run: {summary.get('eligible_signal_count', 0)}",
        f"- Cards closest to eligibility: {', '.join(summary.get('cards_closest_to_eligibility', []) or ['none'])}",
        "",
        "## Score Deltas By Filler",
        "",
        "| Filler | Events | Avg Delta | Min | Max | Archetype Breadth |",
        "|---|---:|---:|---:|---:|---|",
    ]
    deltas = summary.get("score_deltas_by_filler", {})
    breadth = summary.get("archetype_breadth_by_filler", {})
    if deltas:
        for name, stats in deltas.items():
            lines.append(
                f"| {name} | {stats.get('count', 0)} | {stats.get('average_delta', 0)} | "
                f"{stats.get('min_delta', 0)} | {stats.get('max_delta', 0)} | {', '.join(breadth.get(name, []))} |"
            )
    else:
        lines.append("| none | 0 | 0 | 0 | 0 | none |")
    lines.extend(["", "## Gate Progress", ""])
    gate = summary.get("gate_progress", {})
    for key in ("eligible_count", "near_eligible_count", "failed_count", "failure_counts", "cards_closest_to_eligibility"):
        lines.append(f"- {key}: {gate.get(key)}")
    lines.extend(["", "## Clean Events", ""])
    for row in [row for row in report.get("results", []) if row.get("clean_single_card_attribution")][:40]:
        lines.append(
            f"- {row.get('archetype')} run {row.get('run')}: {row.get('candidate_filler')} "
            f"over {row.get('removed_card')} delta {row.get('score_delta')}"
        )
    if not any(row.get("clean_single_card_attribution") for row in report.get("results", [])):
        lines.append("- None")
    lines.extend(["", "## Failed Or Shared Events", ""])
    for row in [row for row in report.get("results", []) if not row.get("clean_single_card_attribution")][:40]:
        lines.append(f"- {row.get('archetype')} {row.get('candidate_filler')}: {row.get('failure_reason')}")
    return "\n".join(lines) + "\n"


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = "_".join(report.get("config", {}).get("archetypes", [])).lower().replace(" ", "_")
    json_path = REPORT_DIR / f"{timestamp}_{slug}_{report.get('config', {}).get('mode', 'meta')}_filler_attribution.json"
    markdown_path = REPORT_DIR / "latest_filler_attribution_report.md"
    atomic_write_json(json_path, report)
    atomic_write_text(markdown_path, render_markdown(report, json_path))
    save_gate_report(report.get("gate_report", {}) or build_filler_signal_gate_report())
    return json_path, markdown_path


def card_name(card: dict[str, Any]) -> str:
    return str(card.get("name", ""))


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be 1 or greater.")
    report = run_attribution_benchmark(
        args.archetypes,
        mode=args.mode,
        runs=args.runs,
        fillers=args.fillers,
        auto_extra_archetype=not args.no_auto_extra_archetype,
    )
    json_path, markdown_path = save_reports(report)
    summary = report["summary"]
    print("\nSingle-Card Filler Attribution Benchmark Complete")
    print(f"Archetypes tested: {', '.join(report['config']['archetypes'])}")
    print(f"Clean single-card events: {summary['clean_single_card_events']}")
    print(f"Shared/failed attribution events: {summary['shared_or_failed_attribution_events']}")
    print(f"Eligible filler signals after run: {summary['eligible_signal_count']}")
    print(f"Cards closest to eligibility: {summary.get('cards_closest_to_eligibility', [])}")
    print(f"Score deltas by filler: {summary.get('score_deltas_by_filler', {})}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
