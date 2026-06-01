from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deck.choke_simulator import simulate_choke_points
from deck.curated_opponent_library import curated_to_opponent_profile, find_curated_profile
from deck.opponent_choke_model import get_opponent_lines
from deck.side_deck_planner import build_side_deck
from deck.timing_windows import best_timing_for_interruption, list_timing_windows, timing_for_interruption

ROOT = Path(__file__).resolve().parent


def card(name: str, card_type: str = "Effect Monster", desc: str = "") -> dict:
    return {"name": name, "type": card_type, "desc": desc, "archetype": ""}


def database() -> list[dict]:
    return [
        card("Blue-Eyes White Dragon", "Normal Monster", "Level 8 Dragon."),
        card("Sage with Eyes of Blue", desc="Add 1 LIGHT tuner from your Deck."),
        card("Ash Blossom & Joyous Spring", desc="Negate adding from Deck."),
        card("Droll & Lock Bird", desc="Stop cards added from Deck."),
        card("Infinite Impermanence", "Trap Card", "Negate a monster effect."),
        card("Effect Veiler", desc="Negate a monster effect."),
        card("D.D. Crow", desc="Banish a card from the GY."),
        card("Ghost Belle & Haunted Mansion", desc="Negate GY movement."),
        card("Nibiru, the Primal Being", desc="Tribute monsters after many summons."),
        card("Cosmic Cyclone", "Spell Card", "Banish 1 Spell/Trap."),
    ]


def main() -> None:
    checks = [
        ("opponent has multiple branchable lines", validate_branchable_lines),
        ("timing windows load", validate_timing_windows),
        ("Ash maps to search timing", validate_ash_timing),
        ("Crow maps to GY timing", validate_crow_timing),
        ("Imperm/Veiler map to field timing", validate_field_timing),
        ("simulator recommends timing window", validate_simulator_timing),
        ("backup line and pivot risk recorded", validate_pivot_risk),
        ("analyze_opponent_deck prints timing recommendations", validate_analyzer_timing),
        ("side planner uses timing-aware reasons", validate_side_planner_timing),
        ("train/evaluate/matrix/post-side still run", validate_integration),
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
    print("Phase 5U validation complete.")


def snake_eye_profile():
    curated = find_curated_profile("Snake-Eye")
    if not curated:
        raise AssertionError("Snake-Eye curated profile missing")
    return curated_to_opponent_profile(curated)


def validate_branchable_lines() -> None:
    lines = get_opponent_lines(snake_eye_profile())
    if len(lines) < 3 or not all(line.branch_points and line.timing_windows for line in lines):
        raise AssertionError(lines)


def validate_timing_windows() -> None:
    windows = set(list_timing_windows())
    if "before search resolves" not in windows or "in GY" not in windows:
        raise AssertionError(windows)


def validate_ash_timing() -> None:
    if best_timing_for_interruption("Ash Blossom", ("before search resolves", "in GY")) != "before search resolves":
        raise AssertionError(timing_for_interruption("Ash Blossom"))


def validate_crow_timing() -> None:
    if "in GY" not in timing_for_interruption("D.D. Crow"):
        raise AssertionError(timing_for_interruption("D.D. Crow"))


def validate_field_timing() -> None:
    veiler = timing_for_interruption("Effect Veiler")
    imperm = timing_for_interruption("Infinite Impermanence")
    if "on summon" not in veiler or "on resolution" not in imperm:
        raise AssertionError((veiler, imperm))


def validate_simulator_timing() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring", "Droll & Lock Bird", "D.D. Crow", "Infinite Impermanence"])
    if not report["best_timing_windows"] or report["timing_precision_score"] <= 0:
        raise AssertionError(report)


def validate_pivot_risk() -> None:
    report = simulate_choke_points(snake_eye_profile(), ["Ash Blossom & Joyous Spring", "D.D. Crow"])
    if report["pivot_risk_score"] <= 0 or report["backup_line_success_rate"] <= 0:
        raise AssertionError(report)


def validate_analyzer_timing() -> None:
    output = run_command("analyze_opponent_deck.py", "--decklist", "sample_opponent_deck.txt", "--archetype", "Blue-Eyes", "--mode", "meta", "--going", "second", timeout=700)
    if "Best timing windows:" not in output or "Pivot risk score:" not in output:
        raise AssertionError(output[-2000:])


def validate_side_planner_timing() -> None:
    report = build_side_deck(database(), "Blue-Eyes", snake_eye_profile(), database(), going="second")
    reasons = {reason for reason_list in report["reasons"].values() for reason in reason_list}
    if "timing_aware_choke" not in reasons or report["timing_precision_score"] <= 0:
        raise AssertionError(report)


def validate_integration() -> None:
    run_command("train_agent.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=800)
    run_command("evaluate_learning.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs", "2", "--matchup", "combo", "--going", "second", timeout=800)
    run_command("post_side_evaluator.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--matchup", "combo", "--going", "second", "--runs", "1", timeout=800)
    run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", timeout=2100)


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
