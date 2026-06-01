from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from deck.generic_package_replay import build_package_replay_report
from deck.generic_ratio_recommender import recommend_ratio_adjustments
from deck.generic_targeted_retest import run_targeted_retest
from generic_archetype_benchmark import run_benchmark, save_reports
from SystemAIYugioh.card_database import CardDatabase

ROOT = Path(__file__).resolve().parent


def main() -> None:
    cards = CardDatabase().load_cards()
    checks = [
        ("replay report includes before/after counts", validate_before_after_counts),
        ("added/removed cards show correctly", validate_added_removed_cards),
        ("markdown replay is generated", validate_markdown_replay),
        ("rejected recommendation includes replay", lambda: validate_rejected_recommendation_replay(cards)),
        ("benchmark markdown includes replay section", validate_benchmark_replay_section),
        ("--show-replay works", validate_show_replay_cli),
        ("Phase 6I validator still passes", validate_phase6i_still_passes),
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
    print_sample(cards)
    print("Phase 6J validation complete.")


def validate_before_after_counts() -> None:
    replay = sample_replay()
    if replay["before_main_count"] != 4 or replay["after_main_count"] != 4:
        raise AssertionError(replay)
    if "before_main_package_counts" not in replay or "after_main_package_counts" not in replay:
        raise AssertionError(replay)


def validate_added_removed_cards() -> None:
    replay = sample_replay()
    if "New Interruption" not in replay["cards_added"]:
        raise AssertionError(replay)
    if "Old Starter" not in replay["cards_removed"]:
        raise AssertionError(replay)


def validate_markdown_replay() -> None:
    replay = sample_replay()
    markdown = replay.get("markdown_section", "")
    if "Package Replay" not in markdown or "| Package | Before | After | Delta |" not in markdown or "| Card | Delta | Change |" not in markdown:
        raise AssertionError(markdown)


def validate_rejected_recommendation_replay(cards: list[dict[str, Any]]) -> None:
    recommendations = recommend_ratio_adjustments("Branded", "meta", {"severity": "medium", "suspected_causes": ["interruption_shortage"]}, base_ratio())
    report = run_targeted_retest("Branded", cards, "meta", recommendations, runs_per_recommendation=1)
    rejected = report.get("rejected_recommendations", [])
    if not rejected:
        raise AssertionError(report)
    replay = rejected[0].get("package_replay_report", {})
    if not replay.get("markdown_section") or "before_main_package_counts" not in replay:
        raise AssertionError(rejected[0])


def validate_benchmark_replay_section() -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=1)
    _json_path, markdown_path = save_reports(report)
    text = markdown_path.read_text(encoding="utf-8")
    for marker in ("## Before/After Package Replay", "### Accepted Replay Sections", "### Rejected Replay Sections", "### Compact Card-Delta Table"):
        if marker not in text:
            raise AssertionError(text[-3000:])
    summary = report.get("summary", {}).get("package_replay_summary", {})
    if "rejected_replay_count" not in summary:
        raise AssertionError(report.get("summary", {}))


def validate_show_replay_cli() -> None:
    output = run_command("generic_archetype_benchmark.py", "--archetypes", "Branded", "--mode", "meta", "--runs", "1", "--show-replay", timeout=900)
    if "Package Replay Preview" not in output:
        raise AssertionError(output[-2500:])


def validate_phase6i_still_passes() -> None:
    run_command("validate_phase6i.py", timeout=1800)


def validate_stabilization_still_passes() -> None:
    run_command("validate_stabilization_f.py", timeout=1800)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])


def sample_replay() -> dict[str, Any]:
    baseline = ["Old Starter", "Shared Extender", "Old Brick", "Old Brick"]
    candidate = ["Shared Extender", "Shared Extender", "Old Brick", "New Interruption"]
    role_map = {
        "Old Starter": "starter",
        "Shared Extender": "extender",
        "Old Brick": "garnet_brick",
        "New Interruption": "interruption",
    }
    return build_package_replay_report("Replay Probe", baseline, candidate, role_map, {}, -1.25)


def print_sample(cards: list[dict[str, Any]]) -> None:
    report = run_benchmark(["Branded", "Kashtira"], mode="meta", runs=1)
    summary = report.get("summary", {}).get("package_replay_summary", {})
    print("SAMPLE: replay summary:", summary)
    for result in report.get("results", []):
        for rejected in result.get("targeted_retest", {}).get("rejected_recommendations", [])[:1]:
            replay = rejected.get("package_replay_report", {})
            print(f"SAMPLE: {result['archetype']} replay explanation:", replay.get("short_explanation"))


def base_ratio() -> dict[str, int]:
    return {
        "starters_searchers": 11,
        "extenders": 6,
        "payoffs": 3,
        "recovery": 2,
        "interruptions": 8,
        "board_breakers": 2,
        "max_bricks": 4,
    }


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
