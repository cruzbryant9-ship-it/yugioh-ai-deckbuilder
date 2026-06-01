from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.card_limits import CUSTOM_CARD_LIMITS, get_blocked_card_names, normalize_card_name
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text, safe_load_json


MEMORY_DIR = Path("SystemAIYugioh") / "data" / "deck_profiles"
REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "legacy_memory_review"
STALE_MEMORY_DAYS = 3.0
CURRENT_PHASE = "phase6"


MEMORY_TARGETS = {
    "learned_card_stats": "learned_card_stats.json",
    "learning_tuning": "learning_tuning.json",
    "learned_engine_stats": "learned_engine_stats.json",
    "post_side_memory": "post_side_stats.json",
    "generic_ratio_memory": "generic_ratio_memory.json",
    "generic_benchmark_history": "generic_benchmark_history.json",
    "generic_diff_index": "generic_diff_index.json",
    "generic_filler_memory": "generic_filler_memory.json",
    "matchup_engine_stats": "matchup_engine_stats.json",
    "curated_opponent_memory": "curated_opponent_memory.json",
}


LEGACY_MEMORY_NAMES = {
    "learned_card_stats",
    "learning_tuning",
    "learned_engine_stats",
    "post_side_memory",
}


PHASE6_FIELD_HINTS = {
    "learned_card_stats": ("playable_hand_rate", "package_quality_score", "graph_valid_line_rate"),
    "learning_tuning": ("card_adjustments", "package_quality_score", "playable_hand_rate"),
    "learned_engine_stats": ("engine_adjustments", "playable_hand_rate", "package_quality_score"),
    "post_side_memory": ("post_side_delta", "valid_candidate_rate", "optimization_used"),
    "generic_ratio_memory": ("best_package_ratios", "targeted_recommendation_history", "last_update_provenance"),
    "generic_benchmark_history": ("latest_diagnosis", "trend_direction", "repair_reliability"),
    "generic_diff_index": ("provenance", "helpful_cards", "harmful_cards"),
    "generic_filler_memory": ("cross_archetype_index", "completion_bias_flag", "average_attribution_confidence"),
    "matchup_engine_stats": ("recommended_engine_by_matchup", "side_deck_compatibility", "rankings"),
    "curated_opponent_memory": ("best_engine_variants", "side_in_card_success_counts", "post_side_validity_history"),
}


PROBE_TERMS = (
    "Index Probe",
    "Card Probe",
    "Warning Probe",
    "Helpful Add",
    "Harmful Add",
    "Helpful Remove",
    "Harmful Remove",
    "Probe Card",
)


