from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from SystemAIYugioh.json_utils import atomic_write_text
from SystemAIYugioh.metric_registry import GRAPH_METRICS, MATRIX_SUMMARY_METRICS, MONTE_CARLO_PROBABILITY_METRICS, RESOURCE_METRICS
from SystemAIYugioh.report_schema import normalize_report, validate_report
from deck.deck_utils import split_deck

ROOT = Path(__file__).resolve().parent
MATRIX_DIR = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "matchup_matrix"


def main() -> None:
    checks = [
        ("shared split_deck works", validate_split_deck),
        ("duplicate split_deck imports are gone", validate_no_cross_entry_imports),
        ("metric registry loads", validate_metric_registry),
        ("strict report validation catches missing required metric", validate_strict_report_validation),
        ("atomic markdown write works", validate_atomic_markdown_write),
        ("matchup_matrix smoke still runs", validate_matrix_smoke),
        ("matrix failure counts appear in reports", validate_matrix_failure_counts),
        ("validate_stabilization_a.py still passes", validate_stabilization_a),
        ("validate_phase5x.py still passes", validate_phase5x),
    ]
    failures = []
    for label, check in checks:
        try:
            check()
            print(f"PASS: {label}")
        except Exception as exc:
            failures.append(label)
            print(f"FAIL: {label}: {exc}")
    if failures:
        raise SystemExit(1)
    print("Stabilization Pass B validation complete.")


def validate_split_deck() -> None:
    deck = [{"name": "Blue-Eyes White Dragon", "type": "Normal Monster"}, {"name": "Blue-Eyes Spirit Dragon", "type": "Synchro Monster"}]
    main, extra = split_deck(deck)
    if len(main) != 1 or len(extra) != 1:
        raise AssertionError((main, extra))


def validate_no_cross_entry_imports() -> None:
    offenders = []
    for path in ROOT.glob("*.py"):
        if path.name.startswith("validate_"):
            continue
        text = path.read_text(encoding="utf-8")
        for needle in ("from train_agent import", "from post_side_evaluator import", "from compare_engines import"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    if offenders:
        raise AssertionError(offenders)


def validate_metric_registry() -> None:
    for group in (GRAPH_METRICS, RESOURCE_METRICS, MONTE_CARLO_PROBABILITY_METRICS, MATRIX_SUMMARY_METRICS):
        if not group:
            raise AssertionError("empty metric group")


def validate_strict_report_validation() -> None:
    try:
        validate_report("matchup_matrix", {"report_type": "matchup_matrix"}, strict=True)
    except ValueError:
        return
    raise AssertionError("strict validation did not fail")


def validate_atomic_markdown_write() -> None:
    path = MATRIX_DIR / "_atomic_markdown_check.md"
    atomic_write_text(path, "# ok\n")
    if path.read_text(encoding="utf-8") != "# ok\n":
        raise AssertionError(path)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=2200)
    if "Matchup Matrix Complete" not in output or "Failed cells:" not in output:
        raise AssertionError(output[-2500:])


def validate_matrix_failure_counts() -> None:
    payload = json.loads(latest_matrix_report().read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    required = {"failed_cell_count", "failed_run_count", "failure_rate"}
    missing = required - set(summary)
    if missing:
        raise AssertionError(summary)
    validate_report("matchup_matrix", payload, strict=True)


def validate_stabilization_a() -> None:
    output = run_command("validate_stabilization_a.py", timeout=5600)
    if "Stabilization Pass A validation complete." not in output:
        raise AssertionError(output[-2500:])


def validate_phase5x() -> None:
    output = run_command("validate_phase5x.py", timeout=3600)
    if "Phase 5X-lite validation complete." not in output:
        raise AssertionError(output[-2500:])


def latest_matrix_report() -> Path:
    reports = sorted(MATRIX_DIR.glob("*_blue-eyes_meta_matchup_matrix.json"), key=lambda path: path.stat().st_mtime)
    if not reports:
        raise AssertionError("no matrix reports found")
    return reports[-1]


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
