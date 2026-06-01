from __future__ import annotations

from typing import Any

from deck.archetype_role_inference import infer_archetype_roles
from deck.packages import PackageDefinition


def extract_generic_packages(cards: list[dict[str, Any]], archetype: str) -> dict[str, Any]:
    analysis = infer_archetype_roles(cards, archetype)
    roles = analysis["roles"]
    packages = [
        build_package(archetype, "core", roles.get("engine_requirement", []) + roles.get("payoff", []), 6, 16),
        build_package(archetype, "starters", roles.get("starter", []), 6, 14),
        build_package(archetype, "searchers", roles.get("searcher", []), 3, 10),
        build_package(archetype, "extenders", roles.get("extender", []), 3, 10),
        build_package(archetype, "bricks", roles.get("garnet_brick", []), 0, 6),
        build_package(archetype, "engine", roles.get("engine_requirement", []), 3, 12),
        build_package(archetype, "traps", [name for name in roles.get("interruption", []) if "trap" in card_type_lookup(cards).get(name, "")], 0, 8),
    ]
    non_engine = sorted(set(roles.get("interruption", []) + roles.get("board_breaker", [])))
    side_candidates = sorted(set(roles.get("board_breaker", []) + roles.get("recovery", []) + roles.get("interruption", [])))
    return {
        "archetype": archetype,
        "source": "generic_inference",
        "role_counts": analysis["role_counts"],
        "packages": [package_to_dict(package) for package in packages if package.card_names],
        "non_engine_candidates": non_engine,
        "side_package_candidates": side_candidates[:30],
        "analysis": analysis,
    }


def build_package(archetype: str, package_type: str, card_names: list[str], min_count: int, max_count: int) -> PackageDefinition:
    unique = tuple(sorted(set(card_names)))
    return PackageDefinition(
        name=f"{archetype} generic {package_type}",
        package_type=package_type,
        card_names=unique,
        min_count=min(min_count, len(unique)),
        max_count=max_count,
    )


def package_to_dict(package: PackageDefinition) -> dict[str, Any]:
    return {
        "name": package.name,
        "package_type": package.package_type,
        "card_names": list(package.card_names),
        "min_count": package.min_count,
        "max_count": package.max_count,
        "engine_variant": package.engine_variant,
    }


def card_type_lookup(cards: list[dict[str, Any]]) -> dict[str, str]:
    return {str(card.get("name", "")): str(card.get("type", "")).casefold() for card in cards}
