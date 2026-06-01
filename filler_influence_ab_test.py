from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from filler_signal_gate_report import build_filler_signal_gate_report, save_gate_report
from generic_archetype_benchmark import run_benchmark
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.memory_context import normalize_provenance


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "filler_influence_ab"
NO_EFFECT_DELTA_BAND = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated control vs filler-memory-influence A/B benchmarks.")
    parser.add_argument("--archetypes", nargs="+", required=True)
    parser.add_argument("--mode", default="meta", choices=("meta", "innovation"))
    parser.add_argument("--runs", type=int, default=5, help="Benchmark tuning runs per archetype per trial.")
    parser.add_argument("--trials", type=int, default=5, help="Number of repeated A/B trials.")
    return parser.parse_args()


def run_ab_test(
    archetypes: list[str],
    mode: str = "meta",
    runs: int = 5,
    trials: int = 5,
    provenance: dict[str, Any] | None = None,
    refresh_gate_report: bool = True,
) -> dict[str, Any]:
    if runs < 1:
        raise ValueError("runs must be 1 or greater")
    if trials < 1:
        raise ValueError("trials must be 1 or greater")
    if refresh_gate_report:
        save_gate_report(build_filler_signal_gate_report())

    provenance = normalize_provenance(provenance, source="filler_influence_ab_test", smoke=runs <= 1)
    trial_rows = []
    for trial_index in range(1, trials + 1):
        trial_provenance = normalize_provenance(provenance, source="filler_influence_ab_test", smoke=runs <= 1)
        control = run_benchmark(
            archetypes,
            mode=mode,
            runs=runs,
            show_replay=False,
            provenance=trial_provenance,
            enable_filler_memory_influence=False,
        )
        experiment = run_benchmark(
            archetypes,
            mode=mode,
            runs=runs,
            show_replay=False,
            provenance=trial_provenance,
            enable_filler_memory_influence=True,
        )
        trial_rows.append(build_trial_result(trial_index, control, experiment))

    summary = summarize_trials(trial_rows)
    return {
        "report_type": "filler_influence_ab_test",
        "report_version": "phase6u-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "archetypes": archetypes,
            "mode": mode,
            "runs": runs,
            "trials": trials,
            "control_filler_memory_influence": False,
            "experiment_filler_memory_influence": True,
        },
        "provenance": provenance,
        "summary": summary,
        "trials": trial_rows,
    }


