from __future__ import annotations

from typing import Iterable


INTERACTION_CORE_REGISTRY: dict[str, tuple[str, ...]] = {
    "kashtira": (
        "Ash Blossom & Joyous Spring",
        "Ghost Belle & Haunted Mansion",
        "D.D. Crow",
        "Nibiru, the Primal Being",
    ),
}


def normalize_archetype(archetype: str | None) -> str:
    return str(archetype or "").strip().casefold()


def interaction_core_for(archetype: str | None) -> tuple[str, ...]:
    return INTERACTION_CORE_REGISTRY.get(normalize_archetype(archetype), ())


def interaction_core_set(archetype: str | None) -> set[str]:
    return set(interaction_core_for(archetype))


def is_interaction_core_card(archetype: str | None, card_name: str | None) -> bool:
    return str(card_name or "") in interaction_core_set(archetype)


def registry_report(archetypes: Iterable[str] | None = None) -> dict[str, object]:
    requested = list(archetypes or sorted(INTERACTION_CORE_REGISTRY))
    return {
        "report_only": True,
        "registry_owner": "deck.interaction_core_registry",
        "archetypes": {
            archetype: {
                "cards": list(interaction_core_for(archetype)),
                "card_count": len(interaction_core_for(archetype)),
            }
            for archetype in requested
        },
    }
