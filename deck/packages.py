from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PACKAGE_TYPES = (
    "core",
    "starters",
    "extenders",
    "searchers",
    "bricks",
    "handtraps",
    "board_breakers",
    "engine",
    "traps",
    "extra_deck",
)


@dataclass(frozen=True)
class PackageDefinition:
    name: str
    package_type: str
    card_names: tuple[str, ...]
    min_count: int = 0
    max_count: int = 40
    engine_variant: str | None = None


BLUE_EYES_PACKAGES: tuple[PackageDefinition, ...] = (
    PackageDefinition(
        name="Blue-Eyes core",
        package_type="core",
        card_names=(
            "Blue-Eyes White Dragon",
            "Blue-Eyes Alternative White Dragon",
            "Blue-Eyes Jet Dragon",
            "Dragon Spirit of White",
            "Blue-Eyes Abyss Dragon",
            "Blue-Eyes Solid Dragon",
        ),
        min_count=8,
        max_count=14,
    ),
    PackageDefinition(
        name="Blue-Eyes starters",
        package_type="starters",
        card_names=(
            "Sage with Eyes of Blue",
            "The White Stone of Ancients",
            "Dictator of D.",
            "Bingo Machine, Go!!!",
            "Wishes for Eyes of Blue",
            "Maiden with Eyes of Blue",
            "The White Stone of Legend",
        ),
        min_count=9,
        max_count=14,
    ),
    PackageDefinition(
        name="Blue-Eyes extenders",
        package_type="extenders",
        card_names=(
            "Blue-Eyes Jet Dragon",
            "Blue-Eyes Alternative White Dragon",
            "Blue-Eyes Abyss Dragon",
            "The White Stone of Ancients",
            "Dictator of D.",
        ),
        min_count=4,
        max_count=8,
    ),
    PackageDefinition(
        name="Blue-Eyes searchers",
        package_type="searchers",
        card_names=(
            "Bingo Machine, Go!!!",
            "Sage with Eyes of Blue",
            "Wishes for Eyes of Blue",
            "The Melody of Awakening Dragon",
        ),
        min_count=4,
        max_count=8,
    ),
    PackageDefinition(
        name="Blue-Eyes bricks",
        package_type="bricks",
        card_names=(
            "Blue-Eyes White Dragon",
            "Blue-Eyes Alternative White Dragon",
            "Blue-Eyes Jet Dragon",
            "Blue-Eyes Chaos MAX Dragon",
            "Deep-Eyes White Dragon",
            "Malefic Blue-Eyes White Dragon",
        ),
        min_count=3,
        max_count=6,
    ),
    PackageDefinition(
        name="Blue-Eyes traps",
        package_type="traps",
        card_names=(
            "True Light",
            "The Ultimate Creature of Destruction",
            "Destined Rivals",
        ),
        min_count=2,
        max_count=5,
    ),
    PackageDefinition(
        name="Blue-Eyes extra deck",
        package_type="extra_deck",
        card_names=(
            "Blue-Eyes Spirit Dragon",
            "Blue-Eyes Ultimate Spirit Dragon",
            "Blue-Eyes Tyrant Dragon",
            "Blue-Eyes Twin Burst Dragon",
            "Blue-Eyes Alternative Ultimate Dragon",
            "Neo Blue-Eyes Ultimate Dragon",
            "Blue-Eyes Ultimate Dragon",
            "Dragon Master Knight",
        ),
        min_count=6,
        max_count=12,
    ),
)


NON_ENGINE_PACKAGES: tuple[PackageDefinition, ...] = (
    PackageDefinition(
        name="Handtrap package",
        package_type="handtraps",
        card_names=(
            "Ash Blossom & Joyous Spring",
            "Effect Veiler",
            "Droll & Lock Bird",
            "Ghost Belle & Haunted Mansion",
            "Ghost Ogre & Snow Rabbit",
            "Nibiru, the Primal Being",
            "D.D. Crow",
            "Infinite Impermanence",
        ),
        min_count=4,
        max_count=12,
    ),
    PackageDefinition(
        name="Board breaker package",
        package_type="board_breakers",
        card_names=(
            "Dark Ruler No More",
            "Evenly Matched",
            "Lightning Storm",
            "Raigeki",
            "Harpie's Feather Duster",
            "Forbidden Droplet",
            "Book of Eclipse",
        ),
        min_count=2,
        max_count=8,
    ),
    PackageDefinition(
        name="Going-first trap package",
        package_type="traps",
        card_names=(
            "Infinite Impermanence",
            "Solemn Judgment",
            "Solemn Strike",
            "Dimensional Barrier",
            "Skill Drain",
        ),
        min_count=2,
        max_count=8,
    ),
)


ENGINE_PACKAGES: tuple[PackageDefinition, ...] = (
    PackageDefinition("Pure Blue-Eyes", "engine", (), engine_variant="pure", min_count=0, max_count=0),
    PackageDefinition(
        "Blue-Eyes ritual engine",
        "engine",
        ("Chaos Form", "Blue-Eyes Chaos MAX Dragon", "Blue-Eyes Chaos Dragon", "Advanced Ritual Art"),
        engine_variant="ritual",
        min_count=3,
        max_count=7,
    ),
    PackageDefinition(
        "Chaos engine",
        "engine",
        ("Chaos Dragon Levianeer", "Black Luster Soldier - Envoy of the Beginning", "The Chaos Creator"),
        engine_variant="chaos",
        min_count=2,
        max_count=5,
    ),
    PackageDefinition(
        "Bystial engine",
        "engine",
        ("Bystial Magnamhut", "Bystial Druiswurm", "The Bystial Lubellion", "Branded Regained"),
        engine_variant="bystial",
        min_count=3,
        max_count=6,
    ),
    PackageDefinition(
        "Horus engine",
        "engine",
        ("Imsety, Glory of Horus", "King's Sarcophagus", "Hapi, Guidance of Horus", "Duamutef, Blessing of Horus"),
        engine_variant="horus",
        min_count=3,
        max_count=6,
    ),
    PackageDefinition(
        "Branded engine",
        "engine",
        ("Branded Fusion", "Fallen of Albaz", "Aluber the Jester of Despia", "Branded Opening"),
        engine_variant="branded",
        min_count=3,
        max_count=7,
    ),
)


def packages_for_archetype(archetype: str) -> list[PackageDefinition]:
    if "blue-eyes" in archetype.casefold() or "blue eyes" in archetype.casefold():
        return list(BLUE_EYES_PACKAGES)
    return []


def non_engine_packages() -> list[PackageDefinition]:
    return list(NON_ENGINE_PACKAGES)


def engine_package(engine_variant: str) -> PackageDefinition | None:
    for package in ENGINE_PACKAGES:
        if package.engine_variant == engine_variant:
            return package
    return None


def card_name_lookup(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(card.get("name", "")): card for card in cards if card.get("name")}

