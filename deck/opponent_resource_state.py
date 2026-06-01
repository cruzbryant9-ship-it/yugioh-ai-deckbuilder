from __future__ import annotations

from typing import Any


class OpponentResourceState:
    def __init__(
        self,
        hand: list[Any] | None = None,
        field: list[Any] | None = None,
        graveyard: list[Any] | None = None,
        banished: list[Any] | None = None,
        deck: list[Any] | None = None,
        extra_deck: list[Any] | None = None,
    ) -> None:
        self.hand = list(hand or [])
        self.field = list(field or [])
        self.graveyard = list(graveyard or [])
        self.banished = list(banished or [])
        self.deck = list(deck or [])
        self.extra_deck = list(extra_deck or [])
        self.used_normal_summon = False
        self.used_once_per_turn_tags: set[str] = set()
        self.locks: set[str] = set()
        self.turn_events: list[dict[str, Any]] = []

    def location(self, name: str) -> list[Any]:
        return getattr(self, name)

    def has_card(self, location: str, card_name: str) -> bool:
        return any(card_label(card) == card_name for card in self.location(location))

    def has_any(self, location: str, card_names: tuple[str, ...] | list[str]) -> bool:
        return any(self.has_card(location, name) for name in card_names)

    def move_card(self, from_location: str, to_location: str, card_name: str) -> bool:
        source = self.location(from_location)
        for index, card in enumerate(source):
            if card_label(card) == card_name:
                moved = source.pop(index)
                self.location(to_location).append(moved)
                self.record_event("move", card_name, {"from": from_location, "to": to_location})
                return True
        return False

    def add_card(self, location: str, card_name: str) -> None:
        self.location(location).append(card_name)
        self.record_event("add", card_name, {"to": location})

    def consume_card(self, location: str, card_name: str) -> bool:
        source = self.location(location)
        for index, card in enumerate(source):
            if card_label(card) == card_name:
                source.pop(index)
                self.record_event("consume", card_name, {"from": location})
                return True
        return False

    def search_deck(self, card_name: str) -> bool:
        return self.move_card("deck", "hand", card_name)

    def summon_from_hand(self, card_name: str) -> bool:
        return self.move_card("hand", "field", card_name)

    def summon_from_deck(self, card_name: str) -> bool:
        return self.move_card("deck", "field", card_name)

    def summon_from_extra(self, card_name: str) -> bool:
        return self.move_card("extra_deck", "field", card_name)

    def send_to_gy(self, card_name: str) -> bool:
        return self.move_card("hand", "graveyard", card_name) or self.move_card("field", "graveyard", card_name) or self.move_card("deck", "graveyard", card_name)

    def banish_from_gy(self, card_name: str) -> bool:
        return self.move_card("graveyard", "banished", card_name)

    def can_use_once_per_turn(self, tag: str) -> bool:
        return not tag or tag not in self.used_once_per_turn_tags

    def use_once_per_turn(self, tag: str) -> bool:
        if not self.can_use_once_per_turn(tag):
            return False
        if tag:
            self.used_once_per_turn_tags.add(tag)
        return True

    def record_event(self, event_type: str, card_name: str, metadata: dict[str, Any] | None = None) -> None:
        self.turn_events.append({"event_type": event_type, "card_name": card_name, "metadata": metadata or {}})


def card_label(card: Any) -> str:
    if isinstance(card, dict):
        return str(card.get("name", ""))
    return str(card)
