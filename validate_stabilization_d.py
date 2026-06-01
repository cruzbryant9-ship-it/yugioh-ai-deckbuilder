from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.score_snapshot import DEFAULT_SCORE_CACHE
from deck.post_side_evaluation import score_full_deck
from deck.side_plan_optimizer import cached_candidate_score, side_candidate_cache_stats

ROOT = Path(__file__).resolve().parent


def main() -> None:
    checks = [
        ("persistent matrix cache works", validate_persistent_matrix_cache),
        ("score snapshot cache reuses full scores", validate_score_cache),
        ("side candidate score cache works", validate_candidate_cache),
        ("matrix smoke reports cache stats", validate_matrix_cache_stats),
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
    print("Stabilization Pass D validation complete.")


def validate_persistent_matrix_cache() -> None:
    cache_dir = ROOT / "SystemAIYugioh" / "data" / "runtime_cache" / "_validation_matrix"
    cache = MatrixCache(cache_dir=cache_dir)
    key = cache.key(test="persistent")
    cache.set(key, {"value": 7})
    second = MatrixCache(cache_dir=cache_dir)
    loaded = second.get(key)
    if loaded != {"value": 7} or second.stats["disk_hits"] < 1:
        raise AssertionError((loaded, second.stats))


def validate_score_cache() -> None:
    DEFAULT_SCORE_CACHE.reset()
    deck = [{"name": "Blue-Eyes White Dragon", "type": "Normal Monster"}]
    first = score_full_deck(deck, "Blue-Eyes", "meta")
    second = score_full_deck(deck, "Blue-Eyes", "meta")
    if first != second or DEFAULT_SCORE_CACHE.stats["hits"] < 1:
        raise AssertionError(DEFAULT_SCORE_CACHE.stats)


def validate_candidate_cache() -> None:
    deck = [{"name": "Blue-Eyes White Dragon", "type": "Normal Monster"}]
    cached_candidate_score(deck, "Blue-Eyes", "meta")
    cached_candidate_score(deck, "Blue-Eyes", "meta")
    if side_candidate_cache_stats()["hits"] < 1:
        raise AssertionError(side_candidate_cache_stats())


def validate_matrix_cache_stats() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])
    output2 = run_command("profile_runtime.py", "--smoke", "--quick", timeout=300)
    if "Cache effectiveness summary" not in output2 and "Runtime Profile" not in output2:
        raise AssertionError(output2[-2500:])


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


if __name__ == "__main__":
    main()
