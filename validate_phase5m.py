from __future__ import annotations

import json
import argparse
import subprocess
import sys
from pathlib import Path

from data.card_limits import get_blocked_card_names, normalize_card_name
from deck.builder import build_deck
from deck.matchup_engine_stats import MATCHUP_ENGINE_STATS_PATH
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.card_database import CardDatabase
from config.settings import MATRIX_FULL_RUNS_PER_CELL, MATRIX_SMOKE_RUNS_PER_CELL

ROOT = Path(__file__).resolve().parent
MATRIX_DIR = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "matchup_matrix"
VALIDATION_MODE = "smoke"


def main() -> None:
    global VALIDATION_MODE
    args = parse_args()
    VALIDATION_MODE = "full" if args.full else "smoke"
    checks = [
        (f"matchup matrix runs in {VALIDATION_MODE} mode", validate_matrix_command),
        ("JSON report is saved", validate_json_report),
        ("markdown report is saved", validate_markdown_report),
        ("matchup engine stats exists", validate_stats_created),
        ("build_deck accepts matchup and going", validate_build_deck_args),
        ("blocked cards never appear", validate_no_blocked_cards),
        ("rankings contain expected fields", validate_rankings),
        ("train/evaluate still run", validate_train_evaluate),
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
    print("Phase 5M validation complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 5M matchup matrix support.")
    parser.add_argument("--smoke", action="store_true", help="Run quick matrix validation. This is the default.")
    parser.add_argument("--full", action="store_true", help="Run full matrix validation sizes.")
    return parser.parse_args()


def validate_matrix_command() -> None:
    runs = MATRIX_FULL_RUNS_PER_CELL if VALIDATION_MODE == "full" else MATRIX_SMOKE_RUNS_PER_CELL
    extra = ["--full"] if VALIDATION_MODE == "full" else ["--smoke"]
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", str(runs), *extra, timeout=2400 if VALIDATION_MODE == "full" else 1200)


def latest_json_report() -> Path:
    reports = sorted(MATRIX_DIR.glob("*_blue-eyes_meta_matchup_matrix.json"), key=lambda path: path.stat().st_mtime)
    if not reports:
        raise AssertionError("no matrix JSON report found")
    return reports[-1]


def validate_json_report() -> None:
    path = latest_json_report()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("summary", {}).get("cell_count", 0) <= 0:
        raise AssertionError(payload.get("summary"))


def validate_markdown_report() -> None:
    path = MATRIX_DIR / "latest_matchup_matrix_report.md"
    if not path.exists() or "Best Engine By Matchup" not in path.read_text(encoding="utf-8"):
        raise AssertionError(path)


def validate_stats_created() -> None:
    path = ROOT / MATCHUP_ENGINE_STATS_PATH
    if not path.exists():
        raise AssertionError(path)


def validate_build_deck_args() -> None:
    cards = CardDatabase().load_cards()
    old_deck, old_pool = build_deck(cards, "Blue-Eyes", mode="meta")
    new_deck, new_pool = build_deck(cards, "Blue-Eyes", mode="meta", matchup="combo", going="both")
    if not old_pool or not new_pool or not old_deck or not new_deck:
        raise AssertionError((len(old_deck), len(new_deck), len(old_pool), len(new_pool)))


def validate_no_blocked_cards() -> None:
    payload = json.loads(latest_json_report().read_text(encoding="utf-8"))
    blocked_names = get_blocked_card_names()
    violations = []
    for cell in payload.get("cells", []):
        for deck_key in ("main_deck", "extra_deck"):
            for name in cell.get("best_deck", {}).get(deck_key, []):
                if normalize_card_name(name) in blocked_names:
                    violations.append(name)
        for name, _count in cell.get("recommended_side_deck", []):
            if normalize_card_name(name) in blocked_names:
                violations.append(name)
        for run in cell.get("runs", []):
            for card_name in run.get("blocked_card_violations", []):
                violations.append(card_name)
    if violations:
        raise AssertionError(sorted(set(violations)))


def validate_rankings() -> None:
    payload = json.loads(latest_json_report().read_text(encoding="utf-8"))
    rankings = payload.get("rankings", {})
    required = {
        "best_overall_engine",
        "best_engine_by_matchup",
        "best_going_first_engine",
        "best_going_second_engine",
        "safest_low_brick_engine",
        "best_side_deck_compatible_engine",
        "most_resilient_engine",
        "worst_engine_matchup_pairing",
    }
    missing = required - set(rankings)
    if missing:
        raise AssertionError(missing)


def validate_train_evaluate() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "both", timeout=240)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "both", timeout=240)


def run_command(*args: str, timeout: int = 180) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-2000:])


if __name__ == "__main__":
    main()
