from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.curated_opponent_library import curated_to_opponent_profile
from matchup_matrix import run_cell
from SystemAIYugioh.json_utils import atomic_write_json
from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.runtime_context import DEFAULT_RUNTIME_CONTEXT


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "determinism"
COMPARE_KEYS = (
    "average_final_score",
    "best_score",
    "side_deck_score",
    "post_side_score",
    "post_side_delta",
    "choke_stop_rate",
    "graph_stop_rate",
    "opponent_resource_valid_rate",
    "probability_weighted_stop_rate",
)


def run_determinism_check(seed: int = 8801) -> dict[str, Any]:
    startup_safety_cleanup()
    cards = DEFAULT_RUNTIME_CONTEXT.cards(refresh=True)
    profile = curated_to_opponent_profile(DEFAULT_RUNTIME_CONTEXT.curated_profiles()[0])
    with TemporaryDirectory(prefix="phase7a_determinism_") as folder:
        random.seed(seed)
        first = run_cell(cards, "Blue-Eyes", "meta", "pure", profile, "both", 1, True, MatrixCache(cache_dir=folder, enabled=False), seed)
        random.seed(seed)
        second = run_cell(cards, "Blue-Eyes", "meta", "pure", profile, "both", 1, True, MatrixCache(cache_dir=folder, enabled=False), seed)
    score_drift = compare_metric(first, second, "average_final_score")
    engine_drift = first.get("engine_variant") != second.get("engine_variant")
    deck_drift = first.get("best_deck") != second.get("best_deck")
    metric_drifts = [key for key in COMPARE_KEYS if first.get(key) != second.get(key)]
    unexpected = []
    if score_drift:
        unexpected.append("score drift")
    if engine_drift:
        unexpected.append("engine drift")
    if deck_drift:
        unexpected.append("deck drift")
    unexpected.extend(f"{key} drift" for key in metric_drifts if key != "average_final_score")
    report = {
        "report_type": "benchmark_determinism",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "same_seed_same_result": not unexpected,
        "score_drift": score_drift,
        "engine_drift": engine_drift,
        "deck_drift": deck_drift,
        "metric_drifts": Counter(metric_drifts).most_common(),
        "expected_randomness": [
            "Different seeds may choose different weighted deck packages and opening-hand samples.",
            "Cache-free repeated runs with the same seed should match exactly for the checked matrix cell.",
        ],
        "unexpected_randomness": unexpected,
    }
    save_report(report)
    return report


def compare_metric(first: dict[str, Any], second: dict[str, Any], key: str) -> float:
    try:
        return round(float(second.get(key, 0) or 0) - float(first.get(key, 0) or 0), 6)
    except (TypeError, ValueError):
        return 0.0 if first.get(key) == second.get(key) else 1.0


def save_report(report: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "latest_benchmark_determinism_report.json"
    atomic_write_json(path, report)
    return path


def main() -> None:
    report = run_determinism_check()
    print("Benchmark Determinism Check Complete")
    print(f"Same seed same result: {report['same_seed_same_result']}")
    print(f"Score drift: {report['score_drift']}")
    print(f"Engine drift: {report['engine_drift']}")
    print(f"Deck drift: {report['deck_drift']}")
    if not report["same_seed_same_result"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
