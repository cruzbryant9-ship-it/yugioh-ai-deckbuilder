from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from deck import advisory_influence_budget as advisory_budget_module
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text, safe_load_json


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "learning_signal_audit"
MEMORY_DIR = Path("SystemAIYugioh") / "data" / "deck_profiles"
TRAINING_RUNS_DIR = Path("SystemAIYugioh") / "data" / "training_runs"
STALE_MEMORY_DAYS = 3.0


SIGNAL_ORDER = [
    "learned_card_stats",
    "learning_tuning",
    "learned_engine_stats",
    "matchup_engine_stats",
    "post_side_memory",
    "curated_opponent_memory",
    "generic_ratio_memory",
    "generic_benchmark_history",
    "generic_diff_index",
    "generic_filler_memory",
    "filler_signal_gates",
    "diagnosis bias",
    "diff-index bias",
    "filler-memory bias",
]


MEMORY_FILES = {
    "learned_card_stats": "learned_card_stats.json",
    "learning_tuning": "learning_tuning.json",
    "learned_engine_stats": "learned_engine_stats.json",
    "matchup_engine_stats": "matchup_engine_stats.json",
    "post_side_memory": "post_side_stats.json",
    "curated_opponent_memory": "curated_opponent_memory.json",
    "generic_ratio_memory": "generic_ratio_memory.json",
    "generic_benchmark_history": "generic_benchmark_history.json",
    "generic_diff_index": "generic_diff_index.json",
    "generic_filler_memory": "generic_filler_memory.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit learning/advisory signal health and influence state.")
    parser.add_argument("--no-save", action="store_true", help="Build and print the audit without saving report files.")
    return parser.parse_args()


def build_learning_signal_audit() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    latest_reports = load_latest_reports()
    signals = [audit_signal(name, now, latest_reports) for name in SIGNAL_ORDER]
    summary = summarize_signals(signals)
    return {
        "report_type": "learning_signal_audit",
        "report_version": "stabilization-i-v1",
        "created_at_utc": now.isoformat(),
        "summary": summary,
        "signals": signals,
        "latest_report_inputs": {
            key: str(value.get("_path", "")) if isinstance(value, dict) else ""
            for key, value in latest_reports.items()
        },
    }


