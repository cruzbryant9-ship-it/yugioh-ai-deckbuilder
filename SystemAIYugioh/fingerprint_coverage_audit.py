from __future__ import annotations

from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.source_fingerprint import SCORE_AFFECTING_SOURCE_FILES


COVERAGE_REPORT_JSON = PROJECT_ROOT / "SystemAIYugioh" / "data" / "training_runs" / "validation" / "fingerprint_coverage_audit.json"
COVERAGE_REPORT_MD = PROJECT_ROOT / "FINGERPRINT_COVERAGE_AUDIT.md"

FINGERPRINT_EXCLUSIONS: dict[str, str] = {
    "deck/__init__.py": "package marker only",
    "deck/archetype_specialization_detector.py": "promotion-readiness detector/report helper; does not affect scoring or deck construction",
    "deck/archetype_specialization_profiles.py": "non-activated semi-specialization profile data for review only",
    "deck/archetype_relationship_graph.py": "relationship discovery helper; not used by benchmark scoring path",
    "deck/curated_opponent_library.py": "static profile loading; profile data files are outside source fingerprint scope",
    "deck/decklist_parser.py": "input parsing utility for external decklists; not part of generated deck scoring",
    "deck/executed_dependency_telemetry.py": "executed comparison telemetry/report helper; does not affect scoring or deck construction",
    "deck/filler_signal_gates.py": "filler-memory governance remains inactive for benchmark scoring",
    "deck/generic_benchmark_memory.py": "memory persistence/reporting; not a scoring algorithm",
    "deck/generic_card_shift_explainer.py": "explanation/report generation only",
    "deck/generic_deck_diff_report.py": "report generation only",
    "deck/generic_diff_index.py": "generic diff memory/index maintenance, not direct scoring",
    "deck/generic_filler_impact.py": "filler impact report helper; filler-memory activation remains disabled",
    "deck/generic_filler_memory.py": "filler memory persistence; filler-memory activation remains disabled",
    "deck/generic_ratio_memory.py": "ratio memory persistence; not direct scoring",
    "deck/generic_ratio_recommender.py": "recommendation reporting, not active score formula",
    "deck/generic_targeted_retest.py": "offline retest orchestration, not scoring logic",
    "deck/generic_trend_diagnosis.py": "trend diagnosis/reporting only",
    "deck/interaction_core_registry.py": "report-only interaction-core ownership registry; does not activate builder behavior",
    "deck/interaction_preservation_trace.py": "trace/report helper for non-activated experimental adapter behavior; does not affect scoring or deck construction",
    "deck/rejection_classification.py": "report classification helper, not score calculation",
    "deck/semi_specialized_package_planner.py": "non-activated package planning scaffold; not used by deck construction",
    "deck/semi_specialized_builder_adapter.py": "explicit opt-in experimental Kashtira adapter; not used by default benchmark scoring or default deck construction",
    "deck/semi_specialized_adapter_tuning.py": "proposed-only adapter tuning definitions; not used by default benchmark scoring or default deck construction",
    "deck/semi_specialized_quota_replay.py": "non-activated quota replay/reporting harness; does not affect scoring or deck construction",
    "deck/semi_specialized_reconciled_comparison.py": "non-activated reconciled comparison/reporting harness; does not affect scoring or deck construction",
    "deck/semi_specialized_role_audit.py": "non-activated role audit/reporting harness; does not affect scoring or deck construction",
    "deck/semi_specialized_role_reconciliation.py": "non-activated role reconciliation/reporting harness; does not affect scoring or deck construction",
    "SystemAIYugioh/__init__.py": "package marker only",
    "SystemAIYugioh/card_database.py": "card data loader; data files are fingerprinted separately",
    "SystemAIYugioh/fingerprint_coverage_audit.py": "coverage validator/reporting helper, not scoring logic",
    "SystemAIYugioh/json_utils.py": "generic persistence utility; not score-affecting logic",
    "SystemAIYugioh/logging_utils.py": "logging helper only",
    "SystemAIYugioh/main.py": "entrypoint wrapper, not scoring logic",
    "SystemAIYugioh/memory_context.py": "provenance helper; does not calculate scoring/matchup values",
    "SystemAIYugioh/memory_quarantine.py": "memory safety/reporting helper, not scoring logic",
    "SystemAIYugioh/report_builder.py": "report assembly only",
    "SystemAIYugioh/runtime_context.py": "runtime cache/resource loader; source changes do not alter scoring formulas",
    "SystemAIYugioh/source_fingerprint.py": "fingerprint infrastructure itself; covered by validation instead of self-fingerprinting",
    "SystemAIYugioh/validation_core.py": "validator helper only",
    "SystemAIYugioh/validation_harness.py": "validator harness only",
}

