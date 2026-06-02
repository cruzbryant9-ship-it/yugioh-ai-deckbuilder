from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScoreSnapshot:
    deck_names: tuple[str, ...]
    archetype: str
    mode: str
    breakdown: dict[str, Any]
    gameplay: dict[str, Any] | None = None
    package_quality: dict[str, Any] | None = None
    side_metrics: dict[str, Any] | None = None
    opponent_metrics: dict[str, Any] | None = None

    def merged_metrics(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for part in (self.breakdown, self.gameplay or {}, self.package_quality or {}, self.side_metrics or {}, self.opponent_metrics or {}):
            merged.update(part)
        return merged


def make_score_snapshot(deck: list[dict[str, Any]], archetype: str, mode: str, breakdown: dict[str, Any], **metrics: Any) -> ScoreSnapshot:
    return ScoreSnapshot(
        deck_names=tuple(str(card.get("name", "")) for card in deck),
        archetype=archetype,
        mode=mode,
        breakdown=dict(breakdown),
        gameplay=metrics.get("gameplay"),
        package_quality=metrics.get("package_quality"),
        side_metrics=metrics.get("side_metrics"),
        opponent_metrics=metrics.get("opponent_metrics"),
    )


class ScoreSnapshotCache:
    def __init__(self, max_entries: int = 2048) -> None:
        self.max_entries = max_entries
        self._breakdowns: OrderedDict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = OrderedDict()
        self._full_scores: OrderedDict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = OrderedDict()
        self.stats = {"hits": 0, "misses": 0}

    def reset(self) -> None:
        self._breakdowns.clear()
        self._full_scores.clear()
        self.stats = {"hits": 0, "misses": 0}

    def key(self, deck: list[dict[str, Any]], archetype: str, mode: str) -> tuple[str, str, tuple[str, ...]]:
        return archetype, mode, tuple(str(card.get("name", "")) for card in deck)

    def cached_breakdown(self, deck: list[dict[str, Any]], archetype: str, mode: str, loader) -> dict[str, Any]:
        key = self.key(deck, archetype, mode)
        if key in self._breakdowns:
            self.stats["hits"] += 1
            self._breakdowns.move_to_end(key)
            return dict(self._breakdowns[key])
        self.stats["misses"] += 1
        value = dict(loader())
        self._remember(self._breakdowns, key, value)
        return dict(value)

    def cached_full_score(self, deck: list[dict[str, Any]], archetype: str, mode: str, loader) -> dict[str, Any]:
        key = self.key(deck, archetype, mode)
        if key in self._full_scores:
            self.stats["hits"] += 1
            self._full_scores.move_to_end(key)
            return dict(self._full_scores[key])
        self.stats["misses"] += 1
        value = dict(loader())
        self._remember(self._full_scores, key, value)
        return dict(value)

    def _remember(self, cache: OrderedDict, key: tuple[str, str, tuple[str, ...]], value: dict[str, Any]) -> None:
        cache[key] = value
        cache.move_to_end(key)
        if self.max_entries <= 0:
            return
        while len(cache) > self.max_entries:
            cache.popitem(last=False)


DEFAULT_SCORE_CACHE = ScoreSnapshotCache()
