from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SECTION_ALIASES = {
    "main": "main",
    "main deck": "main",
    "#main": "main",
    "monster": "main",
    "spells": "main",
    "traps": "main",
    "extra": "extra",
    "extra deck": "extra",
    "#extra": "extra",
    "side": "side",
    "side deck": "side",
    "!side": "side",
}


def parse_decklist_file(path: str | Path) -> dict[str, list[str]]:
    return parse_decklist_text(Path(path).read_text(encoding="utf-8"))


def parse_decklist_text(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"main": [], "extra": [], "side": []}
    current = "main"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        normalized = line.rstrip(":").casefold()
        if normalized in SECTION_ALIASES:
            current = SECTION_ALIASES[normalized]
            continue
        if line.startswith("#"):
            current = SECTION_ALIASES.get(line.casefold(), current)
            continue
        if line.startswith("!"):
            current = SECTION_ALIASES.get(line.casefold(), current)
            continue
        count, name = parse_card_line(line)
        if not name:
            continue
        sections[current].extend([name] * count)
    sections["all_cards"] = [*sections["main"], *sections["extra"], *sections["side"]]
    return sections


def parse_card_line(line: str) -> tuple[int, str]:
    cleaned = re.sub(r"\s+#.*$", "", line).strip()
    match = re.match(r"^(?:(\d+)\s*[xX]?\s+)(.+)$", cleaned)
    if match:
        return max(1, int(match.group(1))), clean_name(match.group(2))
    match = re.match(r"^(.+?)\s*[xX]\s*(\d+)$", cleaned)
    if match:
        return max(1, int(match.group(2))), clean_name(match.group(1))
    return 1, clean_name(cleaned)


def clean_name(name: str) -> str:
    return name.strip(" -\t")
