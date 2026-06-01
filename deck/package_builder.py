from __future__ import annotations

import random
from collections import Counter
from typing import Any

from deck.packages import (
    PackageDefinition,
    card_name_lookup,
    engine_package,
    non_engine_packages,
    packages_for_archetype,
)
from SystemAIYugioh.banlist import get_card_limit

DEFAULT_ENGINE_VARIANTS = {
    "meta": "pure",
    "innovation": "chaos",
}

PACKAGE_QUOTAS = {
    "meta": {
        "core": 11,
        "starters": 10,
        "searchers": 4,
        "extenders": 5,
        "handtraps": 6,
        "board_breakers": 2,
        "traps": 2,
        "bricks": 4,
        "engine": 0,
        "extra_deck": 10,
    },
    "innovation": {
        "core": 10,
        "starters": 9,
        "searchers": 4,
        "extenders": 6,
        "handtraps": 4,
        "board_breakers": 4,
        "traps": 1,
        "bricks": 5,
        "engine": 3,
        "extra_deck": 10,
    },
}

VARIANT_QUOTA_ADJUSTMENTS = {
    "ritual": {"engine": 5, "bricks": 5, "board_breakers": 2},
    "chaos": {"engine": 3, "extenders": 7},
    "bystial": {"engine": 4, "handtraps": 5},
    "horus": {"engine": 4, "extenders": 6},
    "branded": {"engine": 4, "starters": 9},
    "handtrap_heavy": {"handtraps": 10, "board_breakers": 1, "traps": 1},
    "board_breaker_heavy": {"board_breakers": 6, "handtraps": 4, "traps": 0},
}

SAFEGUARDS = {
    "max_bricks": 6,
    "min_starters": 8,
    "min_interruptions": 8,
}


def build_package_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    size: int = 40,
    mode: str = "meta",
    engine_variant: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    variant = engine_variant or DEFAULT_ENGINE_VARIANTS.get(mode, "pure")
    lookup = card_name_lookup(cards)
    quotas = package_quotas(mode, variant)
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    violations: list[str] = []

    for package in ordered_packages(archetype, variant):
        quota = quotas.get(package.package_type, 0)
        if quota <= 0:
            continue
        before = len(selected)
        add_from_package(package, lookup, selected, counts, quota, mode)
        package_counts[package.package_type] += len(selected) - before

    fill_remaining(cards, archetype, selected, counts, package_counts, size, mode)
    selected = trim_to_size(selected, counts, size)
    violations.extend(safeguard_violations(selected, package_counts))

    metrics = package_metrics(selected, package_counts, variant, violations)
    if len(selected) < size:
        metrics["package_quota_violations"].append(f"deck below target size: {len(selected)}/{size}")
    return selected, metrics


def package_quotas(mode: str, engine_variant: str) -> dict[str, int]:
    quotas = dict(PACKAGE_QUOTAS.get(mode, PACKAGE_QUOTAS["meta"]))
    for key, value in VARIANT_QUOTA_ADJUSTMENTS.get(engine_variant, {}).items():
        quotas[key] = value
    if engine_variant == "pure":
        quotas["engine"] = 0
    return quotas


def ordered_packages(archetype: str, engine_variant: str) -> list[PackageDefinition]:
    archetype_packages = packages_for_archetype(archetype)
    by_type = {package.package_type: package for package in archetype_packages}
    packages: list[PackageDefinition] = []
    for package_type in ("core", "starters", "searchers", "extenders", "bricks", "traps", "extra_deck"):
        package = by_type.get(package_type)
        if package:
            packages.append(package)
    selected_engine = engine_package(engine_variant)
    if selected_engine:
        packages.append(selected_engine)
    packages.extend(non_engine_packages())
    return packages


def add_from_package(
    package: PackageDefinition,
    lookup: dict[str, dict[str, Any]],
    selected: list[dict[str, Any]],
    counts: Counter[str],
    quota: int,
    mode: str,
) -> None:
    candidates = [lookup[name] for name in package.card_names if name in lookup]
    if not candidates:
        return
    weights = [package_card_weight(card, mode) for card in candidates]
    attempts = quota * 80
    while count_package_cards(selected, package) < quota and attempts > 0:
        attempts -= 1
        card = random.choices(candidates, weights=weights, k=1)[0]
        name = str(card.get("name", ""))
        if counts[name] < get_card_limit(card):
            selected.append(card)
            counts[name] += 1


def fill_remaining(
    cards: list[dict[str, Any]],
    archetype: str,
    selected: list[dict[str, Any]],
    counts: Counter[str],
    package_counts: Counter[str],
    size: int,
    mode: str,
) -> None:
    candidates = [
        card
        for card in cards
        if card.get("archetype") and archetype.casefold() in str(card.get("archetype", "")).casefold()
    ]
    if not candidates:
        return
    weights = [package_card_weight(card, mode) for card in candidates]
    attempts = size * 100
    while len(selected) < size and attempts > 0:
        attempts -= 1
        card = random.choices(candidates, weights=weights, k=1)[0]
        name = str(card.get("name", ""))
        if counts[name] < get_card_limit(card):
            selected.append(card)
            counts[name] += 1
            package_counts[classify_card_package(card)] += 1


