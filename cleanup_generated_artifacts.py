from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
GENERATED_DIRS = (
    Path("SystemAIYugioh/data/runtime_cache"),
    Path("SystemAIYugioh/data/training_runs"),
    Path("SystemAIYugioh/data/snapshots"),
)
LEARNED_MEMORY_NAMES = {
    "learned_card_stats.json",
    "learning_tuning.json",
    "learned_engine_stats.json",
    "meta_stats.json",
    "generic_ratio_memory.json",
    "matchup_engine_stats.json",
    "curated_opponent_memory.json",
    "post_side_memory.json",
    "post_side_stats.json",
    "generic_filler_memory.json",
}
SOURCE_EXTENSIONS = {".py", ".md", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".json"}


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    reason: str
    bytes: int


def human_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def safe_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        return sum(safe_size(child) for child in path.rglob("*") if child.is_file())
    except OSError:
        return 0


def is_learned_memory(path: Path) -> bool:
    return path.name in LEARNED_MEMORY_NAMES


def collect_candidates(root: Path = ROOT) -> list[CleanupCandidate]:
    root = root.resolve()
    candidates: dict[Path, CleanupCandidate] = {}
    for rel in GENERATED_DIRS:
        path = root / rel
        if path.exists():
            candidates[path] = CleanupCandidate(path, f"generated directory: {rel.as_posix()}", safe_size(path))
    for pycache in root.rglob("__pycache__"):
        if pycache.is_dir():
            candidates[pycache] = CleanupCandidate(pycache, "Python bytecode cache directory", safe_size(pycache))
    for pattern, reason in (("*.pyc", "Python bytecode file"), ("*.tmp", "temporary atomic-write or runtime file")):
        for file_path in root.rglob(pattern):
            if file_path.is_file() and not is_learned_memory(file_path):
                candidates[file_path] = CleanupCandidate(file_path, reason, safe_size(file_path))
    return sorted(candidates.values(), key=lambda candidate: str(candidate.path).casefold())


def collect_learning_files(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    return sorted(
        [path for path in (root / "SystemAIYugioh" / "data").rglob("*.json") if path.name in LEARNED_MEMORY_NAMES],
        key=lambda path: str(path).casefold(),
    ) if (root / "SystemAIYugioh" / "data").exists() else []


def backup_learning(root: Path = ROOT) -> tuple[Path, list[Path]]:
    root = root.resolve()
    backup_root = root / "backup_learning" / datetime.now().strftime("%Y%m%d_%H%M%S")
    copied: list[Path] = []
    for source in collect_learning_files(root):
        destination = backup_root / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return backup_root, copied


def validate_candidate(candidate: CleanupCandidate, root: Path) -> None:
    root = root.resolve()
    path = candidate.path.resolve()
    if not str(path).casefold().startswith(str(root).casefold()):
        raise ValueError(f"refusing to delete outside project root: {path}")
    if path == root:
        raise ValueError("refusing to delete project root")
    if is_learned_memory(path):
        raise ValueError(f"refusing to delete learned memory file: {path}")
    if path.is_file() and path.suffix in SOURCE_EXTENSIONS and path.suffix != ".tmp":
        raise ValueError(f"refusing to delete source/config/doc file: {path}")


def execute_cleanup(candidates: Iterable[CleanupCandidate], root: Path) -> list[CleanupCandidate]:
    removed: list[CleanupCandidate] = []
    for candidate in candidates:
        validate_candidate(candidate, root)
        if candidate.path.is_dir():
            shutil.rmtree(candidate.path)
        elif candidate.path.exists():
            candidate.path.unlink()
        removed.append(candidate)
    return removed


def render_summary(candidates: list[CleanupCandidate], action: str, backup: tuple[Path, list[Path]] | None = None) -> None:
    total = sum(candidate.bytes for candidate in candidates)
    print(f"Cleanup mode: {action}")
    print(f"Candidates: {len(candidates)}")
    print(f"Estimated reclaimable space: {human_size(total)}")
    if backup:
        backup_root, copied = backup
        print(f"Learning backup: {backup_root}")
        print(f"Learning files backed up: {len(copied)}")
    print("\nCandidates:")
    for candidate in sorted(candidates, key=lambda item: item.bytes, reverse=True):
        print(f"- {human_size(candidate.bytes):>10} {candidate.reason}: {candidate.path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely clean regenerated SystemAIYugioh artifacts.")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true", help="Show cleanup candidates without deleting anything.")
    mode.add_argument("--execute", action="store_true", help="Delete only allowlisted generated artifacts.")
    parser.add_argument("--backup-learning", action="store_true", help="Copy learned memory files into backup_learning/ before cleanup.")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    backup = backup_learning(root) if args.backup_learning else None
    candidates = collect_candidates(root)
    if args.execute:
        removed = execute_cleanup(candidates, root)
        render_summary(removed, "execute", backup)
    else:
        render_summary(candidates, "dry-run", backup)


if __name__ == "__main__":
    main()
