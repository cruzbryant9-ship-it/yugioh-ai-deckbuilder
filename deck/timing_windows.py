from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimingWindow:
    window_name: str
    valid_responses: tuple[str, ...]
    risk_if_missed: float
    best_response_cards: tuple[str, ...]
    poor_response_cards: tuple[str, ...]


TIMING_WINDOWS: dict[str, TimingWindow] = {
    "on activation": TimingWindow("on activation", ("Ash Blossom", "Cosmic Cyclone", "Solemn Judgment"), 0.55, ("Ash Blossom", "Cosmic Cyclone"), ("D.D. Crow",)),
    "on summon": TimingWindow("on summon", ("Infinite Impermanence", "Effect Veiler", "Book of Eclipse", "Nibiru"), 0.6, ("Infinite Impermanence", "Effect Veiler"), ("D.D. Crow",)),
    "on resolution": TimingWindow("on resolution", ("Infinite Impermanence", "Effect Veiler", "Ghost Belle"), 0.7, ("Infinite Impermanence", "Effect Veiler"), ("Lightning Storm",)),
    "in GY": TimingWindow("in GY", ("D.D. Crow", "Ghost Belle", "Called by the Grave", "Bystial", "Dimension Shifter"), 0.75, ("D.D. Crow", "Ghost Belle", "Bystial"), ("Effect Veiler",)),
    "before search resolves": TimingWindow("before search resolves", ("Ash Blossom", "Droll & Lock Bird"), 0.9, ("Ash Blossom", "Droll & Lock Bird"), ("D.D. Crow",)),
    "after search resolves": TimingWindow("after search resolves", ("Droll & Lock Bird", "Nibiru"), 0.65, ("Droll & Lock Bird",), ("Ash Blossom",)),
    "before special summon": TimingWindow("before special summon", ("Infinite Impermanence", "Effect Veiler", "Nibiru", "Book of Eclipse"), 0.7, ("Infinite Impermanence", "Effect Veiler", "Nibiru"), ("Cosmic Cyclone",)),
    "after material committed": TimingWindow("after material committed", ("D.D. Crow", "Ghost Belle", "Bystial", "Nibiru"), 0.8, ("D.D. Crow", "Ghost Belle", "Bystial"), ("Ash Blossom",)),
    "before endboard established": TimingWindow("before endboard established", ("Nibiru", "Dark Ruler No More", "Evenly Matched", "Book of Eclipse"), 0.85, ("Nibiru", "Book of Eclipse"), ("Ash Blossom",)),
}


def get_timing_window(window_name: str) -> TimingWindow | None:
    return TIMING_WINDOWS.get(window_name)


def list_timing_windows() -> tuple[str, ...]:
    return tuple(TIMING_WINDOWS)


def timing_for_interruption(interruption: str) -> tuple[str, ...]:
    hits = []
    for name, window in TIMING_WINDOWS.items():
        if any(matches_interruption(interruption, response) for response in window.valid_responses):
            hits.append(name)
    return tuple(hits)


def best_timing_for_interruption(interruption: str, candidate_windows: tuple[str, ...]) -> str | None:
    options = []
    for window_name in candidate_windows:
        window = get_timing_window(window_name)
        if not window:
            continue
        if any(matches_interruption(interruption, response) for response in window.valid_responses):
            bonus = 0.15 if any(matches_interruption(interruption, best) for best in window.best_response_cards) else 0.0
            options.append((window.risk_if_missed + bonus, window_name))
    if not options:
        return None
    return max(options)[1]


def is_poor_timing(interruption: str, window_name: str) -> bool:
    window = get_timing_window(window_name)
    if not window:
        return False
    return any(matches_interruption(interruption, poor) for poor in window.poor_response_cards)


def matches_interruption(card_name: str, label: str) -> bool:
    left = card_name.casefold()
    right = label.casefold()
    return left in right or right in left