REFRESH_COMMANDS = {
    "learned_card_stats": [
        'python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 20',
        'python evaluate_learning.py --archetype "Blue-Eyes" --mode meta --runs 10',
    ],
    "learning_tuning": [
        'python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 20',
    ],
    "learned_engine_stats": [
        'python compare_engines.py --archetype "Blue-Eyes" --mode meta --runs-per-engine 3',
    ],
    "post_side_memory": [
        'python post_side_evaluator.py --archetype "Blue-Eyes" --mode meta --matchup combo --going second --runs 5',
    ],
    "generic_ratio_memory": [
        "python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5",
    ],
    "generic_benchmark_history": [
        "python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5",
    ],
    "generic_diff_index": [
        "python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 5 --show-replay",
    ],
    "generic_filler_memory": [
        "python single_filler_attribution_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 3",
        "python filler_signal_gate_report.py",
    ],
    "matchup_engine_stats": [
        'python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 3 --use-curated-opponents',
    ],
    "curated_opponent_memory": [
        'python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 3 --use-curated-opponents',
        'python analyze_opponent_deck.py --decklist sample_opponent_deck.txt --archetype "Blue-Eyes" --mode meta --going second',
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review legacy/stale memory files and recommend refresh, quarantine, or retirement.")
    parser.add_argument("--no-save", action="store_true", help="Print the review without writing report files.")
    return parser.parse_args()


def build_legacy_memory_review() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    memories = [review_memory(name, filename, now) for name, filename in MEMORY_TARGETS.items()]
    return {
        "report_type": "legacy_memory_review",
        "report_version": "stabilization-j-v1",
        "created_at_utc": now.isoformat(),
        "summary": summarize_reviews(memories),
        "memories": memories,
        "refresh_commands": {memory["name"]: memory.get("suggested_refresh_commands", []) for memory in memories},
        "quarantine_behavior": {
            "automatic_delete": False,
            "automatic_quarantine": False,
            "copy_only_helper": "SystemAIYugioh.memory_quarantine.quarantine_memory_file",
        },
    }


def review_memory(name: str, filename: str, now: datetime) -> dict[str, Any]:
    path = MEMORY_DIR / filename
    payload = safe_load_json(path, None)
    exists = path.exists()
    stat = path.stat() if exists else None
    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc) if stat else None
    age_days = round((now - modified).total_seconds() / 86400, 2) if modified else None
    schema_version = payload.get("version") if isinstance(payload, dict) else None
    record_count = estimate_record_count(payload)
    provenance = provenance_coverage(payload)
    blocked_scan = scan_blocked_and_probe_terms(payload)
    missing_fields = missing_phase6_fields(name, payload)
    compatibility = compatibility_status(name, missing_fields, payload)
    stale = bool(age_days is not None and age_days > STALE_MEMORY_DAYS)
    recommendation = recommend_action(name, exists, stale, blocked_scan, provenance, compatibility, record_count)
    return {
        "name": name,
        "path": str(path),
        "exists": exists,
        "size_bytes": stat.st_size if stat else 0,
        "last_modified_utc": modified.isoformat() if modified else None,
        "age_days": age_days,
        "stale": stale,
        "schema_version": schema_version,
        "record_count": record_count,
        "provenance": provenance,
        "missing_fields": missing_fields,
        "blocked_card_contamination": blocked_scan["blocked"],
        "validator_probe_contamination": blocked_scan["probes"],
        "blocked_or_invalid_memory_scan": blocked_scan,
        "phase6_metric_compatibility": compatibility,
        "recommendation": recommendation,
        "suggested_refresh_commands": REFRESH_COMMANDS.get(name, []),
        "quarantine_recommended": recommendation == "quarantine",
        "retirement_candidate": recommendation == "retire",
    }


def recommend_action(
    name: str,
    exists: bool,
    stale: bool,
    contamination: dict[str, Any],
    provenance: dict[str, Any],
    compatibility: str,
    record_count: int,
) -> str:
    if not exists or record_count == 0:
        return "collect_more_data"
    if contamination.get("blocked", {}).get("total_hits", 0) or contamination.get("probes", {}).get("total_hits", 0):
        return "quarantine"
    if provenance.get("validator_generated_entries", 0) and provenance.get("coverage_ratio", 0) >= 0.5:
        return "quarantine"
    if name in LEGACY_MEMORY_NAMES and (stale or compatibility in {"legacy_partial", "legacy_missing_current_metrics"}):
        return "refresh"
    if compatibility == "incompatible":
        return "retire"
    if name == "generic_filler_memory":
        return "collect_more_data"
    return "keep_active"


def compatibility_status(name: str, missing_fields: list[str], payload: Any) -> str:
    if not isinstance(payload, dict):
        return "incompatible"
    if name in LEGACY_MEMORY_NAMES and missing_fields:
        return "legacy_missing_current_metrics"
    if missing_fields:
        return "phase6_partial"
    return "phase6_compatible"


def missing_phase6_fields(name: str, payload: Any) -> list[str]:
    hints = PHASE6_FIELD_HINTS.get(name, ())
    if not isinstance(payload, dict):
        return list(hints)
    haystack = flatten_strings(payload, limit=200000)
    return [field for field in hints if field not in haystack]


def provenance_coverage(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "provenance_log_count": 0,
            "validator_generated_entries": 0,
            "last_update_has_provenance": False,
            "coverage_ratio": 0.0,
        }
    logs = payload.get("provenance_log", []) if isinstance(payload.get("provenance_log"), list) else []
    validator = sum(1 for row in logs if isinstance(row, dict) and row.get("validator_generated"))
    last = payload.get("last_update_provenance", {})
    profile_total = max(1, estimate_record_count(payload))
    coverage = min(1.0, (len(logs) + (1 if isinstance(last, dict) and last else 0)) / profile_total)
    return {
        "provenance_log_count": len(logs),
        "validator_generated_entries": validator,
        "last_update_has_provenance": bool(isinstance(last, dict) and last),
        "coverage_ratio": round(coverage, 4),
    }


def scan_blocked_and_probe_terms(payload: Any) -> dict[str, Any]:
    blocked_terms = set(get_blocked_card_names())
    raw_terms = set(CUSTOM_CARD_LIMITS)
    probe_terms = set(PROBE_TERMS)
    occurrences: Counter[str] = Counter()
    probe_occurrences: Counter[str] = Counter()
    for text in iter_text_values(payload):
        normalized = normalize_card_name(text)
        if normalized in blocked_terms:
            occurrences[text] += 1
        else:
            for raw in raw_terms:
                if normalize_card_name(raw) in normalized:
                    occurrences[raw] += 1
        for probe in probe_terms:
            if probe.casefold() in text.casefold():
                probe_occurrences[probe] += 1
    return {
        "blocked": {
            "total_hits": sum(occurrences.values()),
            "hits_by_term": dict(sorted(occurrences.items())),
        },
        "probes": {
            "total_hits": sum(probe_occurrences.values()),
            "hits_by_term": dict(sorted(probe_occurrences.items())),
        },
    }


def iter_text_values(value: Any) -> list[str]:
    rows: list[str] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                rows.append(str(key))
                stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, (str, int, float, bool)):
            rows.append(str(item))
    return rows


def flatten_strings(value: Any, limit: int = 100000) -> str:
    rows = []
    size = 0
    for text in iter_text_values(value):
        rows.append(text)
        size += len(text)
        if size >= limit:
            break
    return "\n".join(rows)


