from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.builder import build_deck, get_last_build_report
from deck.generic_ratio_memory import load_generic_ratio_memory, record_bad_ratio_pattern
from generic_archetype_benchmark import BENCHMARK_DIR, run_benchmark, save_reports
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("benchmark runs on at least 2 archetypes", validate_benchmark_runs),
        ("report JSON and markdown are saved", validate_reports_saved),
        ("normal vs tuned comparison exists", validate_comparison_fields),
        ("ratio memory updates safely", validate_memory_update),
        ("bad ratio patterns are recorded", validate_bad_ratio_recording),
        ("Blue-Eyes authored path still works", lambda: validate_blue_eyes_authored(cards)),
        ("Phase 6C validator still passes", validate_phase6c_still_passes),
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
    print("Phase 6D validation complete.")


def validate_benchmark_runs() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    if report["summary"]["archetype_count"] < 2 or len(report["results"]) < 2:
        raise AssertionError(report["summary"])


def validate_reports_saved() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    json_path, markdown_path = save_reports(report)
    if not json_path.exists() or not markdown_path.exists():
        raise AssertionError((json_path, markdown_path))


def validate_comparison_fields() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    first = report["results"][0]
    for key in ("normal_score", "tuned_score", "improvement", "normal_package_counts", "tuned_package_counts", "skeleton_coverage"):
        if key not in first:
            raise AssertionError(first)


def validate_memory_update() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    actions = {result["memory_action"] for result in report["results"]}
    if not actions <= {"updated", "recorded_bad_pattern", "unchanged"}:
        raise AssertionError(actions)
    memory = load_generic_ratio_memory("Branded", "meta")
    if not isinstance(memory, dict):
        raise AssertionError(memory)


def validate_bad_ratio_recording() -> None:
    record_bad_ratio_pattern("Validation Archetype", "meta", {"starters_searchers": 1}, "validator_probe", -9.0)
    memory = load_generic_ratio_memory("Validation Archetype", "meta")
    if not memory.get("bad_ratio_patterns"):
        raise AssertionError(memory)


def validate_blue_eyes_authored(cards: list[dict]) -> None:
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    report = get_last_build_report()
    if not deck or report.get("builder_used") != "authored":
        raise AssertionError(report)


def validate_phase6c_still_passes() -> None:
    run_command("validate_phase6c.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def print_sample() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=2)
    print("SAMPLE: Average improvement:", report["summary"]["average_improvement"])
    print("SAMPLE: Best improved archetype:", report["summary"]["best_improved_archetype"])
    print("SAMPLE: Memory actions:", dict(report["summary"]["memory_updates"]))
    latest = BENCHMARK_DIR / "latest_generic_benchmark_report.md"
    print("SAMPLE: Latest benchmark markdown:", latest)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
