from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from SystemAIYugioh.validation_harness import run_checks


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "OPPONENT_SIGNAL_AUDIT.md"

REQUIRED_SIGNALS = (
    "choke_stop_rate",
    "opponent_recovery_rate",
    "graph_stop_rate",
    "graph_pivot_rate",
    "probability_weighted_stop_rate",
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_starter_open_rate",
    "opponent_brick_rate",
)

INFLUENCE_PATHS = (
    "scoring",
    "tuning",
    "side_optimization",
    "matchup_matrix",
    "learning_memory",
    "regression_gates",
)

REPORT_SECTIONS = (
    "Signal Status Table",
    "Influence Map",
    "Classification Summary",
    "Dead Signal List",
    "Curated-Only Signal List",
    "Silent Fallback List",
    "Recommended Actions",
)


@dataclass(frozen=True)
class SignalAudit:
    signal: str
    status: str
    producer: str
    consumers: str
    persistence: str
    reports: str
    influences: dict[str, str]
    notes: str


SIGNAL_AUDITS = {
    "choke_stop_rate": SignalAudit(
        signal="choke_stop_rate",
        status="active",
        producer="deck/choke_simulator.py: simulate_choke_points() average_stop_rate; exported by deck/side_deck_planner.py and deck/side_plan_optimizer.py",
        consumers="curated opponent memory, regression gates, matchup/post-side/training summaries",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports, curated_opponent_memory.json histories",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "indirect",
            "matchup_matrix": "yes",
            "learning_memory": "yes-curated",
            "regression_gates": "yes",
        },
        notes="Directly stored by curated opponent memory; side optimization uses the choke report context rather than this scalar alone.",
    ),
    "opponent_recovery_rate": SignalAudit(
        signal="opponent_recovery_rate",
        status="active",
        producer="deck/choke_simulator.py: simulate_choke_points() average_recovery_rate; exported by side-deck reporting layers",
        consumers="curated opponent memory, regression gates, matchup/post-side/training summaries",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports, curated_opponent_memory.json histories",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "telemetry",
            "matchup_matrix": "yes",
            "learning_memory": "yes-curated",
            "regression_gates": "yes",
        },
        notes="Curated memory keeps a history, but no general learned-card or engine-memory path consumes it.",
    ),
    "graph_stop_rate": SignalAudit(
        signal="graph_stop_rate",
        status="active-telemetry-gated",
        producer="deck/opponent_graph_simulator.py: simulate_opponent_graph() aggregates route stop scores",
        consumers="regression gates, matchup/post-side/training summaries; graph-derived best interruption nodes feed side planning",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "indirect",
            "matchup_matrix": "yes",
            "learning_memory": "no",
            "regression_gates": "yes",
        },
        notes="The numeric rate is gated and reported; side optimization is affected by graph interruption recommendations, not by the scalar directly.",
    ),
    "graph_pivot_rate": SignalAudit(
        signal="graph_pivot_rate",
        status="active-telemetry-gated",
        producer="deck/opponent_graph_simulator.py: simulate_opponent_graph() aggregates route pivot scores",
        consumers="regression gates, matchup/post-side/training summaries",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "telemetry",
            "matchup_matrix": "yes",
            "learning_memory": "no",
            "regression_gates": "yes",
        },
        notes="No deck construction, gameplay score, or memory influence was found.",
    ),
    "probability_weighted_stop_rate": SignalAudit(
        signal="probability_weighted_stop_rate",
        status="report-only-bypassed",
        producer="deck/opponent_graph_simulator.py: probability_weighted_metrics() multiplies graph_stop_rate by likely-line access",
        consumers="opponent analysis, matchup matrix, post-side reporting; metric registry names it",
        persistence="matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation",
        reports="matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "no",
            "matchup_matrix": "report-only",
            "learning_memory": "no",
            "regression_gates": "no",
        },
        notes="Produced, stored, and reported in several paths, but no active consumer was found.",
    ),
    "opponent_resource_valid_rate": SignalAudit(
        signal="opponent_resource_valid_rate",
        status="active-telemetry-gated",
        producer="deck/opponent_graph_simulator.py: simulate_opponent_graph() validates route resource requirements",
        consumers="regression gates, matchup/post-side/training summaries",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "telemetry",
            "matchup_matrix": "yes",
            "learning_memory": "no",
            "regression_gates": "yes",
        },
        notes="Gated as a safety signal, but does not alter construction or memory influence.",
    ),
    "opponent_resource_failure_rate": SignalAudit(
        signal="opponent_resource_failure_rate",
        status="active",
        producer="deck/opponent_graph_simulator.py: simulate_opponent_graph() validates route resource failures",
        consumers="deck/side_deck_planner.py choke_candidate_adjustment(), regression gates, matchup/post-side/training summaries",
        persistence="training/evaluation run JSON, matchup matrix reports, post-side reports",
        reports="train_agent.py, evaluate_learning.py, matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "yes",
            "matchup_matrix": "yes",
            "learning_memory": "no",
            "regression_gates": "yes",
        },
        notes="The only required scalar found to directly affect side candidate adjustment, via resource-aware interruption tagging.",
    ),
    "opponent_starter_open_rate": SignalAudit(
        signal="opponent_starter_open_rate",
        status="report-only-bypassed",
        producer="deck/opponent_probability_simulator.py: simulate_opponent_openings(); copied through opponent_graph_simulator.probability_weighted_metrics()",
        consumers="opponent analysis, matchup matrix, post-side reporting; metric registry names it",
        persistence="matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation",
        reports="matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "no",
            "matchup_matrix": "report-only",
            "learning_memory": "no",
            "regression_gates": "no",
        },
        notes="Produced by Monte Carlo opening estimates and reported, but no active decision consumer was found.",
    ),
    "opponent_brick_rate": SignalAudit(
        signal="opponent_brick_rate",
        status="report-only-bypassed",
        producer="deck/opponent_probability_simulator.py: simulate_opponent_openings(); copied through opponent_graph_simulator.probability_weighted_metrics()",
        consumers="opponent analysis, matchup matrix, post-side reporting; metric registry names it",
        persistence="matchup matrix reports and opponent/post-side reports; omitted from train/evaluate side-metric aggregation",
        reports="matchup_matrix.py, post_side_evaluator.py, analyze_opponent_deck.py",
        influences={
            "scoring": "no",
            "tuning": "no",
            "side_optimization": "no",
            "matchup_matrix": "report-only",
            "learning_memory": "no",
            "regression_gates": "no",
        },
        notes="Missing probability data can become indistinguishable from a true zero brick rate in current reporting paths.",
    ),
}