def build_trial_result(trial_index: int, control: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    control_summary = control.get("summary", {}) if isinstance(control.get("summary"), dict) else {}
    experiment_summary = experiment.get("summary", {}) if isinstance(experiment.get("summary"), dict) else {}
    control_score = average_result_field(control, "tuned_score")
    experiment_score = average_result_field(experiment, "tuned_score")
    control_improvement = as_float(control_summary.get("average_improvement"))
    experiment_improvement = as_float(experiment_summary.get("average_improvement"))
    delta = round(experiment_improvement - control_improvement, 4)
    experiment_influence = experiment_summary.get("filler_memory_influence", {}) if isinstance(experiment_summary.get("filler_memory_influence"), dict) else {}
    ordering_changes = int(experiment_influence.get("influence_changed_order_count", 0) or 0)
    influence_selection_changes = count_selection_changes(experiment_influence)
    filler_distribution_changed = normalize_counter(control_summary.get("selected_filler_counts", {})) != normalize_counter(
        experiment_summary.get("selected_filler_counts", {})
    )
    legality_failures = int(control_summary.get("decks_still_rejected", 0) or 0) + int(experiment_summary.get("decks_still_rejected", 0) or 0)
    classification = classify_ab_result(delta, ordering_changes, influence_selection_changes)
    return {
        "trial": trial_index,
        "control": compact_benchmark_report(control),
        "experiment": compact_benchmark_report(experiment),
        "control_average_score": control_score,
        "experiment_average_score": experiment_score,
        "control_average_improvement": round(control_improvement, 4),
        "experiment_average_improvement": round(experiment_improvement, 4),
        "experiment_minus_control_delta": delta,
        "repair_success_delta": round(as_float(experiment_summary.get("repair_success_rate")) - as_float(control_summary.get("repair_success_rate")), 4),
        "control_rejected_decks": int(control_summary.get("decks_still_rejected", 0) or 0),
        "experiment_rejected_decks": int(experiment_summary.get("decks_still_rejected", 0) or 0),
        "legality_failures": legality_failures,
        "ordering_change_count": ordering_changes,
        "selection_change_count": influence_selection_changes,
        "benchmark_filler_distribution_changed": filler_distribution_changed,
        "filler_memory_bias_applied": experiment_influence.get("filler_memory_bias_applied", {}),
        "selected_filler_before_after": experiment_influence.get("selection_before_after", []),
        "classification": classification,
    }


def compact_benchmark_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    return {
        "filler_memory_influence_enabled": bool(summary.get("filler_memory_influence_enabled")),
        "average_normal_score": average_result_field(report, "normal_score"),
        "average_tuned_score": average_result_field(report, "tuned_score"),
        "average_improvement": summary.get("average_improvement", 0),
        "repair_success_rate": summary.get("repair_success_rate", 0),
        "decks_still_rejected": summary.get("decks_still_rejected", 0),
        "selected_filler_counts": normalize_counter(summary.get("selected_filler_counts", {})),
        "filler_memory_influence": summary.get("filler_memory_influence", {}),
        "archetype_results": [
            {
                "archetype": result.get("archetype"),
                "improvement": result.get("improvement", 0),
                "tuned_legal": bool(result.get("tuned_legal")),
                "selected_filler_counts": normalize_counter(result.get("selected_filler_counts", {})),
            }
            for result in report.get("results", [])
        ],
    }


def summarize_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    if not trials:
        return empty_summary()
    deltas = [as_float(row.get("experiment_minus_control_delta")) for row in trials]
    control_scores = [as_float(row.get("control_average_score")) for row in trials]
    experiment_scores = [as_float(row.get("experiment_average_score")) for row in trials]
    control_values = [as_float(row.get("control_average_improvement")) for row in trials]
    experiment_values = [as_float(row.get("experiment_average_improvement")) for row in trials]
    classification_counts = Counter(str(row.get("classification", "no_effect")) for row in trials)
    ordering_changes = sum(int(row.get("ordering_change_count", 0) or 0) for row in trials)
    selection_changes = sum(int(row.get("selection_change_count", 0) or 0) for row in trials)
    legality_failures = sum(int(row.get("legality_failures", 0) or 0) for row in trials)
    bias_counter: Counter[str] = Counter()
    for row in trials:
        for name, value in (row.get("filler_memory_bias_applied", {}) or {}).items():
            bias_counter[str(name)] += as_float(value)
    return {
        "total_trials": len(trials),
        "average_control_score": round(mean(control_scores), 4),
        "average_control_improvement": round(mean(control_values), 4),
        "average_experiment_score": round(mean(experiment_scores), 4),
        "average_experiment_improvement": round(mean(experiment_values), 4),
        "average_experiment_minus_control_delta": round(mean(deltas), 4),
        "positive_trial_count": sum(1 for value in deltas if value > NO_EFFECT_DELTA_BAND),
        "negative_trial_count": sum(1 for value in deltas if value < -NO_EFFECT_DELTA_BAND),
        "neutral_trial_count": sum(1 for value in deltas if -NO_EFFECT_DELTA_BAND <= value <= NO_EFFECT_DELTA_BAND),
        "ordering_change_count": ordering_changes,
        "selection_change_count": selection_changes,
        "benchmark_filler_distribution_change_count": sum(1 for row in trials if row.get("benchmark_filler_distribution_changed")),
        "legality_failures": legality_failures,
        "control_rejected_decks": sum(int(row.get("control_rejected_decks", 0) or 0) for row in trials),
        "experiment_rejected_decks": sum(int(row.get("experiment_rejected_decks", 0) or 0) for row in trials),
        "classification_counts": dict(classification_counts),
        "overall_classification": classify_overall(classification_counts, ordering_changes, selection_changes),
        "bias_applied_totals": {name: round(value, 6) for name, value in sorted(bias_counter.items())},
        "recommendation": recommendation_text(classification_counts, ordering_changes, selection_changes, legality_failures),
    }


def empty_summary() -> dict[str, Any]:
    return {
        "total_trials": 0,
        "average_control_improvement": 0,
        "average_experiment_improvement": 0,
        "average_experiment_minus_control_delta": 0,
        "positive_trial_count": 0,
        "negative_trial_count": 0,
        "neutral_trial_count": 0,
        "ordering_change_count": 0,
        "selection_change_count": 0,
        "legality_failures": 0,
        "classification_counts": {},
        "overall_classification": "no_effect",
        "recommendation": "Keep filler-memory influence experimental until selection-changing evidence exists.",
    }


def classify_ab_result(delta: float, ordering_changes: int, selection_changes: int) -> str:
    if int(ordering_changes or 0) <= 0 and int(selection_changes or 0) <= 0:
        return "no_effect"
    if delta > NO_EFFECT_DELTA_BAND:
        return "helped"
    if delta < -NO_EFFECT_DELTA_BAND:
        return "hurt"
    return "no_effect"


def classify_overall(classification_counts: Counter[str], ordering_changes: int, selection_changes: int) -> str:
    if ordering_changes <= 0 and selection_changes <= 0:
        return "no_effect"
    helped = int(classification_counts.get("helped", 0) or 0)
    hurt = int(classification_counts.get("hurt", 0) or 0)
    if helped > hurt:
        return "helped"
    if hurt > helped:
        return "hurt"
    return "no_effect"


def recommendation_text(classification_counts: Counter[str], ordering_changes: int, selection_changes: int, legality_failures: int) -> str:
    if legality_failures:
        return "Keep filler-memory influence experimental; legality failures appeared during A/B testing."
    if ordering_changes <= 0 and selection_changes <= 0:
        return "Keep filler-memory influence experimental; current evidence is no-op because filler ordering/selection did not change."
    if int(classification_counts.get("hurt", 0) or 0) > int(classification_counts.get("helped", 0) or 0):
        return "Keep filler-memory influence experimental; selection-changing evidence is currently negative."
    return "Keep filler-memory influence experimental and continue collecting repeated A/B evidence before default activation."


def count_selection_changes(influence_summary: dict[str, Any]) -> int:
    return sum(
        1
        for row in influence_summary.get("selection_before_after", []) or []
        if isinstance(row, dict) and row.get("before") and row.get("after") and row.get("before") != row.get("after")
    )


def average_result_field(report: dict[str, Any], field: str) -> float:
    values = [as_float(result.get(field)) for result in report.get("results", []) if isinstance(result, dict)]
    return round(mean(values), 4) if values else 0.0


def normalize_counter(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(amount or 0) for key, amount in sorted(value.items()) if int(amount or 0)}


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"{timestamp}_filler_influence_ab_report.json"
    latest_json = REPORT_DIR / "latest_filler_influence_ab_report.json"
    markdown_path = REPORT_DIR / "latest_filler_influence_ab_report.md"
    atomic_write_json(json_path, report)
    atomic_write_json(latest_json, report)
    atomic_write_text(markdown_path, render_markdown(report, latest_json))
    return latest_json, markdown_path


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Filler Influence A/B Test",
        "",
        f"- Mode: {report.get('config', {}).get('mode')}",
        f"- Archetypes: {', '.join(report.get('config', {}).get('archetypes', []))}",
        f"- Runs per benchmark: {report.get('config', {}).get('runs')}",
        f"- Trials: {summary.get('total_trials', 0)}",
        f"- JSON report: `{json_path}`",
        f"- Average control score: {summary.get('average_control_score', 0)}",
        f"- Average experiment score: {summary.get('average_experiment_score', 0)}",
        f"- Average control improvement: {summary.get('average_control_improvement', 0)}",
        f"- Average experiment improvement: {summary.get('average_experiment_improvement', 0)}",
        f"- Average experiment-control delta: {summary.get('average_experiment_minus_control_delta', 0)}",
        f"- Ordering-change count: {summary.get('ordering_change_count', 0)}",
        f"- Selection-change count: {summary.get('selection_change_count', 0)}",
        f"- Legality failures: {summary.get('legality_failures', 0)}",
        f"- Overall classification: {summary.get('overall_classification', 'no_effect')}",
        f"- Recommendation: {summary.get('recommendation')}",
        "",
        "## Trial Summary",
        "",
        "| Trial | Control Score | Experiment Score | Control Improvement | Experiment Improvement | Delta | Ordering Changes | Selection Changes | Classification |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("trials", []):
        lines.append(
            f"| {row.get('trial')} | {row.get('control_average_score', 0)} | {row.get('experiment_average_score', 0)} | "
            f"{row.get('control_average_improvement', 0)} | {row.get('experiment_average_improvement', 0)} | "
            f"{row.get('experiment_minus_control_delta', 0)} | "
            f"{row.get('ordering_change_count', 0)} | {row.get('selection_change_count', 0)} | {row.get('classification')} |"
        )
    lines.extend(
        [
            "",
            "## Bias Applied",
            "",
        ]
    )
    bias = summary.get("bias_applied_totals", {})
    if bias:
        for name, value in bias.items():
            lines.append(f"- {name}: {value}")
    else:
        lines.append("- None")
    lines.extend(["", "## Filler Choices", ""])
    for row in report.get("trials", []):
        control_fillers = row.get("control", {}).get("selected_filler_counts", {})
        experiment_fillers = row.get("experiment", {}).get("selected_filler_counts", {})
        lines.append(f"- Trial {row.get('trial')} control: {format_counts(control_fillers)}")
        lines.append(f"- Trial {row.get('trial')} experiment: {format_counts(experiment_fillers)}")
    return "\n".join(lines) + "\n"


def format_counts(counts: dict[str, int]) -> str:
    rows = Counter(counts).most_common(5)
    return ", ".join(f"{name} ({count})" for name, count in rows) if rows else "none"


def main() -> None:
    args = parse_args()
    report = run_ab_test(args.archetypes, mode=args.mode, runs=args.runs, trials=args.trials)
    json_path, markdown_path = save_reports(report)
    summary = report["summary"]
    print("\nFiller Influence A/B Test Complete")
    print(f"Trials: {summary['total_trials']}")
    print(f"Average control score: {summary['average_control_score']}")
    print(f"Average experiment score: {summary['average_experiment_score']}")
    print(f"Average control improvement: {summary['average_control_improvement']}")
    print(f"Average experiment improvement: {summary['average_experiment_improvement']}")
    print(f"Average experiment-control delta: {summary['average_experiment_minus_control_delta']}")
    print(f"Positive/negative/neutral trials: {summary['positive_trial_count']}/{summary['negative_trial_count']}/{summary['neutral_trial_count']}")
    print(f"Ordering-change count: {summary['ordering_change_count']}")
    print(f"Selection-change count: {summary['selection_change_count']}")
    print(f"Legality failures: {summary['legality_failures']}")
    print(f"Classification counts: {summary['classification_counts']}")
    print(f"Overall classification: {summary['overall_classification']}")
    print(f"Recommendation: {summary['recommendation']}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