def estimate_record_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    profiles = payload.get("profiles")
    if isinstance(profiles, dict):
        return count_leaf_profiles(profiles)
    if isinstance(payload.get("cross_archetype_index"), dict):
        return len(payload.get("cross_archetype_index", {}))
    return len(payload)


def count_leaf_profiles(value: Any) -> int:
    if not isinstance(value, dict) or not value:
        return 0
    child_dicts = [child for child in value.values() if isinstance(child, dict)]
    if not child_dicts:
        return 1
    return sum(count_leaf_profiles(child) for child in child_dicts)


def summarize_reviews(memories: list[dict[str, Any]]) -> dict[str, Any]:
    recommendations = Counter(memory.get("recommendation") for memory in memories)
    stale = [memory["name"] for memory in memories if memory.get("stale")]
    contaminated = [
        memory["name"]
        for memory in memories
        if memory.get("blocked_card_contamination", {}).get("total_hits", 0)
        or memory.get("validator_probe_contamination", {}).get("total_hits", 0)
    ]
    return {
        "memory_count": len(memories),
        "stale_memories": stale,
        "contaminated_memories": contaminated,
        "recommendation_counts": dict(recommendations),
        "refresh_candidates": [memory["name"] for memory in memories if memory.get("recommendation") == "refresh"],
        "quarantine_candidates": [memory["name"] for memory in memories if memory.get("recommendation") == "quarantine"],
        "retirement_candidates": [memory["name"] for memory in memories if memory.get("recommendation") == "retire"],
        "keep_active": [memory["name"] for memory in memories if memory.get("recommendation") == "keep_active"],
        "collect_more_data": [memory["name"] for memory in memories if memory.get("recommendation") == "collect_more_data"],
    }


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"{timestamp}_legacy_memory_review.json"
    latest_json = REPORT_DIR / "latest_legacy_memory_review.json"
    markdown_path = REPORT_DIR / "latest_legacy_memory_review.md"
    atomic_write_json(json_path, report)
    atomic_write_json(latest_json, report)
    atomic_write_text(markdown_path, render_markdown(report, latest_json))
    return latest_json, markdown_path


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Legacy Memory Review",
        "",
        f"- Created: {report.get('created_at_utc')}",
        f"- JSON report: `{json_path}`",
        f"- Memories reviewed: {summary.get('memory_count', 0)}",
        f"- Stale memories: {', '.join(summary.get('stale_memories', []) or ['none'])}",
        f"- Contaminated memories: {', '.join(summary.get('contaminated_memories', []) or ['none'])}",
        f"- Refresh candidates: {', '.join(summary.get('refresh_candidates', []) or ['none'])}",
        f"- Quarantine candidates: {', '.join(summary.get('quarantine_candidates', []) or ['none'])}",
        f"- Retirement candidates: {', '.join(summary.get('retirement_candidates', []) or ['none'])}",
        "",
        "## Review Table",
        "",
        "| Memory | Records | Age Days | Compatibility | Blocked Hits | Probe Hits | Recommendation |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for memory in report.get("memories", []):
        lines.append(
            f"| {memory.get('name')} | {memory.get('record_count', 0)} | {memory.get('age_days')} | "
            f"{memory.get('phase6_metric_compatibility')} | "
            f"{memory.get('blocked_card_contamination', {}).get('total_hits', 0)} | "
            f"{memory.get('validator_probe_contamination', {}).get('total_hits', 0)} | "
            f"{memory.get('recommendation')} |"
        )
    lines.extend(["", "## Refresh Commands", ""])
    for name, commands in report.get("refresh_commands", {}).items():
        if not commands:
            continue
        lines.append(f"### {name}")
        for command in commands:
            lines.append(f"- `{command}`")
        lines.append("")
    lines.extend(
        [
            "## Quarantine Behavior",
            "",
            "- The review does not quarantine or delete production memory automatically.",
            "- Use `SystemAIYugioh.memory_quarantine.quarantine_memory_file()` to copy a selected memory into quarantine.",
            "- The helper writes a manifest and preserves timestamps with `shutil.copy2`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    report = build_legacy_memory_review()
    if not args.no_save:
        json_path, markdown_path = save_reports(report)
    else:
        json_path = markdown_path = None
    summary = report["summary"]
    print("\nLegacy Memory Review Complete")
    print(f"Memories reviewed: {summary['memory_count']}")
    print(f"Stale memories: {', '.join(summary['stale_memories']) or 'none'}")
    print(f"Contaminated memories: {', '.join(summary['contaminated_memories']) or 'none'}")
    print(f"Refresh candidates: {', '.join(summary['refresh_candidates']) or 'none'}")
    print(f"Quarantine candidates: {', '.join(summary['quarantine_candidates']) or 'none'}")
    print(f"Retirement candidates: {', '.join(summary['retirement_candidates']) or 'none'}")
    if json_path and markdown_path:
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