SILENT_FALLBACKS = (
    "deck/choke_simulator.py:269-290 empty graph report returns 0.0 for graph/resource/probability signals.",
    "deck/opponent_probability_simulator.py:72-78 empty probability report returns 0.0 for starter and brick rates.",
    "deck/opponent_graph_simulator.py:304-310 missing probability estimates use estimates.get(..., 0.0), then probability_weighted_stop_rate becomes graph_stop_rate * 0.0.",
    "deck/side_deck_planner.py:197 resource failure lookup uses choke_report.get('opponent_resource_failure_rate', 0).",
    "train_agent.py:117-135 side metric collection falls back to side_report.get(..., 0) for choke/graph/resource metrics.",
    "evaluate_learning.py:110-128 side metric collection falls back to side_report.get(..., 0) for choke/graph/resource metrics.",
    "analyze_opponent_deck.py:92-122 report assembly falls back from optimized report to side report, then 0, for all required opponent signals.",
    "matchup_matrix.py:199-225 matrix cell assembly falls back from post-side report to side report, then 0, for all required opponent signals.",
    "matchup_matrix.py:373-393 matrix summary averages use float(cell.get(..., 0) or 0), masking missing cells as zeros.",
    "post_side_evaluator.py:83-107 post-side averages use result.get(..., 0) for all required opponent signals.",
    "SystemAIYugioh/report_schema.py:46-47 schema helper defaults missing opponent_resource_valid_rate and probability_weighted_stop_rate to 0.",
    "SystemAIYugioh/regression_gates.py:601-605 _number() converts missing or malformed values to 0.0 before gate comparisons and snapshots.",
)


