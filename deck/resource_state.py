from __future__ import annotations

from collections import Counter
from typing import Any

from deck.card_metadata import card_matches_requirement, get_card_name


class ResourceState:
    """Small string-based zone tracker for graph validation."""

    LOCATIONS = {"hand", "field", "graveyard", "banished", "deck", "extra_deck"}

    def __init__(
        self,
        hand: list[Any] | None = None,
        field: list[Any] | None = None,
        graveyard: list[Any] | None = None,
        banished: list[Any] | None = None,
        deck: list[Any] | None = None,
        extra_deck: list[Any] | None = None,
    ) -> None:
        self.card_objects: dict[str, Any] = {}
        self.hand = self._counter(hand or [])
        self.field = self._counter(field or [])
        self.graveyard = self._counter(graveyard or [])
        self.banished = self._counter(banished or [])
        self.deck = self._counter(deck or [])
        self.extra_deck = self._counter(extra_deck or [])
        self.used_normal_summon = False
        self.used_once_per_turn_tags: set[str] = set()
        self.locks: set[str] = set()
        self.movements: list[str] = []
        self.summoned_this_turn: set[str] = set()
        self.special_summoned_this_turn: set[str] = set()
        self.sent_to_gy_this_turn: set[str] = set()
        self.activated_cards_this_turn: set[str] = set()
        self.resolved_effects_this_turn: set[str] = set()
        self.searched_this_turn: set[str] = set()
        self.used_effect_tags: set[str] = set()
        self.turn_events: list[dict[str, Any]] = []

    def has_card(self, location: str, card_name: str) -> bool:
        return self._zone(location)[card_name] > 0

    def has_any(self, location: str, card_names: tuple[str, ...] | list[str]) -> bool:
        return any(self.has_card(location, card_name) for card_name in card_names)

    def move_card(self, from_location: str, to_location: str, card_name: str) -> bool:
        if not self.consume_card(from_location, card_name):
            return False
        self.add_card(to_location, card_name)
        self.movements.append(f"{card_name}: {from_location}->{to_location}")
        self.record_event("card_moved", card_name, {"from": from_location, "to": to_location})
        if to_location == "graveyard":
            self.sent_to_gy_this_turn.add(card_name)
            self.record_event("sent_to_gy", card_name, {"from": from_location})
        return True

    def add_card(self, location: str, card_name: str) -> None:
        self._zone(location)[self._key(card_name)] += 1

    def consume_card(self, location: str, card_name: str) -> bool:
        zone = self._zone(location)
        key = self._key(card_name)
        if zone[key] <= 0:
            return False
        zone[key] -= 1
        if zone[key] <= 0:
            del zone[key]
        return True

    def reveal_card(self, card_name_or_requirement: Any) -> bool:
        card = self._resolve_requirement("hand", card_name_or_requirement)
        if not card:
            return False
        self.movements.append(f"{card}: revealed from hand")
        self.record_event("revealed", card)
        return True

    def discard_card(self, card_name_or_requirement: Any) -> bool:
        card = self._resolve_requirement("hand", card_name_or_requirement)
        if not card:
            return False
        return self.move_card("hand", "graveyard", card)

    def banish_from_gy(self, card_name_or_requirement: Any) -> bool:
        return self.banish_matching(card_name_or_requirement, "graveyard")

    def banish_matching(self, card_name_or_requirement: Any, from_location: str = "graveyard") -> bool:
        card = self._resolve_requirement(from_location, card_name_or_requirement)
        if not card:
            return False
        return self.move_card(from_location, "banished", card)

    def send_matching_to_gy(self, card_name_or_requirement: Any, from_location: str = "hand") -> bool:
        card = self._resolve_requirement(from_location, card_name_or_requirement)
        if not card:
            return False
        return self.move_card(from_location, "graveyard", card)

    def control_card(self, requirement: Any) -> bool:
        return self.card_on_field(requirement)

    def card_in_gy(self, requirement: Any) -> bool:
        return self.has_matching_card("graveyard", requirement)

    def card_in_hand(self, requirement: Any) -> bool:
        return self.has_matching_card("hand", requirement)

    def card_in_deck(self, requirement: Any) -> bool:
        return self.has_matching_card("deck", requirement)

    def card_on_field(self, requirement: Any) -> bool:
        return self.has_matching_card("field", requirement)

    def find_cards(self, location: str, requirement: dict[str, Any] | str) -> list[Any]:
        cards = []
        for stored_card, count in self._zone(location).items():
            card_object = self.card_objects.get(stored_card, stored_card)
            for _ in range(count):
                if card_matches_requirement(card_object, requirement):
                    cards.append(stored_card)
        return cards

    def has_matching_card(self, location: str, requirement: dict[str, Any] | str) -> bool:
        return bool(self.find_cards(location, requirement))

    def consume_matching_card(self, location: str, requirement: dict[str, Any] | str) -> Any | None:
        matches = self.find_cards(location, requirement)
        if not matches:
            return None
        card = matches[0]
        return card if self.consume_card(location, card) else None

    def consume_materials(self, location: str, requirements: list[dict[str, Any] | str] | tuple[Any, ...]) -> list[Any] | None:
        consumed = []
        for requirement in requirements:
            card = self.consume_matching_card(location, requirement)
            if card is None:
                for previous in consumed:
                    self.add_card(location, previous)
                return None
            consumed.append(card)
        return consumed

    def count_matching(self, location: str, requirement: dict[str, Any] | str) -> int:
        return len(self.find_cards(location, requirement))

    def search_deck(self, card_name: str) -> bool:
        moved = self.move_card("deck", "hand", card_name)
        if moved:
            self.searched_this_turn.add(card_name)
            self.record_event("searched", card_name)
        return moved

    def send_to_gy(self, card_name: str, from_location: str = "hand") -> bool:
        return self.move_card(from_location, "graveyard", card_name)

    def summon_from_hand(self, card_name: str) -> bool:
        moved = self.move_card("hand", "field", card_name)
        if moved:
            self.summoned_this_turn.add(card_name)
            self.record_event("summoned", card_name, {"from": "hand"})
        return moved

    def summon_from_deck(self, card_name: str) -> bool:
        moved = self.move_card("deck", "field", card_name)
        if moved:
            self.summoned_this_turn.add(card_name)
            self.special_summoned_this_turn.add(card_name)
            self.record_event("special_summoned", card_name, {"from": "deck"})
        return moved

    def summon_from_extra(self, card_name: str) -> bool:
        moved = self.move_card("extra_deck", "field", card_name)
        if moved:
            self.summoned_this_turn.add(card_name)
            self.special_summoned_this_turn.add(card_name)
            self.record_event("special_summoned", card_name, {"from": "extra_deck"})
        return moved

    def can_normal_summon(self) -> bool:
        return not self.used_normal_summon

    def use_normal_summon(self) -> bool:
        if self.used_normal_summon:
            return False
        self.used_normal_summon = True
        return True

    def can_use_once_per_turn(self, tag: str) -> bool:
        return tag not in self.used_once_per_turn_tags

    def use_once_per_turn(self, tag: str) -> bool:
        if not self.can_use_once_per_turn(tag):
            return False
        self.used_once_per_turn_tags.add(tag)
        self.used_effect_tags.add(tag)
        self.record_event("effect_tag_used", tag)
        return True

    def apply_lock(self, lock_name: str) -> None:
        self.locks.add(lock_name)

    def record_event(self, event_type: str, card_name: str, metadata: dict[str, Any] | None = None) -> None:
        self.turn_events.append({"event_type": event_type, "card_name": card_name, "metadata": metadata or {}})
        if event_type == "activated":
            self.activated_cards_this_turn.add(card_name)
        elif event_type == "effect_resolved":
            self.resolved_effects_this_turn.add(card_name)
        elif event_type == "searched":
            self.searched_this_turn.add(card_name)
        elif event_type == "summoned":
            self.summoned_this_turn.add(card_name)
        elif event_type == "special_summoned":
            self.summoned_this_turn.add(card_name)
            self.special_summoned_this_turn.add(card_name)
        elif event_type == "sent_to_gy":
            self.sent_to_gy_this_turn.add(card_name)

    def was_summoned_this_turn(self, card_name: str) -> bool:
        return card_name in self.summoned_this_turn

    def was_special_summoned_this_turn(self, card_name: str) -> bool:
        return card_name in self.special_summoned_this_turn

    def was_sent_to_gy_this_turn(self, card_name: str) -> bool:
        return card_name in self.sent_to_gy_this_turn

    def was_activated_this_turn(self, card_name: str) -> bool:
        return card_name in self.activated_cards_this_turn

    def was_effect_resolved_this_turn(self, card_name: str) -> bool:
        return card_name in self.resolved_effects_this_turn

    def has_event(self, event_type: str, card_name: str | None = None) -> bool:
        return any(
            event["event_type"] == event_type and (card_name is None or event["card_name"] == card_name)
            for event in self.turn_events
        )

    def snapshot(self) -> dict[str, dict[str, int] | list[str] | bool]:
        return {
            "hand": dict(self.hand),
            "field": dict(self.field),
            "graveyard": dict(self.graveyard),
            "banished": dict(self.banished),
            "deck": dict(self.deck),
            "extra_deck": dict(self.extra_deck),
            "used_normal_summon": self.used_normal_summon,
            "used_once_per_turn_tags": sorted(self.used_once_per_turn_tags),
            "locks": sorted(self.locks),
            "movements": list(self.movements),
            "summoned_this_turn": sorted(self.summoned_this_turn),
            "special_summoned_this_turn": sorted(self.special_summoned_this_turn),
            "sent_to_gy_this_turn": sorted(self.sent_to_gy_this_turn),
            "activated_cards_this_turn": sorted(self.activated_cards_this_turn),
            "resolved_effects_this_turn": sorted(self.resolved_effects_this_turn),
            "searched_this_turn": sorted(self.searched_this_turn),
            "used_effect_tags": sorted(self.used_effect_tags),
            "turn_events": list(self.turn_events),
        }

    def _zone(self, location: str) -> Counter[str]:
        if location not in self.LOCATIONS:
            raise ValueError(f"Unknown resource location: {location}")
        return getattr(self, location)

    def _key(self, card: Any) -> Any:
        if isinstance(card, dict):
            name = get_card_name(card)
            if name:
                self.card_objects[name] = card
            return name
        return card

    def _counter(self, cards: list[Any]) -> Counter[str]:
        counter: Counter[str] = Counter()
        for card in cards:
            counter[self._key(card)] += 1
        return counter

    def _resolve_requirement(self, location: str, card_name_or_requirement: Any) -> str | None:
        if isinstance(card_name_or_requirement, str):
            return card_name_or_requirement if self.has_card(location, card_name_or_requirement) else None
        matches = self.find_cards(location, card_name_or_requirement)
        return matches[0] if matches else None