def audit_signal(name: str, now: datetime, latest_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    memory = memory_summary(name, now) if name in MEMORY_FILES else {}
    evidence: list[str] = []
    classification: list[str] = []
    active = False
    influence_level = "none"
    recommendation = "collect more data"

    if name == "learned_card_stats":
        active = True
        influence_level = "score_bonus_and_weighted_fallback"
        classification = ["active", "useful" if memory.get("profile_count") else "stale"]
        recommendation = "keep active"
        evidence.append("Used by deck.builder learned_card_weight() and score_deck_breakdown learned_card_bonus.")
    elif name == "learning_tuning":
        active = True
        influence_level = "weighted_random_fallback"
        classification = ["active", "stale" if memory.get("stale") else "useful"]
        recommendation = "collect more data"
        evidence.append("Used by deck.builder tuning_card_weight() in the weighted fallback path.")
    elif name == "learned_engine_stats":
        active = True
        influence_level = "weighted_random_fallback"
        classification = ["active", "stale" if memory.get("stale") else "useful"]
        recommendation = "collect more data"
        evidence.append("Used by deck.builder engine_card_weight() in the weighted fallback path.")
    elif name == "matchup_engine_stats":
        active = True
        influence_level = "matchup_engine_selection"
        classification = ["active", "useful"]
        recommendation = "keep active"
        matrix = latest_reports.get("matchup_matrix", {})
        evidence.append("Used by deck.builder when matchup/going context is provided.")
        evidence.append(f"Latest matrix updated stats: {bool(matrix.get('matchup_engine_stats_updated'))}.")
    elif name == "post_side_memory":
        active = True
        influence_level = "side_plan_optimization"
        classification = ["active", "useful" if memory.get("profile_count") else "stale"]
        recommendation = "keep active"
        evidence.append("Used by side_plan_optimizer side-in and side-out adjustment helpers.")
    elif name == "curated_opponent_memory":
        active = True
        influence_level = "opponent_specific_side_and_engine_selection"
        classification = ["active", "useful"]
        recommendation = "keep active"
        matrix = latest_reports.get("matchup_matrix", {})
        evidence.append("Used by side_plan_optimizer and matchup_engine_stats for curated opponents.")
        evidence.append(f"Latest matrix updated curated opponent memory: {bool(matrix.get('curated_opponent_memory_updated'))}.")
    elif name == "generic_ratio_memory":
        active = True
        influence_level = "generic_builder_ratio_profile"
        classification = ["active", "useful"]
        recommendation = "keep active"
        evidence.append("Used by generic_deck_builder when use_ratio_memory=True.")
    elif name == "generic_benchmark_history":
        active = True
        influence_level = "diagnosis_source"
        classification = ["active", "useful"]
        recommendation = "keep active"
        evidence.append("Used by generic_tuner through load_tuning_diagnosis() to drive diagnosis bias.")
    elif name == "generic_diff_index":
        active = True
        influence_level = "small_capped_advisory"
        latest_generic = latest_reports.get("generic_benchmark", {})
        used_count = int(latest_generic.get("summary", {}).get("diff_index_bias_used_count", 0) or 0)
        classification = ["active", "no-op" if used_count == 0 else "experimental", "noisy"]
        recommendation = "keep experimental"
        evidence.append("Used by generic_tuner get_diff_index_advisory_signal(); advisory-only and capped.")
        evidence.append(f"Latest generic benchmark diff-index bias used count: {used_count}.")
    elif name == "generic_filler_memory":
        active = False
        influence_level = "reporting_and_gate_input"
        classification = ["reporting-only", "unsafe-to-influence"]
        recommendation = "collect more data"
        evidence.append("Feeds filler_signal_gates and reports; influence is off by default.")
        evidence.append("Phase 6U still saw zero ordering/selection changes when the experiment flag was enabled.")
    elif name == "filler_signal_gates":
        active = False
        influence_level = "gate/report"
        classification = ["reporting-only", "useful"]
        recommendation = "keep active"
        gates = latest_reports.get("filler_gate", {})
        summary = gates.get("summary", {}) if isinstance(gates.get("summary"), dict) else {}
        evidence.append("Defines activation readiness; does not itself alter deck construction.")
        evidence.append(f"Activation-ready fillers: {', '.join(summary.get('activation_ready_fillers', []) or []) or 'none'}.")
    elif name == "diagnosis bias":
        active = True
        influence_level = "small_capped_ratio_nudge"
        latest_generic = latest_reports.get("generic_benchmark", {})
        count = int(latest_generic.get("summary", {}).get("advisory_bias_calibration", {}).get("diagnosis_bias_used_count", 0) or 0)
        classification = ["active", "useful" if count else "no-op"]
        recommendation = "keep active"
        evidence.append("generic_tuner applies small ratio nudges from generic_benchmark_history diagnoses.")
        evidence.append(f"Latest benchmark diagnosis bias used count: {count}.")
    elif name == "diff-index bias":
        active = True
        influence_level = "small_capped_advisory"
        latest_generic = latest_reports.get("generic_benchmark", {})
        count = int(latest_generic.get("summary", {}).get("diff_index_bias_used_count", 0) or 0)
        classification = ["active", "experimental", "no-op" if count == 0 else "noisy"]
        recommendation = "keep experimental"
        evidence.append("Uses scrubbed generic_diff_index signals as capped advisory nudges.")
        evidence.append(f"Latest benchmark diff-index bias used count: {count}.")
    elif name == "filler-memory bias":
        active = False
        influence_level = "disabled_by_default"
        ab = latest_reports.get("filler_ab", {})
        ab_summary = ab.get("summary", {}) if isinstance(ab.get("summary"), dict) else {}
        ordering = int(ab_summary.get("ordering_change_count", 0) or 0)
        selection = int(ab_summary.get("selection_change_count", 0) or 0)
        classification = ["no-op", "experimental", "unsafe-to-influence"]
        recommendation = "keep experimental"
        evidence.append(f"Experiment flag exists but default is {advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE}.")
        evidence.append(f"Latest Phase 6U A/B ordering changes: {ordering}; selection changes: {selection}.")

    if memory:
        if memory.get("stale") and "stale" not in classification:
            classification.append("stale")
        evidence.extend(memory.get("evidence", []))

    return {
        "name": name,
        "active": active,
        "influence_level": influence_level,
        "classification": stable_unique(classification),
        "memory": memory,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def memory_summary(name: str, now: datetime) -> dict[str, Any]:
    path = MEMORY_DIR / MEMORY_FILES[name]
    payload = safe_load_json(path, {})
    exists = path.exists()
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) if exists else None
    age_days = round((now - modified).total_seconds() / 86400, 2) if modified else None
    profile_count = count_profiles(payload)
    provenance_log = payload.get("provenance_log", []) if isinstance(payload, dict) else []
    validator_entries = sum(1 for row in provenance_log if isinstance(row, dict) and row.get("validator_generated"))
    evidence = []
    if exists:
        evidence.append(f"Memory file exists at {path} ({path.stat().st_size} bytes).")
    else:
        evidence.append(f"Memory file missing at {path}.")
    if modified:
        evidence.append(f"Last modified: {modified.isoformat()} ({age_days} days old).")
    if profile_count:
        evidence.append(f"Profile/record count estimate: {profile_count}.")
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified_at_utc": modified.isoformat() if modified else None,
        "age_days": age_days,
        "stale": bool(age_days is not None and age_days > STALE_MEMORY_DAYS),
        "profile_count": profile_count,
        "provenance_log_count": len(provenance_log) if isinstance(provenance_log, list) else 0,
        "validator_generated_provenance_count": validator_entries,
        "evidence": evidence,
    }


