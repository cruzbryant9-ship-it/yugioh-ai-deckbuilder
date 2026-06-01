from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.generic_deck_diff_report import build_rich_deck_diff_report
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.memory_context import provenance_metadata, temporary_isolated_memory_root

ROOT = Path(__file__).resolve().parent
DIFF_DIR = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "generic_benchmarks" / "deck_diffs"


def main() -> None:
    with temporary_isolated_memory_root("phase6k_memory_"):
        run_checks()


def run_checks() -> None:
    checks = [
        ("deck diff markdown is created", validate_deck_diff_markdown_created),
        ("report includes baseline/tuned sections", validate_baseline_tuned_sections),
        ("report includes package comparison", validate_package_comparison),
        ("report includes card deltas", validate_card_deltas),
        ("report includes repair actions", validate_repair_actions),
        ("benchmark links to diff artifact", validate_benchmark_links),
        ("Phase 6J validator still passes", validate_phase6j_still_passes),
        ("stabilization validator still passes", validate_stabilization_still_passes),
        ("matchup matrix smoke still passes", validate_matrix_smoke),
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
    print_sample()
    print("Phase 6K validation complete.")


def validate_deck_diff_markdown_created() -> None:
    report = run_benchmark(["Branded"], mode="meta", runs=1, provenance=validator_provenance())
    save_reports(report)
    markdown = DIFF_DIR / "latest_branded_deck_diff.md"
    html = DIFF_DIR / "latest_branded_deck_diff.html"
    if not markdown.exists() or not html.exists():
        raise AssertionError((markdown, html))


def validate_baseline_tuned_sections() -> None:
    text = latest_branded_text()
    if "## Baseline Deck" not in text or "## Tuned Deck" not in text:
        raise AssertionError(text[:1000])


def validate_package_comparison() -> None:
    text = latest_branded_text()
    if "## Package Count Comparison" not in text or "| Package | Baseline | Tuned | Delta |" not in text:
        raise AssertionError(text[:1500])


def validate_card_deltas() -> None:
    text = latest_branded_text()
    if "## Cards Added" not in text or "## Cards Removed" not in text or "## Copy Changes" not in text:
        raise AssertionError(text[:2000])


def validate_repair_actions() -> None:
    report = synthetic_diff_report()
    markdown = report["markdown"]
    if "## Repair Actions" not in markdown or "filled missing main slot" not in markdown:
        raise AssertionError(markdown)


def validate_benchmark_links() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=1, provenance=validator_provenance())
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    if "## Deck Diff Artifacts" not in text or "latest_branded_deck_diff.md" not in text or "latest_kashtira_deck_diff.md" not in text:
        raise AssertionError(text[:2000])
    for result in report["results"]:
        artifacts = result.get("deck_diff_artifacts", {})
        if not artifacts.get("markdown") or not artifacts.get("html"):
            raise AssertionError(result)


def validate_phase6j_still_passes() -> None:
    run_command("validate_phase6j.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def latest_branded_text() -> str:
    path = DIFF_DIR / "latest_branded_deck_diff.md"
    if not path.exists():
        validate_deck_diff_markdown_created()
    return path.read_text(encoding="utf-8")


def synthetic_diff_report() -> dict:
    baseline = {
        "score": 100,
        "confidence": 0.5,
        "package_counts": {"starters_searchers": 10, "extenders": 5},
        "deck_sections": {"main": ["Starter A", "Extender A"], "extra": ["Extra A"]},
        "deck_names": ["Starter A", "Extender A", "Extra A"],
        "repair_actions": ["filled missing main slot with starter: Starter A"],
    }
    tuned = {
        "score": 103,
        "confidence": 0.55,
        "package_counts": {"starters_searchers": 11, "extenders": 4},
        "deck_sections": {"main": ["Starter A", "Starter B"], "extra": ["Extra A"]},
        "deck_names": ["Starter A", "Starter B", "Extra A"],
        "repair_actions": ["added Extra Deck repair card: Extra A"],
    }
    return build_rich_deck_diff_report("Synthetic", baseline, tuned, {"targeted_retest_used": False})


def print_sample() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=1, provenance=validator_provenance())
    save_reports(report)
    for result in report["results"]:
        print(f"SAMPLE: {result['archetype']} diff artifacts:", result.get("deck_diff_artifacts"))
        print(f"SAMPLE: {result['archetype']} diff summary:", result.get("deck_diff_summary"))


def validator_provenance() -> dict:
    return provenance_metadata(source="validator", validator_generated=True, smoke=True, legal=True)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
