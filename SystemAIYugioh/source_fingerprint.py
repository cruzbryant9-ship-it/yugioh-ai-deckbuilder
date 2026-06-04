from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT


SOURCE_FINGERPRINT_VERSION = 1

SCORE_AFFECTING_SOURCE_FILES = (
    "deck/advisory_influence_budget.py",
    "deck/archetype_role_inference.py",
    "deck/builder.py",
    "deck/card_conditions.py",
    "deck/card_metadata.py",
    "deck/card_text_parser.py",
    "deck/chain_model.py",
    "deck/package_builder.py",
    "deck/hand_simulator.py",
    "deck/combo_lines.py",
    "deck/curated_opponent_memory.py",
    "deck/deck_analysis.py",
    "deck/deck_utils.py",
    "deck/generic_combo_skeleton.py",
    "deck/generic_deck_builder.py",
    "deck/generic_deck_repair.py",
    "deck/generic_filler_selector.py",
    "deck/generic_package_extractor.py",
    "deck/generic_package_replay.py",
    "deck/generic_repair_diagnostics.py",
    "deck/generic_tuner.py",
    "deck/interruption_profiles.py",
    "deck/line_graph.py",
    "deck/line_validator.py",
    "deck/package_quality.py",
    "deck/packages.py",
    "deck/post_side_memory.py",
    "deck/resource_state.py",
    "deck/side_application.py",
    "deck/side_deck_scoring.py",
    "deck/side_deck_planner.py",
    "deck/side_plan_optimizer.py",
    "deck/post_side_evaluation.py",
    "deck/choke_simulator.py",
    "deck/opponent_graph_simulator.py",
    "deck/opponent_probability_simulator.py",
    "deck/opponent_analyzer.py",
    "deck/opponent_choke_model.py",
    "deck/opponent_branch_graph.py",
    "deck/opponent_profiles.py",
    "deck/opponent_resource_state.py",
    "deck/matchup_profiles.py",
    "deck/matchup_engine_stats.py",
    "deck/engine_variants.py",
    "deck/timing_windows.py",
    "SystemAIYugioh/banlist.py",
    "SystemAIYugioh/cache_fingerprint.py",
    "SystemAIYugioh/matrix_cache.py",
    "SystemAIYugioh/metric_registry.py",
    "SystemAIYugioh/opponent_metric_builder.py",
    "SystemAIYugioh/opponent_signal_sentinel.py",
    "SystemAIYugioh/regression_gates.py",
    "SystemAIYugioh/report_schema.py",
    "SystemAIYugioh/score_snapshot.py",
    "matchup_matrix.py",
)


def source_fingerprint(extra_files: list[str | Path] | None = None) -> dict[str, Any]:
    files = list(SCORE_AFFECTING_SOURCE_FILES)
    if extra_files:
        files.extend(normalize_relative_path(path) for path in extra_files)
    file_payload = {
        relative: source_file_state(PROJECT_ROOT / relative)
        for relative in sorted(dict.fromkeys(files))
    }
    payload = {
        "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
        "files": file_payload,
    }
    return {
        "fingerprint": stable_hash(payload),
        "source_hash": stable_hash(file_payload),
        "file_count": len(file_payload),
        "files": file_payload,
        "version": SOURCE_FINGERPRINT_VERSION,
    }


def normalize_relative_path(path: str | Path) -> str:
    item = Path(path)
    if item.is_absolute():
        item = item.resolve().relative_to(PROJECT_ROOT)
    return item.as_posix()


def source_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "sha256": None, "size": 0}
    return {
        "exists": True,
        "sha256": file_hash(path),
        "size": path.stat().st_size,
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