def trim_to_size(deck: list[dict[str, Any]], counts: Counter[str], size: int) -> list[dict[str, Any]]:
    if len(deck) <= size:
        return deck
    trimmed = list(deck)
    while len(trimmed) > size:
        removable_index = next(
            (
                index
                for index, card in enumerate(trimmed)
                if classify_card_package(card) in {"bricks", "extra_deck"}
            ),
            len(trimmed) - 1,
        )
        card = trimmed.pop(removable_index)
        counts[str(card.get("name", ""))] -= 1
    return trimmed


def package_metrics(
    deck: list[dict[str, Any]],
    package_counts: Counter[str],
    engine_variant: str,
    violations: list[str],
) -> dict[str, Any]:
    derived_counts = Counter(classify_card_package(card) for card in deck)
    package_counts.update({key: value for key, value in derived_counts.items() if package_counts[key] < value})
    return {
        "package_counts": dict(sorted(package_counts.items())),
        "chosen_engine_variant": engine_variant,
        "starter_count": derived_counts["starters"] + derived_counts["searchers"],
        "brick_count": derived_counts["bricks"],
        "non_engine_count": derived_counts["handtraps"] + derived_counts["board_breakers"] + derived_counts["traps"],
        "package_quota_violations": list(violations),
    }


def summarize_package_metrics(
    deck: list[dict[str, Any]],
    engine_variant: str = "pure",
    violations: list[str] | None = None,
) -> dict[str, Any]:
    package_counts: Counter[str] = Counter(classify_card_package(card) for card in deck)
    return package_metrics(deck, package_counts, engine_variant, violations or safeguard_violations(deck, package_counts))


def safeguard_violations(deck: list[dict[str, Any]], package_counts: Counter[str]) -> list[str]:
    violations = []
    derived = Counter(classify_card_package(card) for card in deck)
    starter_count = derived["starters"] + derived["searchers"]
    interruption_count = derived["handtraps"] + derived["traps"] + sum(1 for card in deck if is_interruption_text(card))

    if derived["bricks"] > SAFEGUARDS["max_bricks"]:
        violations.append(f"brick cap exceeded: {derived['bricks']}>{SAFEGUARDS['max_bricks']}")
    if starter_count < SAFEGUARDS["min_starters"]:
        violations.append(f"starter minimum missed: {starter_count}<{SAFEGUARDS['min_starters']}")
    if interruption_count < SAFEGUARDS["min_interruptions"]:
        violations.append(f"interruption minimum missed: {interruption_count}<{SAFEGUARDS['min_interruptions']}")

    card_counts = Counter(str(card.get("name", "")) for card in deck)
    for card in deck:
        name = str(card.get("name", ""))
        if card_counts[name] > get_card_limit(card):
            violations.append(f"copy limit exceeded: {name}")
    return sorted(set(violations))


def count_package_cards(deck: list[dict[str, Any]], package: PackageDefinition) -> int:
    package_names = set(package.card_names)
    return sum(1 for card in deck if str(card.get("name", "")) in package_names)


def classify_card_package(card: dict[str, Any]) -> str:
    name = str(card.get("name", "")).lower()
    text = f"{name} {card.get('type', '')} {card.get('desc', '')}".lower()
    level = safe_int(card.get("level"))
    card_type = str(card.get("type", "")).lower()

    if any(term in name for term in ("ash blossom", "effect veiler", "droll", "ghost", "nibiru", "d.d. crow", "infinite impermanence")):
        return "handtraps"
    if any(term in name for term in ("dark ruler", "evenly matched", "lightning storm", "raigeki", "harpie", "droplet", "kaiju", "book of eclipse")):
        return "board_breakers"
    if "trap" in card_type:
        return "traps"
    if any(extra in card_type for extra in ("fusion", "synchro", "xyz", "link")):
        return "extra_deck"
    if level >= 7 and "special summon" not in text and "ritual" not in card_type:
        return "bricks"
    if "bingo machine" in name or "sage with eyes" in name or "white stone" in name or "dictator of d" in name or "wishes for eyes" in name:
        return "starters"
    if "add" in text or "from your deck" in text or "search" in text:
        return "searchers"
    if "special summon" in text or "from your hand" in text or "from your graveyard" in text or "from your gy" in text:
        return "extenders"
    return "core"


def package_card_weight(card: dict[str, Any], mode: str) -> float:
    from deck.builder import (
        engine_card_weight,
        learned_card_weight,
        load_engine_profile,
        load_learned_profile,
        load_tuning_profile,
        tuning_card_weight,
    )

    archetype = str(card.get("archetype", "") or "Blue-Eyes")
    learned_profile = load_learned_profile(archetype, mode)
    tuning_profile = load_tuning_profile(archetype, mode)
    engine_profile = load_engine_profile(archetype, mode)
    return (
        learned_card_weight(str(card.get("name", "")), learned_profile)
        * tuning_card_weight(str(card.get("name", "")), tuning_profile)
        * engine_card_weight(card, engine_profile)
    )


def is_interruption_text(card: dict[str, Any]) -> bool:
    text = str(card.get("desc", "")).lower()
    return "negate" in text or "destroy" in text or "banish" in text or "shuffle" in text or "quick effect" in text


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
