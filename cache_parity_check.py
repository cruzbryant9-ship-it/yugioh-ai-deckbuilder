from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from data.card_limits import startup_safety_cleanup
from deck.curated_opponent_library import curated_to_opponent_profile, load_curated_profiles
from matchup_matrix import GOING_OPTIONS, rank_matrix, run_cell
from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import atomic_write_json, atomic_write_text
from SystemAIYugioh.matrix_cache import MatrixCache


REPORT_DIR = Path("SystemAIYugioh") / "data" / "training_runs" / "cache_parity"
MARKDOWN_PATH = Path("CACHE_PARITY_REPORT.md")
COMPARE_KEYS = (
    "average_final_score",
    "best_score",
    "package_quality",
    "playable_hand_rate",
    "brick_rate",
    "resilience_score",
    "side_deck_score",
    "post_side_score",
    "post_side_delta",
    "choke_stop_rate",
    "opponent_recovery_rate",
    "graph_stop_rate",
    "graph_pivot_rate",
    "opponent_resource_valid_rate",
    "opponent_resource_failure_rate",
    "opponent_starter_open_rate",
    "opponent_brick_rate",
    "probability_weighted_stop_rate",
)


def run_cache_parity(seed: int = 7701, frozen_inputs: bool = True) -> dict[str, Any]:
    startup_safety_cleanup()
    cards = frozen_card_pool() if frozen_inputs else refreshed_card_pool()
    profile = curated_to_opponent_profile(load_curated_profiles()[0])
    cold_cells = []
    warm_cells = []
    with TemporaryDirectory(prefix="phase7a_matrix_cache_") as folder:
        warm_cache = MatrixCache(cache_dir=folder, enabled=True)
        for index, going in enumerate(GOING_OPTIONS):
            cell_seed = seed + index
            random.seed(cell_seed)
            cold = run_cell(cards, "Blue-Eyes", "meta", "pure", profile, going, 1, True, MatrixCache(cache_dir=folder, enabled=False), cell_seed)
            random.seed(cell_seed)
            run_cell(cards, "Blue-Eyes", "meta", "pure", profile, going, 1, True, warm_cache, cell_seed)
            random.seed(cell_seed)
            warm = run_cell(cards, "Blue-Eyes", "meta", "pure", profile, going, 1, True, warm_cache, cell_seed)
            cold_cells.append(cold)
            warm_cells.append(warm)
    comparisons = [compare_cells(cold, warm) for cold, warm in zip(cold_cells, warm_cells)]
    mismatches = [item for item in comparisons if item["mismatch_reasons"]]
    report = {
        "report_type": "cache_parity",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "frozen_inputs": frozen_inputs,
        "matched_cells": len(comparisons) - len(mismatches),
        "mismatched_cells": len(mismatches),
        "mismatch_reasons": Counter(reason for item in mismatches for reason in item["mismatch_reasons"]).most_common(),
        "best_engine_cold": rank_matrix(cold_cells).get("best_overall_engine", "none"),
        "best_engine_warm": rank_matrix(warm_cells).get("best_overall_engine", "none"),
        "comparisons": comparisons,
    }
    save_reports(report)
    return report


def frozen_card_pool() -> list[dict[str, Any]]:
    return CardDatabase().load_cards()


def refreshed_card_pool() -> list[dict[str, Any]]:
    database = CardDatabase()
    database.refresh_on_startup()
    return database.load_cards()


def compare_cells(cold: dict[str, Any], warm: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if not warm.get("cache_hit"):
        reasons.append("warm cell did not hit cache")
    for key in COMPARE_KEYS:
        if cold.get(key) != warm.get(key):
            reasons.append(f"{key} mismatch")
    cold_deck = cold.get("best_deck", {})
    warm_deck = warm.get("best_deck", {})
    if cold_deck != warm_deck:
        reasons.append("best deck mismatch")
    return {
        "engine_variant": cold.get("engine_variant"),
        "matchup": cold.get("matchup"),
        "going": cold.get("going"),
        "cache_hit": warm.get("cache_hit", False),
        "mismatch_reasons": reasons,
    }


def save_reports(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "latest_cache_parity_report.json"
    atomic_write_json(json_path, report)
    atomic_write_text(MARKDOWN_PATH, render_markdown(report, json_path))
    return json_path, MARKDOWN_PATH


def render_markdown(report: dict[str, Any], json_path: Path) -> str:
    lines = [
        "# Cache Parity Report",
        "",
        f"- JSON report: `{json_path}`",
        f"- Seed: {report['seed']}",
        f"- Matched cells: {report['matched_cells']}",
        f"- Mismatched cells: {report['mismatched_cells']}",
        f"- Best engine cold: {report['best_engine_cold']}",
        f"- Best engine warm: {report['best_engine_warm']}",
        "",
        "## Mismatch Reasons",
        "",
    ]
    if report["mismatch_reasons"]:
        for reason, count in report["mismatch_reasons"]:
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Cells", ""])
    for item in report["comparisons"]:
        reason = ", ".join(item["mismatch_reasons"]) or "matched"
        lines.append(f"- {item['engine_variant']} vs {item['matchup']} going {item['going']}: {reason}")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run_cache_parity()
    print("Cache Parity Complete")
    print(f"Matched cells: {report['matched_cells']}")
    print(f"Mismatched cells: {report['mismatched_cells']}")
    print(f"Markdown report: {MARKDOWN_PATH}")
    if report["mismatched_cells"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