def main() -> None:
    checks = [
        ("audit runs successfully", validate_audit_runs),
        ("all required opponent signals are discovered", validate_signal_discovery),
        ("all influence paths are classified", validate_influence_paths),
        ("report is generated", validate_report_generated),
    ]
    result = run_checks(
        "validate_stabilization_k",
        checks,
        json_path=Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_stabilization_k.json",
    )
    if not result.passed:
        raise SystemExit(1)
    print("Stabilization K validation complete.")


def validate_audit_runs() -> None:
    report = build_audit_report()
    if "Signal Status Table" not in report:
        raise AssertionError("audit report missing signal table")


def validate_signal_discovery() -> None:
    occurrences = discover_signal_occurrences()
    missing = [signal for signal in REQUIRED_SIGNALS if not occurrences.get(signal)]
    if missing:
        raise AssertionError(missing)


def validate_influence_paths() -> None:
    for signal in REQUIRED_SIGNALS:
        audit = SIGNAL_AUDITS.get(signal)
        if not audit:
            raise AssertionError(f"missing audit entry for {signal}")
        missing_paths = [path for path in INFLUENCE_PATHS if path not in audit.influences]
        if missing_paths:
            raise AssertionError(f"{signal}: {missing_paths}")
        if not audit.status or not audit.producer or not audit.consumers:
            raise AssertionError(f"incomplete audit entry for {signal}")


def validate_report_generated() -> None:
    report = build_audit_report()
    REPORT_PATH.write_text(report, encoding="utf-8")
    text = REPORT_PATH.read_text(encoding="utf-8")
    for section in REPORT_SECTIONS:
        if section not in text:
            raise AssertionError(f"missing section {section}")
    for signal in REQUIRED_SIGNALS:
        if signal not in text:
            raise AssertionError(f"missing signal {signal}")


