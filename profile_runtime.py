from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from config.settings import MATRIX_FULL_RUNS_PER_CELL, MATRIX_SMOKE_RUNS_PER_CELL
from SystemAIYugioh.json_utils import safe_load_json

ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile key SystemAIYugioh commands.")
    parser.add_argument("--smoke", action="store_true", help="Run short profiling commands.")
    parser.add_argument("--full", action="store_true", help="Run slower full profiling commands.")
    parser.add_argument("--quick", action="store_true", help="Run only the fastest import-level profiling checks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    smoke = not args.full
    commands = [["validate_stabilization_a.py", "--imports-only"]] if args.quick else profile_commands(smoke)
    results = []
    for command in commands:
        started = time.perf_counter()
        result = subprocess.run([sys.executable, *command], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        duration = round(time.perf_counter() - started, 2)
        results.append({"command": " ".join(command), "duration": duration, "success": result.returncode == 0})
    print("\nRuntime Profile")
    for item in results:
        status = "ok" if item["success"] else "failed"
        print(f"{item['duration']:>7.2f}s  {status:<6} {item['command']}")
    slowest = sorted(results, key=lambda item: item["duration"], reverse=True)[:3]
    print("\nSlowest scripts:")
    for item in slowest:
        print(f"- {item['command']} ({item['duration']}s)")
    print("\nRecommended optimization targets:")
    for item in slowest:
        print(f"- {optimization_hint(item['command'])}")
    if not all(item["success"] for item in results):
        raise SystemExit(1)
    print_cache_summary()


def profile_commands(smoke: bool) -> list[list[str]]:
    matrix_runs = MATRIX_SMOKE_RUNS_PER_CELL if smoke else MATRIX_FULL_RUNS_PER_CELL
    return [
        ["validate_phase5x.py"],
        ["analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second"],
        ["post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1" if smoke else "3"],
        ["matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", str(matrix_runs), "--use-curated-opponents", "--smoke" if smoke else "--full"],
    ]


def optimization_hint(command: str) -> str:
    if "matchup_matrix" in command:
        return "Cache repeated deck scoring and side-plan candidate scoring inside matchup matrix cells."
    if "validate_phase5x" in command:
        return "Split nested validator calls so Phase 5W smoke checks can be reused without rerunning integration commands."
    if "analyze_opponent_deck" in command:
        return "Reuse loaded card data and curated profile data across repeated opponent analyses."
    return "Profile JSON/report writes and repeated card database startup work."


def print_cache_summary() -> None:
    matrix_dir = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "matchup_matrix"
    reports = sorted(matrix_dir.glob("*_matchup_matrix.json"), key=lambda path: path.stat().st_mtime)
    if not reports:
        return
    payload = safe_load_json(reports[-1], {})
    if not isinstance(payload, dict):
        return
    stats = payload.get("runtime_stats", {})
    print("\nCache effectiveness summary:")
    for name, values in stats.items():
        print(f"- {name}: hits={values.get('hits', 0)} misses={values.get('misses', 0)}")


if __name__ == "__main__":
    main()
