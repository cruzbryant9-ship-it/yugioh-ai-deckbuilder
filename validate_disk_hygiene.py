from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from cleanup_generated_artifacts import backup_learning, collect_candidates, execute_cleanup
from disk_usage_report import build_report
from SystemAIYugioh.validation_harness import assert_success, run_checks, run_python


VALIDATION_JSON = Path("SystemAIYugioh") / "data" / "training_runs" / "validation" / "validate_disk_hygiene.json"
FIXTURE_ROOT = Path(".disk_hygiene_fixture")


def main() -> None:
    checks = [
        ("disk usage report works", validate_disk_report),
        ("dry-run works", validate_dry_run),
        ("execute only removes generated artifacts", validate_execute_fixture),
        ("source files are not deleted", validate_source_preserved),
        ("learned memory files are preserved", validate_learned_memory_preserved),
        (".gitignore contains rules", validate_gitignore),
        ("backup-learning copies learned memory", validate_backup_learning_fixture),
    ]
    result = run_checks("validate_disk_hygiene", checks, json_path=VALIDATION_JSON)
    if not result.passed:
        raise SystemExit(1)
    print("Disk hygiene validation complete.")


def validate_disk_report() -> dict[str, Any]:
    report = build_report(Path("."), limit=5)
    if "focus_paths" not in report or "pattern_summary" not in report:
        raise AssertionError(report)
    return {
        "focus_paths": report["focus_paths"],
        "pattern_summary": report["pattern_summary"],
    }


def validate_dry_run() -> dict[str, Any]:
    result = run_python("cleanup_generated_artifacts.py", "--dry-run", timeout=120)
    assert_success(result, ("Cleanup mode: dry-run", "Estimated reclaimable space:"))
    return {"returncode": result.returncode, "duration_seconds": round(result.duration_seconds, 4)}


def validate_execute_fixture() -> dict[str, Any]:
    fixture = make_fixture()
    candidates = collect_candidates(fixture)
    removed = execute_cleanup(candidates, fixture)
    generated_paths = [
        fixture / "SystemAIYugioh" / "data" / "runtime_cache",
        fixture / "SystemAIYugioh" / "data" / "training_runs",
        fixture / "SystemAIYugioh" / "data" / "snapshots",
        fixture / "pkg" / "__pycache__",
        fixture / "temp.tmp",
    ]
    survivors = [str(path) for path in generated_paths if path.exists()]
    if survivors:
        raise AssertionError({"survivors": survivors, "removed": [str(item.path) for item in removed]})
    return {"removed_count": len(removed), "removed_bytes": sum(item.bytes for item in removed)}


def validate_source_preserved() -> dict[str, Any]:
    fixture = make_fixture()
    execute_cleanup(collect_candidates(fixture), fixture)
    source = fixture / "deck" / "builder.py"
    docs = fixture / "README.md"
    config = fixture / "config" / "settings.toml"
    missing = [str(path) for path in (source, docs, config) if not path.exists()]
    if missing:
        raise AssertionError(missing)
    return {"preserved": [str(source), str(docs), str(config)]}


def validate_learned_memory_preserved() -> dict[str, Any]:
    fixture = make_fixture()
    execute_cleanup(collect_candidates(fixture), fixture)
    memories = [
        fixture / "SystemAIYugioh" / "data" / "deck_profiles" / "learned_card_stats.json",
        fixture / "SystemAIYugioh" / "data" / "deck_profiles" / "learning_tuning.json",
        fixture / "SystemAIYugioh" / "data" / "meta_stats.json",
    ]
    missing = [str(path) for path in memories if not path.exists()]
    if missing:
        raise AssertionError(missing)
    return {"preserved": [str(path) for path in memories]}


def validate_gitignore() -> dict[str, Any]:
    text = Path(".gitignore").read_text(encoding="utf-8")
    required = [
        "SystemAIYugioh/data/runtime_cache/",
        "SystemAIYugioh/data/training_runs/",
        "SystemAIYugioh/data/snapshots/",
        "**/__pycache__/",
        "*.pyc",
        "*.tmp",
    ]
    missing = [rule for rule in required if rule not in text]
    if missing:
        raise AssertionError(missing)
    return {"rules": required}


def validate_backup_learning_fixture() -> dict[str, Any]:
    fixture = make_fixture()
    backup_root, copied = backup_learning(fixture)
    copied_names = sorted(path.name for path in copied)
    expected = {"learned_card_stats.json", "learning_tuning.json", "meta_stats.json"}
    if not expected.issubset(set(copied_names)):
        raise AssertionError({"copied": copied_names, "backup_root": str(backup_root)})
    return {"backup_root": str(backup_root), "copied": copied_names}


def make_fixture() -> Path:
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    paths = [
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "runtime_cache" / "matrix" / "cache.json",
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "training_runs" / "latest_report.json",
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "snapshots" / "cards_20260608.json",
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "deck_profiles" / "learned_card_stats.json",
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "deck_profiles" / "learning_tuning.json",
        FIXTURE_ROOT / "SystemAIYugioh" / "data" / "meta_stats.json",
        FIXTURE_ROOT / "pkg" / "__pycache__" / "mod.cpython-310.pyc",
        FIXTURE_ROOT / "temp.tmp",
        FIXTURE_ROOT / "deck" / "builder.py",
        FIXTURE_ROOT / "README.md",
        FIXTURE_ROOT / "config" / "settings.toml",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    return FIXTURE_ROOT.resolve()


if __name__ == "__main__":
    main()