SCORE_AFFECTING_TERMS = (
    "score",
    "scoring",
    "final_score",
    "simulate",
    "simulator",
    "builder",
    "optimize",
    "optimizer",
    "side",
    "package",
    "line",
    "resource",
    "opponent",
    "matchup",
    "engine",
    "combo",
    "repair",
    "filler",
    "tuner",
    "brick_rate",
    "playable_hand_rate",
    "valid_line",
)


def run_fingerprint_coverage_audit(write_reports: bool = True) -> dict[str, Any]:
    fingerprinted = set(SCORE_AFFECTING_SOURCE_FILES)
    candidates = discover_candidate_modules()
    excluded = {
        path: FINGERPRINT_EXCLUSIONS[path]
        for path in candidates
        if path in FINGERPRINT_EXCLUSIONS and path not in fingerprinted
    }
    covered = sorted(path for path in candidates if path in fingerprinted)
    uncovered = sorted(path for path in candidates if path not in fingerprinted and path not in FINGERPRINT_EXCLUSIONS)
    stale_fingerprints = sorted(path for path in fingerprinted if not (PROJECT_ROOT / path).exists())
    report = {
        "report_type": "fingerprint_coverage_audit",
        "candidate_count": len(candidates),
        "fingerprinted_count": len(covered),
        "excluded_count": len(excluded),
        "uncovered": uncovered,
        "stale_fingerprints": stale_fingerprints,
        "fingerprinted": covered,
        "excluded": excluded,
        "passed": not uncovered and not stale_fingerprints,
    }
    if write_reports:
        write_coverage_reports(report)
    return report


def discover_candidate_modules() -> list[str]:
    paths = [
        *sorted((PROJECT_ROOT / "deck").glob("*.py")),
        *sorted((PROJECT_ROOT / "SystemAIYugioh").glob("*.py")),
    ]
    candidates: list[str] = []
    for path in paths:
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative in SCORE_AFFECTING_SOURCE_FILES or relative in FINGERPRINT_EXCLUSIONS:
            candidates.append(relative)
            continue
        if looks_score_affecting(path):
            candidates.append(relative)
    return sorted(dict.fromkeys(candidates))


def looks_score_affecting(path: Path) -> bool:
    stem = path.stem.casefold()
    try:
        text = path.read_text(encoding="utf-8").casefold()
    except UnicodeDecodeError:
        text = ""
    return any(term in stem or term in text for term in SCORE_AFFECTING_TERMS)


def write_coverage_reports(report: dict[str, Any]) -> None:
    atomic_write_json(COVERAGE_REPORT_JSON, report)
    lines = [
        "# Fingerprint Coverage Audit",
        "",
        f"- Passed: {report['passed']}",
        f"- Candidate modules: {report['candidate_count']}",
        f"- Fingerprinted: {report['fingerprinted_count']}",
        f"- Explicitly excluded: {report['excluded_count']}",
        f"- Uncovered: {len(report['uncovered'])}",
        "",
        "## Uncovered Modules",
        "",
    ]
    if report["uncovered"]:
        lines.extend(f"- `{path}`" for path in report["uncovered"])
    else:
        lines.append("- None")
    lines.extend(["", "## Exclusions", ""])
    for path, reason in sorted(report["excluded"].items()):
        lines.append(f"- `{path}`: {reason}")
    lines.extend(["", "## Fingerprinted Modules", ""])
    lines.extend(f"- `{path}`" for path in report["fingerprinted"])
    atomic_write_text(COVERAGE_REPORT_MD, "\n".join(lines) + "\n")


if __name__ == "__main__":
    result = run_fingerprint_coverage_audit()
    print(f"Fingerprint coverage audit passed: {result['passed']}")
    print(f"Uncovered modules: {len(result['uncovered'])}")
    if not result["passed"]:
        raise SystemExit(1)
