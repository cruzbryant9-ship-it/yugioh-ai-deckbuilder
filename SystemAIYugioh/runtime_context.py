from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from SystemAIYugioh.card_database import CardDatabase
from SystemAIYugioh.json_utils import safe_load_json


class RuntimeContext:
    def __init__(self, max_entries: int = 128) -> None:
        self.max_entries = max_entries
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self.stats = {"hits": 0, "misses": 0}

    def reset(self) -> None:
        self._cache.clear()
        self.stats = {"hits": 0, "misses": 0}

    def get(self, key: str, loader) -> Any:
        if key in self._cache:
            self.stats["hits"] += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self.stats["misses"] += 1
        value = loader()
        self._cache[key] = value
        self._cache.move_to_end(key)
        if self.max_entries > 0:
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return value

    def card_database(self) -> CardDatabase:
        return self.get("card_database", CardDatabase)

    def cards(self, refresh: bool = True) -> list[dict[str, Any]]:
        def load() -> list[dict[str, Any]]:
            database = self.card_database()
            if refresh:
                try:
                    database.refresh_on_startup()
                except RuntimeError:
                    pass
            return database.load_cards()

        return self.get(f"cards:{refresh}", load)

    def curated_profiles(self) -> list[dict[str, Any]]:
        from deck.curated_opponent_library import load_curated_profiles

        return self.get("curated_profiles", load_curated_profiles)

    def matchup_profile(self, name: str):
        from deck.matchup_profiles import get_matchup_profile

        return self.get(f"matchup_profile:{name}", lambda: get_matchup_profile(name))

    def parsed_decklist(self, path: str | Path) -> dict[str, list[str]]:
        from deck.decklist_parser import parse_decklist_file

        resolved = str(Path(path).resolve())
        return self.get(f"decklist:{resolved}", lambda: parse_decklist_file(resolved))

    def json_file(self, path: str | Path, default: Any = None) -> Any:
        resolved = str(Path(path).resolve())
        return self.get(f"json:{resolved}", lambda: safe_load_json(resolved, default))


DEFAULT_RUNTIME_CONTEXT = RuntimeContext()


def reset_runtime_context() -> None:
    DEFAULT_RUNTIME_CONTEXT.reset()