def count_profiles(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    profiles = payload.get("profiles")
    if isinstance(profiles, dict):
        return count_leaf_dicts(profiles)
    if "cross_archetype_index" in payload and isinstance(payload.get("cross_archetype_index"), dict):
        return len(payload.get("cross_archetype_index", {}))
    return len(payload) if payload else 0


def count_leaf_dicts(value: Any) -> int:
    if not isinstance(value, dict) or not value:
        return 0
    child_dicts = [child for child in value.values() if isinstance(child, dict)]
    if not child_dicts:
        return 1
    return sum(count_leaf_dicts(child) for child in child_dicts)


def load_latest_reports() -> dict[str, dict[str, Any]]:
    reports = {
        "filler_ab": load_report(TRAINING_RUNS_DIR / "filler_influence_ab" / "latest_filler_influence_ab_report.json"),
        "filler_gate": load_report(TRAINING_RUNS_DIR / "generic_benchmarks" / "latest_filler_signal_gate_report.json"),
        "filler_holdout": load_report(TRAINING_RUNS_DIR / "filler_holdout" / "latest_filler_holdout_report.json"),
        "generic_benchmark": load_report(latest_matching(TRAINING_RUNS_DIR / "generic_benchmarks", "*_generic_benchmark.json")),
        "matchup_matrix": load_report(latest_matching(TRAINING_RUNS_DIR / "matchup_matrix", "*_matchup_matrix.json")),
    }
    return reports


def latest_matching(folder: Path, pattern: str) -> Path:
    matches = sorted(folder.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True) if folder.exists() else []
    return matches[0] if matches else Path("")


def load_report(path: Path) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    payload = safe_load_json(path, {})
    if not isinstance(payload, dict):
        return {}
    payload["_path"] = str(path)
    return payload


def summarize_signals(signals: list[dict[str, Any]]) -> dict[str, Any]:
    def names_with(tag: str) -> list[str]:
        return [signal["name"] for signal in signals if tag in signal.get("classification", [])]

    active = [signal["name"] for signal in signals if signal.get("active")]
    recommendations = {signal["name"]: signal.get("recommendation") for signal in signals}
    return {
        "signal_count": len(signals),
        "active_influences": active,
        "no_op_influences": names_with("no-op"),
        "reporting_only_systems": names_with("reporting-only"),
        "stale_memories": [signal["name"] for signal in signals if signal.get("memory", {}).get("stale")],
        "noisy_memories": names_with("noisy"),
        "unsafe_to_influence_memories": names_with("unsafe-to-influence"),
        "recommendations": recommendations,
        "active_count": len(active),
        "no_op_count": len(names_with("no-op")),
        "reporting_only_count": len(names_with("reporting-only")),
    }


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"{timestamp}_learning_signal_audit.json"
    latest_json = REPORT_DIR / "latest_learning_signal_audit.json"
    markdown_path = REPORT_DIR / "latest_learning_signal_audit.md"
    atomic_write_json(json_path, report)
    atomic_write_json(latest_json, report)
    atomic_write_text(markdown_path, render_markdown(report, latest_json))
    return latest_json, markdown_path


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Learning Signal Audit",
        "",
        f"- Report version: {report.get('report_version')}",
        f"- Created: {report.get('created_at_utc')}",
        f"- JSON report: `{json_path}`",
        f"- Signals audited: {summary.get('signal_count', 0)}",
        f"- Active influences: {', '.join(summary.get('active_influences', []) or ['none'])}",
        f"- No-op influences: {', '.join(summary.get('no_op_influences', []) or ['none'])}",
        f"- Reporting-only systems: {', '.join(summary.get('reporting_only_systems', []) or ['none'])}",
        f"- Stale memories: {', '.join(summary.get('stale_memories', []) or ['none'])}",
        f"- Noisy memories: {', '.join(summary.get('noisy_memories', []) or ['none'])}",
        f"- Unsafe-to-influence memories: {', '.join(summary.get('unsafe_to_influence_memories', []) or ['none'])}",
        "",
        "## Signal Table",
        "",
        "| Signal | Classification | Influence | Recommendation |",
        "|---|---|---|---|",
    ]
    for signal in report.get("signals", []):
        lines.append(
            f"| {signal.get('name')} | {', '.join(signal.get('classification', []))} | "
            f"{signal.get('influence_level')} | {signal.get('recommendation')} |"
        )
    lines.extend(["", "## Evidence", ""])
    for signal in report.get("signals", []):
        lines.append(f"### {signal.get('name')}")
        for item in signal.get("evidence", [])[:8]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def stable_unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def main() -> None:
    args = parse_args()
    report = build_learning_signal_audit()
    if args.no_save:
        json_path = None
        markdown_path = None
    else:
        json_path, markdown_path = save_reports(report)
    summary = report["summary"]
    print("\nLearning Signal Audit Complete")
    print(f"Signals audited: {summary['signal_count']}")
    print(f"Active influences: {', '.join(summary['active_influences']) or 'none'}")
    print(f"No-op influences: {', '.join(summary['no_op_influences']) or 'none'}")
    print(f"Reporting-only systems: {', '.join(summary['reporting_only_systems']) or 'none'}")
    print(f"Stale memories: {', '.join(summary['stale_memories']) or 'none'}")
    print(f"Noisy memories: {', '.join(summary['noisy_memories']) or 'none'}")
    print(f"Unsafe-to-influence memories: {', '.join(summary['unsafe_to_influence_memories']) or 'none'}")
    if json_path and markdown_path:
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
