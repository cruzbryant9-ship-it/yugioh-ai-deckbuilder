from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


DEFAULT_ROOT = Path(__file__).resolve().parent
FOCUS_PATHS = (
    "SystemAIYugioh/data",
    "SystemAIYugioh/data/training_runs",
    "SystemAIYugioh/data/runtime_cache",
    "SystemAIYugioh/data/snapshots",
)


def human_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def iter_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return
    if path.is_file():
        yield path
        return
    for current, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if name not in {".git", ".idea", ".venv", "venv"}]
        current_path = Path(current)
        for file_name in files:
            file_path = current_path / file_name
            try:
                if file_path.is_file():
                    yield file_path
            except OSError:
                continue


def folder_size(path: Path) -> int:
    return sum(safe_size(file_path) for file_path in iter_files(path))


def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def largest_children(root: Path, limit: int = 20) -> list[dict[str, object]]:
    rows = []
    for child in root.iterdir() if root.exists() else []:
        if child.name == ".git":
            continue
        size = folder_size(child) if child.is_dir() else safe_size(child)
        rows.append({"path": str(child.relative_to(root)), "bytes": size, "size": human_size(size), "type": "dir" if child.is_dir() else "file"})
    return sorted(rows, key=lambda row: int(row["bytes"]), reverse=True)[:limit]


def largest_files(root: Path, limit: int = 30) -> list[dict[str, object]]:
    rows = []
    for file_path in iter_files(root):
        size = safe_size(file_path)
        rows.append({"path": str(file_path.relative_to(root)), "bytes": size, "size": human_size(size)})
    return sorted(rows, key=lambda row: int(row["bytes"]), reverse=True)[:limit]


def pattern_summary(root: Path) -> dict[str, dict[str, object]]:
    patterns = {
        "__pycache__ directories": [path for path in root.rglob("__pycache__") if path.is_dir()],
        "*.pyc files": list(root.rglob("*.pyc")),
        "*.tmp files": list(root.rglob("*.tmp")),
    }
    summary: dict[str, dict[str, object]] = {}
    for label, paths in patterns.items():
        total = 0
        for path in paths:
            total += folder_size(path) if path.is_dir() else safe_size(path)
        summary[label] = {"count": len(paths), "bytes": total, "size": human_size(total)}
    return summary


def build_report(root: Path = DEFAULT_ROOT, limit: int = 20) -> dict[str, object]:
    root = root.resolve()
    focus = []
    for rel in FOCUS_PATHS:
        path = root / rel
        size = folder_size(path)
        focus.append({"path": rel, "exists": path.exists(), "bytes": size, "size": human_size(size)})
    return {
        "root": str(root),
        "focus_paths": focus,
        "largest_children": largest_children(root, limit),
        "largest_files": largest_files(root, limit),
        "pattern_summary": pattern_summary(root),
    }


def print_report(report: dict[str, object]) -> None:
    print(f"Disk Usage Report: {report['root']}")
    print("\nFocus paths:")
    for row in report["focus_paths"]:  # type: ignore[index]
        print(f"- {row['path']}: {row['size']} ({'exists' if row['exists'] else 'missing'})")
    print("\nLargest project children:")
    for row in report["largest_children"]:  # type: ignore[index]
        print(f"- {row['size']:>10} {row['type']:>4} {row['path']}")
    print("\nLargest files:")
    for row in report["largest_files"]:  # type: ignore[index]
        print(f"- {row['size']:>10} {row['path']}")
    print("\nGenerated artifact patterns:")
    for label, row in report["pattern_summary"].items():  # type: ignore[union-attr]
        print(f"- {label}: {row['count']} items, {row['size']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Report project disk usage with focus on generated artifacts.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help=argparse.SUPPRESS)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    print_report(build_report(Path(args.root), args.limit))


if __name__ == "__main__":
    main()
