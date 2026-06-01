from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from SystemAIYugioh.json_utils import atomic_json_write, safe_load_json
from SystemAIYugioh.matrix_cache import MatrixCache
from SystemAIYugioh.report_builder import build_report, merge_metric_sections, validate_or_raise
from SystemAIYugioh.runtime_context import RuntimeContext
from SystemAIYugioh.score_snapshot import make_score_snapshot
from SystemAIYugioh.validation_core import check_matrix_report, check_runtime_stats
from deck.side_plan_optimizer import optimize_side_plan

ROOT = Path(__file__).resolve().parent
MATRIX_DIR = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "matchup_matrix"


def main() -> None:
    checks = [
        ("runtime context reuse works", validate_runtime_context),
        ("matrix cache works", validate_matrix_cache),
        ("cache hit/miss tracking works", validate_cache_stats),
        ("validator topology no longer nests older validators directly", validate_validator_topology),
        ("side-plan pruning works", validate_side_pruning),
        ("score snapshots reuse correctly", validate_score_snapshot),
        ("report builder works", validate_report_builder),
        ("JSON helper migration completed", validate_json_migration),
        ("smoke/full flags work consistently", validate_smoke_full_flags),
        ("matchup_matrix smoke still runs", validate_matrix_smoke),
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
    print("Stabilization Pass C validation complete.")


def validate_runtime_context() -> None:
    context = RuntimeContext()
    first = context.cards(refresh=False)
    second = context.cards(refresh=False)
    if first is not second or context.stats["hits"] < 1:
        raise AssertionError(context.stats)
    context.reset()
    if context.stats != {"hits": 0, "misses": 0}:
        raise AssertionError(context.stats)


def validate_matrix_cache() -> None:
    cache = MatrixCache(cache_dir=temp_cache_dir("matrix"))
    key = cache.key(archetype="Blue-Eyes", mode="meta", variant="pure")
    if cache.get(key) is not None:
        raise AssertionError("unexpected cache hit")
    cache.set(key, {"ok": True})
    if cache.get(key).get("ok") is not True:
        raise AssertionError(cache.stats)


def validate_cache_stats() -> None:
    cache = MatrixCache(cache_dir=temp_cache_dir("stats"))
    key = cache.key(cell="x")
    cache.get(key)
    cache.set(key, {"x": 1})
    cache.get(key)
    check_runtime_stats(cache.stats)
    if cache.stats["hits"] != 1 or cache.stats["misses"] != 1:
        raise AssertionError(cache.stats)


def validate_validator_topology() -> None:
    phase5x = (ROOT / "validate_phase5x.py").read_text(encoding="utf-8")
    if "validate_phase5w.py" in phase5x:
        raise AssertionError("validate_phase5x still shells out to validate_phase5w")


def validate_side_pruning() -> None:
    from SystemAIYugioh.card_database import CardDatabase
    from deck.builder import build_deck
    from deck.deck_utils import split_deck
    from deck.side_deck_planner import build_side_deck

    cards = CardDatabase().load_cards()
    deck, _pool = build_deck(cards, "Blue-Eyes", mode="meta")
    main, _extra = split_deck(deck)
    side = build_side_deck(deck, "Blue-Eyes", "combo", cards, going="second")
    result = optimize_side_plan(main, side["side_deck"], "combo", "second", cards, max_candidates=8, archetype="Blue-Eyes", mode="meta")
    for key in ("pruned_candidate_count", "duplicate_candidate_count", "early_rejection_count"):
        if key not in result:
            raise AssertionError(result)


def validate_score_snapshot() -> None:
    deck = [{"name": "Blue-Eyes White Dragon"}]
    snapshot = make_score_snapshot(deck, "Blue-Eyes", "meta", {"final_score": 1}, gameplay={"brick_rate": 0.1})
    merged = snapshot.merged_metrics()
    if merged["final_score"] != 1 or merged["brick_rate"] != 0.1:
        raise AssertionError(merged)


def validate_report_builder() -> None:
    report = build_report("matchup_matrix", {"x": 1}, {"cell_count": 1}, rankings={}, cells=[])
    validate_or_raise("matchup_matrix", report)
    merged = merge_metric_sections({"a": 1}, {"b": 2}, ("a", "b", "c"))
    if merged != {"a": 1, "b": 2, "c": 0}:
        raise AssertionError(merged)


def validate_json_migration() -> None:
    offenders = []
    allowed = {
        "SystemAIYugioh\\json_utils.py",
        "SystemAIYugioh\\card_database.py",
        "SystemAIYugioh\\matrix_cache.py",
        "SystemAIYugioh\\cache_fingerprint.py",
    }
    for folder in ("deck", "data", "SystemAIYugioh"):
        for path in (ROOT / folder).glob("*.py"):
            rel = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8")
            if rel not in allowed and ("json.dump" in text or "json.load(" in text or "json.loads" in text):
                offenders.append(rel)
    if offenders:
        raise AssertionError(offenders)
    temp = ROOT / "SystemAIYugioh" / "data" / "training_runs" / "_stabilization_c_json.json"
    atomic_json_write(temp, {"ok": True})
    if safe_load_json(temp, {}).get("ok") is not True:
        raise AssertionError(temp)


def validate_smoke_full_flags() -> None:
    for path_name in ("validate_phase5m.py", "validate_phase5x.py", "matchup_matrix.py"):
        text = (ROOT / path_name).read_text(encoding="utf-8")
        if "--smoke" not in text or "--full" not in text:
            raise AssertionError(path_name)


def validate_matrix_smoke() -> None:
    output = run_command("matchup_matrix.py", "--archetype", "Blue-Eyes", "--mode", "meta", "--runs-per-cell", "1", "--use-curated-opponents", "--smoke", timeout=1800)
    if "Matchup Matrix Complete" not in output:
        raise AssertionError(output[-2500:])
    check_matrix_report(latest_matrix_report())


def latest_matrix_report() -> Path:
    reports = sorted(MATRIX_DIR.glob("*_blue-eyes_meta_matchup_matrix.json"), key=lambda path: path.stat().st_mtime)
    if not reports:
        raise AssertionError("no matrix report")
    return reports[-1]


def run_command(*args: str, timeout: int = 180) -> str:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if result.returncode:
        raise AssertionError(result.stdout[-3000:])
    return result.stdout


def temp_cache_dir(label: str) -> Path:
    path = ROOT / "SystemAIYugioh" / "data" / "runtime_cache" / f"_stabilization_c_{label}_{time.time_ns()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    main()