def build_audit_report() -> str:
    occurrences = discover_signal_occurrences()
    lines = [
        "# Stabilization K: Opponent Intelligence Integration Audit",
        "",
        "Audit-only review. This pass does not change gameplay scoring, deck construction, authored Blue-Eyes behavior, memory influence, reports outside this audit output, or regression gates.",
        "",
        "## Signal Status Table",
        "",
        "| Signal | Status | Producer | Consumers | Persistence | Report Locations | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for signal in REQUIRED_SIGNALS:
        audit = SIGNAL_AUDITS[signal]
        lines.append(
            "| {signal} | {status} | {producer} | {consumers} | {persistence} | {reports} | {notes} |".format(
                signal=audit.signal,
                status=audit.status,
                producer=audit.producer,
                consumers=audit.consumers,
                persistence=audit.persistence,
                reports=audit.reports,
                notes=audit.notes,
            )
        )

    lines.extend(
        [
            "",
            "## Influence Map",
            "",
            "| Signal | Scoring | Tuning | Side Optimization | Matchup Matrix | Learning Memory | Regression Gates |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for signal in REQUIRED_SIGNALS:
        audit = SIGNAL_AUDITS[signal]
        lines.append(
            "| {signal} | {scoring} | {tuning} | {side_optimization} | {matchup_matrix} | {learning_memory} | {regression_gates} |".format(
                signal=signal,
                **audit.influences,
            )
        )

    lines.extend(
        [
            "",
            "## Classification Summary",
            "",
            "- Active: choke_stop_rate, opponent_recovery_rate, opponent_resource_failure_rate.",
            "- Active telemetry/gated: graph_stop_rate, graph_pivot_rate, opponent_resource_valid_rate.",
            "- Report only: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.",
            "- Bypassed in train/evaluate aggregation: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.",
            "- Curated-only memory persistence: choke_stop_rate, opponent_recovery_rate.",
            "- Dead: none among the required signals.",
            "",
            "## Discovery Counts",
            "",
            "| Signal | Source Occurrences | Representative Files |",
            "| --- | ---: | --- |",
        ]
    )
    for signal in REQUIRED_SIGNALS:
        files = sorted({item.split(":", 1)[0] for item in occurrences.get(signal, [])})
        lines.append(f"| {signal} | {len(occurrences.get(signal, []))} | {', '.join(files[:8])} |")

    lines.extend(
        [
            "",
            "## Dead Signal List",
            "",
            "- No required signal is completely dead: every required signal is produced and appears in at least one report or validation path.",
            "- Produced, stored, reported, but not consumed by active decision logic: probability_weighted_stop_rate, opponent_starter_open_rate, opponent_brick_rate.",
            "- Gated telemetry without direct scoring/deck/memory influence: graph_pivot_rate and opponent_resource_valid_rate.",
            "",
            "## Curated-Only Signal List",
            "",
            "- choke_stop_rate: stored in curated_opponent_memory.json histories and side-card choke effectiveness.",
            "- opponent_recovery_rate: stored in curated_opponent_memory.json histories.",
            "- No graph, probability, starter, brick, or resource signal is persisted into curated opponent memory today.",
            "",
            "## Produced/Stored/Reported But Never Consumed",
            "",
            "- probability_weighted_stop_rate: produced in deck/opponent_graph_simulator.py, exported by side planners, reported by matchup/post-side/opponent analysis paths, and registered in SystemAIYugioh/metric_registry.py; no scoring, tuning, side optimization, memory, or regression-gate consumer was found.",
            "- opponent_starter_open_rate: produced in deck/opponent_probability_simulator.py and reported in opponent analysis, matchup matrix, and post-side summaries; no active decision consumer was found.",
            "- opponent_brick_rate: produced in deck/opponent_probability_simulator.py and reported in opponent analysis, matchup matrix, and post-side summaries; no active decision consumer was found.",
            "",
            "## Silent Fallback List",
            "",
        ]
    )
    lines.extend(f"- {fallback}" for fallback in SILENT_FALLBACKS)
    lines.extend(
        [
            "",
            "## Recommended Actions",
            "",
            "1. Decide whether probability_weighted_stop_rate, opponent_starter_open_rate, and opponent_brick_rate should remain report-only telemetry or become regression gates.",
            "2. Add a future explicit missing-data sentinel for opponent probability and graph reports so missing data is distinguishable from a true 0.0 measurement.",
            "3. Consider extending train_agent.py and evaluate_learning.py side-metric aggregation to include probability_weighted_stop_rate, opponent_starter_open_rate, and opponent_brick_rate if these are intended to be monitored over training runs.",
            "4. Document that curated opponent memory currently stores only choke_stop_rate and opponent_recovery_rate among the required signals, or deliberately extend curated memory in a later non-audit pass.",
            "5. If opponent_resource_failure_rate remains a side optimization input, add future tests that assert missing resource modeling does not silently trigger a zero-resource-failure interpretation.",
            "",
            "## Validation",
            "",
            "Run:",
            "",
            "```powershell",
            "python validate_stabilization_k.py",
            "```",
            "",
            "The validator scans source files, verifies all required opponent signals are discoverable, verifies every influence path is classified, and regenerates this audit report.",
        ]
    )
    return "\n".join(lines) + "\n"


def discover_signal_occurrences() -> dict[str, list[str]]:
    occurrences = {signal: [] for signal in REQUIRED_SIGNALS}
    for path in iter_source_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(lines, start=1):
            for signal in REQUIRED_SIGNALS:
                if signal in line:
                    occurrences[signal].append(f"{relative}:{line_number}")
    return occurrences


def iter_source_files():
    excluded_parts = {"venv", "__pycache__", ".git", ".idea"}
    excluded_data = ("SystemAIYugioh", "data")
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".md"}:
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & excluded_parts:
            continue
        relative_parts = path.relative_to(ROOT).parts
        if len(relative_parts) >= 2 and relative_parts[:2] == excluded_data:
            continue
        yield path


if __name__ == "__main__":
    main()
