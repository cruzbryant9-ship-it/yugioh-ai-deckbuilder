from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from data.card_limits import cleanup_learned_card_stats
from deck.hand_simulator import real_combo_report
from deck.matchup_engine_stats import load_matchup_engine_stats, matchup_engine_weight, recommended_variant_with_curated_memory
from SystemAIYugioh.banlist import get_card_limit
from SystemAIYugioh.json_utils import safe_load_json

EXTRA_DECK_TYPES = ("fusion", "synchro", "xyz", "link")
LEARNED_CARD_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learned_card_stats.json"
LEARNING_TUNING_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learning_tuning.json"
LEARNED_ENGINE_STATS_PATH = Path("SystemAIYugioh") / "data" / "deck_profiles" / "learned_engine_stats.json"
ENGINE_WEIGHT_CAP = 0.10
LAST_BUILD_REPORT: dict[str, Any] = {}

ENGINE_DEFINITIONS = {
    "Blue-Eyes core": {
        "name_terms": ("blue-eyes", "eyes of blue", "white stone", "dictator of d", "bingo machine", "true light"),
        "text_terms": (),
    },
    "Blue-Eyes ritual": {
        "name_terms": ("chaos max", "blue-eyes chaos", "chaos form", "advanced ritual art", "ultimate creature"),
        "text_terms": ("ritual summon", "ritual monster"),
    },
    "Bystial": {
        "name_terms": ("bystial", "lubellion", "branded regained", "branded beast"),
        "text_terms": (),
    },
    "Horus": {
        "name_terms": ("horus", "king's sarcophagus", "imsety", "duamutef", "hapi", "qebehsenuef"),
        "text_terms": ("king's sarcophagus",),
    },
    "Branded": {
        "name_terms": ("branded", "albaz", "despia", "fallen of albaz", "cartesia", "quem"),
        "text_terms": ("fallen of albaz",),
    },
    "Chaos": {
        "name_terms": ("chaos", "black luster soldier", "levianeer", "lightpulsar", "darkflare"),
        "text_terms": ("light and dark", "light or dark", "banish 1 light"),
    },
    "handtrap package": {
        "name_terms": ("ash blossom", "effect veiler", "droll", "ghost belle", "ghost ogre", "nibiru", "d.d. crow", "infinite impermanence"),
        "text_terms": (),
    },
    "board breaker package": {
        "name_terms": ("dark ruler no more", "evenly matched", "lightning storm", "raigeki", "harpie's feather duster", "forbidden droplet", "kaiju", "book of eclipse"),
        "text_terms": (),
    },
}


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    card_type = str(card.get("type", "")).lower()
    return any(extra_type in card_type for extra_type in EXTRA_DECK_TYPES)


def build_deck(
    cards: list[dict[str, Any]],
    archetype_name: str,
    size: int = 40,
    mode: str = "meta",
    use_learning: bool = True,
    engine_variant: str | None = None,
    matchup: Any = None,
    going: str | None = None,
    generic_tune_runs: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matchup_profile = load_matchup_engine_stats(archetype_name, mode) if use_learning and matchup else {}
    matchup_variant = engine_variant or recommended_variant_with_curated_memory(archetype_name, mode, matchup_profile, matchup, going)
    authored_available = False
    try:
        from deck.packages import packages_for_archetype

        authored_available = bool(packages_for_archetype(archetype_name))
    except Exception:
        authored_available = False
    if use_learning:
        try:
            from deck.package_builder import build_package_deck

            if authored_available:
                package_deck, package_metrics = build_package_deck(
                    cards,
                    archetype_name,
                    size=size,
                    mode=mode,
                    engine_variant=matchup_variant,
                )
                if len(package_deck) >= size and not any(
                    "copy limit exceeded" in violation
                    for violation in package_metrics.get("package_quota_violations", [])
                ):
                    archetype_pool = [
                        card
                        for card in cards
                        if card.get("archetype") and archetype_name.lower() in card.get("archetype", "").lower()
                    ]
                    set_last_build_report(
                        {
                            "builder_used": "authored",
                            "chosen_engine_variant": package_metrics.get("chosen_engine_variant", matchup_variant),
                            "package_counts": package_metrics.get("package_counts", {}),
                            "quota_warnings": package_metrics.get("package_quota_violations", []),
                            "generic_confidence_score": None,
                        }
                    )
                    return package_deck[:size], archetype_pool
        except Exception:
            pass

    generic_deck, generic_pool, generic_report = try_generic_deck(cards, archetype_name, mode, matchup_variant, size, generic_tune_runs)
    if generic_deck:
        set_last_build_report(generic_report)
        return generic_deck, generic_pool

    archetype_cards = [
        card
        for card in cards
        if card.get("archetype") and archetype_name.lower() in card.get("archetype", "").lower()
    ]

    if not archetype_cards:
        set_last_build_report({"builder_used": "none", "generic_confidence_score": 0.0, "package_counts": {}, "quota_warnings": ["no archetype cards found"]})
        return [], archetype_cards

    deck = []
    card_counts = Counter()
    attempts = 0
    max_attempts = size * 100
    learned_profile = load_learned_profile(archetype_name, mode) if use_learning else {}
    tuning_profile = load_tuning_profile(archetype_name, mode) if use_learning else {}
    engine_profile = load_engine_profile(archetype_name, mode) if use_learning else {}
    card_weights = [
        learned_card_weight(card.get("name", ""), learned_profile)
        * tuning_card_weight(card.get("name", ""), tuning_profile)
        * engine_card_weight(card, engine_profile)
        * matchup_engine_weight(detect_card_engines(card), matchup_variant)
        for card in archetype_cards
    ]

    while len(deck) < size and attempts < max_attempts:
        attempts += 1
        card = random.choices(archetype_cards, weights=card_weights, k=1)[0]
        limit = get_card_limit(card)
        if limit > 0 and card_counts[card["name"]] < limit:
            deck.append(card)
            card_counts[card["name"]] += 1

    set_last_build_report({"builder_used": "weighted_random", "generic_confidence_score": None, "package_counts": {}, "quota_warnings": []})
    return deck, archetype_cards


def try_generic_deck(
    cards: list[dict[str, Any]],
    archetype_name: str,
    mode: str,
    engine_hint: str | None,
    size: int,
    generic_tune_runs: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    try:
        from deck.archetype_role_inference import archetype_pool
        from deck.generic_deck_builder import build_generic_deck
        from deck.generic_tuner import tune_generic_deck

        if generic_tune_runs > 0:
            tuning_report = tune_generic_deck(archetype_name, cards, mode=mode, runs=generic_tune_runs)
            generic_deck = tuning_report.get("best_deck", [])
            main_deck = [card for card in generic_deck if not is_extra_deck_card(card)]
            extra_deck = [card for card in generic_deck if is_extra_deck_card(card)]
            report = {
                "builder_used": "generic_tuned",
                "generic_confidence_score": tuning_report.get("best_result", {}).get("confidence", 0),
                "main_deck_count": len(main_deck),
                "extra_deck_count": len(extra_deck),
                "package_counts": tuning_report.get("best_result", {}).get("package_counts", {}),
                "quota_warnings": tuning_report.get("best_result", {}).get("quota_warnings", []),
                "generic_tuning": {
                    "runs": tuning_report.get("runs", 0),
                    "best_score": tuning_report.get("best_score", 0),
                    "average_score": tuning_report.get("average_score", 0),
                    "memory_updated": tuning_report.get("memory_updated", False),
                },
            }
        else:
            generic_deck, report = build_generic_deck(archetype_name, cards, mode=mode, engine_hint=engine_hint)
        pool = archetype_pool(cards, archetype_name)
        main_count = int(report.get("main_deck_count", 0) or 0)
        hard_warnings = [
            warning
            for warning in report.get("quota_warnings", [])
            if "copy limit exceeded" in warning or "blocked card selected" in warning
        ]
        if main_count >= size and not hard_warnings:
            return generic_deck, pool, report
    except Exception:
        return [], [], {"builder_used": "generic_failed", "generic_confidence_score": 0.0, "package_counts": {}, "quota_warnings": ["generic builder failed"]}
    return [], [], report if "report" in locals() else {"builder_used": "generic_failed", "generic_confidence_score": 0.0, "package_counts": {}, "quota_warnings": ["generic builder failed"]}


def set_last_build_report(report: dict[str, Any]) -> None:
    LAST_BUILD_REPORT.clear()
    LAST_BUILD_REPORT.update(report)


def get_last_build_report() -> dict[str, Any]:
    return dict(LAST_BUILD_REPORT)


def load_learned_profile(archetype_name: str, mode: str) -> dict[str, Any]:
    cleanup_learned_card_stats(LEARNED_CARD_STATS_PATH)

    if not LEARNED_CARD_STATS_PATH.exists():
        return {}

    learned_stats = safe_load_json(LEARNED_CARD_STATS_PATH, {})

    profiles = learned_stats.get("profiles")
    if not isinstance(profiles, dict):
        return {}

    archetype_profiles = profiles.get(archetype_name.casefold())
    if not isinstance(archetype_profiles, dict):
        return {}

    profile = archetype_profiles.get(mode)
    return profile if isinstance(profile, dict) else {}


def learned_card_weight(card_name: str, learned_profile: dict[str, Any]) -> float:
    if not learned_profile:
        return 1.0

    top_cards = learned_profile.get("cards_appearing_in_top_10_percent_decks", {})
    avoid_cards = learned_profile.get("cards_appearing_often_in_bottom_25_percent_decks", {})
    avg_scores = learned_profile.get("card_average_score_when_included", {})
    average_score = float(learned_profile.get("average_score", 0) or 0)
    total_runs = max(1, int(learned_profile.get("total_runs", 1) or 1))

    top_hits = _safe_numeric_lookup(top_cards, card_name)
    avoid_hits = _safe_numeric_lookup(avoid_cards, card_name)
    card_avg_score = _safe_numeric_lookup(avg_scores, card_name)

    weight = 1.0
    weight += min(0.18, (top_hits / total_runs) * 0.4)
    weight -= min(0.18, (avoid_hits / total_runs) * 0.4)

    if average_score and card_avg_score:
        score_delta = (card_avg_score - average_score) / max(abs(average_score), 1)
        weight += max(-0.08, min(0.08, score_delta * 0.25))

    return max(0.75, min(1.25, weight))


def load_tuning_profile(archetype_name: str, mode: str) -> dict[str, Any]:
    if not LEARNING_TUNING_PATH.exists():
        return {}

    tuning_stats = safe_load_json(LEARNING_TUNING_PATH, {})

    profiles = tuning_stats.get("profiles")
    if not isinstance(profiles, dict):
        return {}

    archetype_profiles = profiles.get(archetype_name.casefold())
    if not isinstance(archetype_profiles, dict):
        return {}

    profile = archetype_profiles.get(mode)
    return profile if isinstance(profile, dict) else {}


def tuning_card_weight(card_name: str, tuning_profile: dict[str, Any]) -> float:
    if not tuning_profile:
        return 1.0

    adjustments = tuning_profile.get("card_adjustments", {})
    adjustment = _safe_numeric_lookup(adjustments, card_name)
    return max(0.88, min(1.12, 1.0 + adjustment))


def load_engine_profile(archetype_name: str, mode: str) -> dict[str, Any]:
    if not LEARNED_ENGINE_STATS_PATH.exists():
        return {}

    engine_stats = safe_load_json(LEARNED_ENGINE_STATS_PATH, {})

    profiles = engine_stats.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    archetype_profiles = profiles.get(archetype_name.casefold())
    if not isinstance(archetype_profiles, dict):
        return {}
    profile = archetype_profiles.get(mode)
    return profile if isinstance(profile, dict) else {}


def engine_card_weight(card: dict[str, Any], engine_profile: dict[str, Any]) -> float:
    if not engine_profile:
        return 1.0

    adjustments = engine_profile.get("engine_adjustments", {})
    if not isinstance(adjustments, dict):
        return 1.0

    engine_names = detect_card_engines(card)
    if not engine_names:
        return 1.0

    adjustment = sum(_safe_numeric_lookup(adjustments, engine) for engine in engine_names)
    return max(1.0 - ENGINE_WEIGHT_CAP, min(1.0 + ENGINE_WEIGHT_CAP, 1.0 + adjustment))


def detect_card_engines(card: dict[str, Any]) -> set[str]:
    name = str(card.get("name", "")).lower()
    text = f"{name} {card.get('archetype', '')} {card.get('type', '')} {card.get('desc', '')}".lower()
    engines = set()

    for engine, patterns in ENGINE_DEFINITIONS.items():
        name_terms = patterns.get("name_terms", ())
        text_terms = patterns.get("text_terms", ())
        if any(term in name for term in name_terms) or any(term in text for term in text_terms):
            engines.add(engine)

    return engines


def detect_deck_engines(deck: list[dict[str, Any]]) -> dict[str, list[str]]:
    engines: dict[str, set[str]] = {}
    for card in deck:
        for engine in detect_card_engines(card):
            engines.setdefault(engine, set()).add(str(card.get("name", "")))
    return {engine: sorted(cards) for engine, cards in sorted(engines.items())}


def card_role_flags(card: dict[str, Any]) -> set[str]:
    text = str(card.get("desc", "")).lower()
    card_type = str(card.get("type", "")).lower()
    level = _safe_int(card.get("level"))
    roles = set()

    if (
        "normal summon" in text
        or "add 1" in text
        or "search" in text
        or "from your deck" in text
        or (level <= 4 and "monster" in card_type and not is_extra_deck_card(card))
    ):
        roles.add("starter")
    if (
        "special summon" in text
        or "summon this card" in text
        or "from your hand" in text
        or "from your graveyard" in text
        or "from your gy" in text
    ):
        roles.add("extender")
    if (
        "negate" in text
        or "destroy" in text
        or "banish" in text
        or "shuffle" in text
        or "quick effect" in text
        or "trap" in card_type
    ):
        roles.add("interruption")
    if is_extra_deck_card(card) or "cannot be destroyed" in text or "unaffected" in text or "negate" in text:
        roles.add("endboard")
    if level >= 7 and "special summon" not in text and "ritual" not in card_type and not is_extra_deck_card(card):
        roles.add("brick")

    return roles


def _safe_numeric_lookup(values: Any, card_name: str) -> float:
    if not isinstance(values, dict):
        return 0.0
    value = values.get(card_name)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def simulate_hand_score(hand: list[dict[str, Any]]) -> int:
    score = 0
    names = {card.get("name", "") for card in hand}

    for card in hand:
        text = str(card.get("desc", "")).lower()
        if "draw" in text or "add" in text:
            score += 2
        if "special summon" in text:
            score += 2
        if "negate" in text:
            score += 3
        if is_extra_deck_card(card):
            score += 1

    if len(names) < len(hand):
        score -= 1

    return score


def score_deck_breakdown(deck: list[dict[str, Any]], archetype: str, mode: str) -> dict[str, float]:
    if not deck:
        return {
            "consistency_score": 0.0,
            "starter_score": 0.0,
            "extender_score": 0.0,
            "interruption_score": 0.0,
            "brick_penalty": 0.0,
            "endboard_score": 0.0,
            "learned_card_bonus": 0.0,
            "final_score": 0.0,
        }

    card_counts = Counter(card.get("name", "") for card in deck)
    main_deck = [card for card in deck if not is_extra_deck_card(card)]
    extra_deck = [card for card in deck if is_extra_deck_card(card)]
    texts = [str(card.get("desc", "")).lower() for card in deck]
    learned_profile = load_learned_profile(archetype, mode)
    package_quality = {}

    consistency_score = _consistency_score(deck, texts, archetype)
    starter_score = _starter_score(deck, texts)
    extender_score = _extender_score(texts)
    interruption_score = _interruption_score(deck, texts)
    brick_penalty = _brick_penalty(deck, main_deck, extra_deck, card_counts)
    endboard_score = _endboard_score(extra_deck, texts)
    learned_card_bonus = _learned_card_bonus(deck, learned_profile)
    gameplay_report = real_combo_report(deck, archetype, samples=40) if archetype else {}
    playable_hand_rate = float(gameplay_report.get("playable_hand_rate", 0.0) or 0.0)
    brick_rate = float(gameplay_report.get("brick_rate", 0.0) or 0.0)
    combo_line_score = float(gameplay_report.get("combo_line_score", 0.0) or 0.0)
    interruption_resilience_score = float(gameplay_report.get("interruption_resilience_score", 0.0) or 0.0)
    follow_up_score = float(gameplay_report.get("follow_up_score", 0.0) or 0.0)
    normal_summon_conflict_rate = float(gameplay_report.get("normal_summon_conflict_rate", 0.0) or 0.0)
    once_per_turn_conflict_rate = float(gameplay_report.get("once_per_turn_conflict_rate", 0.0) or 0.0)
    dead_duplicate_rate = float(gameplay_report.get("dead_duplicate_rate", 0.0) or 0.0)
    payoff_without_enabler_rate = float(gameplay_report.get("payoff_without_enabler_rate", 0.0) or 0.0)
    enabler_without_payoff_rate = float(gameplay_report.get("enabler_without_payoff_rate", 0.0) or 0.0)
    best_line_average_score = float(gameplay_report.get("best_line_average_score", 0.0) or 0.0)
    graph_valid_line_rate = float(gameplay_report.get("graph_valid_line_rate", 0.0) or 0.0)
    graph_average_line_score = float(gameplay_report.get("graph_average_line_score", 0.0) or 0.0)
    graph_average_payoff_score = float(gameplay_report.get("graph_average_payoff_score", 0.0) or 0.0)
    graph_average_resource_score = float(gameplay_report.get("graph_average_resource_score", 0.0) or 0.0)
    graph_average_risk_score = float(gameplay_report.get("graph_average_risk_score", 0.0) or 0.0)
    graph_failed_line_rate = float(gameplay_report.get("graph_failed_line_rate", 0.0) or 0.0)
    optional_line_failure_rate = float(gameplay_report.get("optional_line_failure_rate", 0.0) or 0.0)
    best_line_failure_rate = float(gameplay_report.get("best_line_failure_rate", 0.0) or 0.0)
    no_valid_line_rate = float(gameplay_report.get("no_valid_line_rate", 0.0) or 0.0)
    branch_valid_rate = float(gameplay_report.get("branch_valid_rate", 0.0) or 0.0)
    no_valid_branch_rate = float(gameplay_report.get("no_valid_branch_rate", 0.0) or 0.0)
    average_branch_score = float(gameplay_report.get("average_branch_score", 0.0) or 0.0)
    interruption_window_count = float(gameplay_report.get("interruption_window_count", 0.0) or 0.0)
    average_interruption_risk = float(gameplay_report.get("average_interruption_risk", 0.0) or 0.0)
    ash_vulnerability_rate = float(gameplay_report.get("ash_vulnerability_rate", 0.0) or 0.0)
    imperm_vulnerability_rate = float(gameplay_report.get("imperm_vulnerability_rate", 0.0) or 0.0)
    veiler_vulnerability_rate = float(gameplay_report.get("veiler_vulnerability_rate", 0.0) or 0.0)
    droll_vulnerability_rate = float(gameplay_report.get("droll_vulnerability_rate", 0.0) or 0.0)
    crow_vulnerability_rate = float(gameplay_report.get("crow_vulnerability_rate", 0.0) or 0.0)
    nibiru_vulnerability_rate = float(gameplay_report.get("nibiru_vulnerability_rate", 0.0) or 0.0)
    recovery_route_rate = float(gameplay_report.get("recovery_route_rate", 0.0) or 0.0)
    interrupted_line_success_rate = float(gameplay_report.get("interrupted_line_success_rate", 0.0) or 0.0)
    resilience_score = float(gameplay_report.get("resilience_score", 0.0) or 0.0)
    resource_valid_line_rate = float(gameplay_report.get("resource_valid_line_rate", 0.0) or 0.0)
    material_failure_rate = float(gameplay_report.get("missing_material_rate", 0.0) or 0.0)
    search_failure_rate = float(gameplay_report.get("missing_search_target_rate", 0.0) or 0.0)
    extra_deck_failure_rate = float(gameplay_report.get("missing_extra_deck_rate", 0.0) or 0.0)
    cost_failure_rate = float(gameplay_report.get("cost_failure_rate", 0.0) or 0.0)
    normalized_search_failure_rate = float(gameplay_report.get("normalized_search_failure_rate", 0.0) or 0.0)
    normalized_cost_failure_rate = float(gameplay_report.get("normalized_cost_failure_rate", 0.0) or 0.0)
    normalized_material_failure_rate = float(gameplay_report.get("normalized_material_failure_rate", 0.0) or 0.0)
    normalized_extra_deck_failure_rate = float(gameplay_report.get("normalized_extra_deck_failure_rate", 0.0) or 0.0)
    cost_condition_valid_rate = float(gameplay_report.get("cost_condition_valid_rate", 0.0) or 0.0)
    cost_failure_rate_normalized = float(gameplay_report.get("cost_failure_rate_normalized", 0.0) or 0.0)
    condition_failure_rate_normalized = float(gameplay_report.get("condition_failure_rate_normalized", 0.0) or 0.0)
    reveal_cost_failure_rate = float(gameplay_report.get("reveal_cost_failure_rate", 0.0) or 0.0)
    discard_cost_failure_rate = float(gameplay_report.get("discard_cost_failure_rate", 0.0) or 0.0)
    gy_condition_failure_rate = float(gameplay_report.get("gy_condition_failure_rate", 0.0) or 0.0)
    control_condition_failure_rate = float(gameplay_report.get("control_condition_failure_rate", 0.0) or 0.0)
    history_condition_failure_rate = float(gameplay_report.get("history_condition_failure_rate", 0.0) or 0.0)
    summon_history_failure_rate = float(gameplay_report.get("summon_history_failure_rate", 0.0) or 0.0)
    gy_history_failure_rate = float(gameplay_report.get("gy_history_failure_rate", 0.0) or 0.0)
    activation_history_failure_rate = float(gameplay_report.get("activation_history_failure_rate", 0.0) or 0.0)
    resolution_history_failure_rate = float(gameplay_report.get("resolution_history_failure_rate", 0.0) or 0.0)
    typed_material_valid_rate = float(gameplay_report.get("typed_material_valid_rate", 0.0) or 0.0)
    synchro_material_failure_rate = float(gameplay_report.get("synchro_material_failure_rate", 0.0) or 0.0)
    fusion_material_failure_rate = float(gameplay_report.get("fusion_material_failure_rate", 0.0) or 0.0)
    ritual_material_failure_rate = float(gameplay_report.get("ritual_material_failure_rate", 0.0) or 0.0)
    link_material_failure_rate = float(gameplay_report.get("link_material_failure_rate", 0.0) or 0.0)
    named_material_failure_rate = float(gameplay_report.get("named_material_failure_rate", 0.0) or 0.0)
    synchro_exact_level_valid_rate = float(gameplay_report.get("synchro_exact_level_valid_rate", 0.0) or 0.0)
    synchro_level_failure_rate = float(gameplay_report.get("synchro_level_failure_rate", 0.0) or 0.0)
    ritual_level_valid_rate = float(gameplay_report.get("ritual_level_valid_rate", 0.0) or 0.0)
    ritual_level_failure_rate = float(gameplay_report.get("ritual_level_failure_rate", 0.0) or 0.0)
    xyz_material_valid_rate = float(gameplay_report.get("xyz_material_valid_rate", 0.0) or 0.0)
    link_material_valid_rate = float(gameplay_report.get("link_material_valid_rate", 0.0) or 0.0)

    if mode == "innovation":
        unique_ratio = len(card_counts) / len(deck)
        learned_card_bonus *= 0.75
        extender_score += unique_ratio * 4
    elif mode == "meta":
        consistency_score += sum(0.6 for count in card_counts.values() if count >= 2)

    final_score = (
        consistency_score
        + starter_score
        + extender_score
        + interruption_score
        + endboard_score
        + learned_card_bonus
        + playable_hand_rate * 12.0
        + combo_line_score * 1.2
        + interruption_resilience_score * 0.8
        + follow_up_score * 0.7
        + best_line_average_score * 0.8
        + graph_valid_line_rate * 8.0
        + resource_valid_line_rate * 6.0
        + typed_material_valid_rate * 4.0
        + cost_condition_valid_rate * 3.0
        + branch_valid_rate * 2.0
        + average_branch_score * 0.3
        + interrupted_line_success_rate * 6.0
        + resilience_score * 0.8
        + recovery_route_rate * 2.0
        + synchro_exact_level_valid_rate * 1.5
        + ritual_level_valid_rate * 1.0
        + graph_average_line_score * 0.8
        + graph_average_payoff_score * 0.6
        + graph_average_resource_score * 0.2
        - brick_penalty
        - brick_rate * 10.0
        - normal_summon_conflict_rate * 5.0
        - once_per_turn_conflict_rate * 4.0
        - dead_duplicate_rate * 3.0
        - payoff_without_enabler_rate * 5.0
        - enabler_without_payoff_rate * 3.0
        - best_line_failure_rate * 5.0
        - no_valid_line_rate * 4.0
        - no_valid_branch_rate * 4.0
        - average_interruption_risk * 0.8
        - ash_vulnerability_rate * 2.0
        - imperm_vulnerability_rate * 1.5
        - droll_vulnerability_rate * 1.5
        - optional_line_failure_rate * 0.5
        - graph_average_risk_score * 0.5
        - normalized_material_failure_rate * 4.0
        - normalized_search_failure_rate * 3.0
        - normalized_extra_deck_failure_rate * 4.0
        - normalized_cost_failure_rate * 3.0
        - condition_failure_rate_normalized * 3.0
        - reveal_cost_failure_rate * 2.0
        - discard_cost_failure_rate * 2.0
        - gy_condition_failure_rate * 2.0
        - control_condition_failure_rate * 2.0
        - history_condition_failure_rate * 3.0
        - summon_history_failure_rate * 2.0
        - gy_history_failure_rate * 2.0
        - activation_history_failure_rate * 2.0
        - resolution_history_failure_rate * 2.0
        - synchro_material_failure_rate * 3.0
        - fusion_material_failure_rate * 3.0
        - ritual_material_failure_rate * 3.0
        - link_material_failure_rate * 2.0
        - named_material_failure_rate * 3.0
        - synchro_level_failure_rate * 3.0
        - ritual_level_failure_rate * 3.0
    )

    breakdown = {
        "consistency_score": round(consistency_score, 2),
        "starter_score": round(starter_score, 2),
        "extender_score": round(extender_score, 2),
        "interruption_score": round(interruption_score, 2),
        "brick_penalty": round(brick_penalty, 2),
        "endboard_score": round(endboard_score, 2),
        "learned_card_bonus": round(learned_card_bonus, 2),
        "playable_hand_rate": round(playable_hand_rate, 4),
        "brick_rate": round(brick_rate, 4),
        "combo_line_score": round(combo_line_score, 2),
        "interruption_resilience_score": round(interruption_resilience_score, 2),
        "follow_up_score": round(follow_up_score, 2),
        "normal_summon_conflict_rate": round(normal_summon_conflict_rate, 4),
        "once_per_turn_conflict_rate": round(once_per_turn_conflict_rate, 4),
        "dead_duplicate_rate": round(dead_duplicate_rate, 4),
        "payoff_without_enabler_rate": round(payoff_without_enabler_rate, 4),
        "enabler_without_payoff_rate": round(enabler_without_payoff_rate, 4),
        "best_line_average_score": round(best_line_average_score, 2),
        "graph_valid_line_rate": round(graph_valid_line_rate, 4),
        "graph_average_line_score": round(graph_average_line_score, 2),
        "graph_average_payoff_score": round(graph_average_payoff_score, 2),
        "graph_average_resource_score": round(graph_average_resource_score, 2),
        "graph_average_risk_score": round(graph_average_risk_score, 2),
        "graph_failed_line_rate": round(graph_failed_line_rate, 4),
        "optional_line_failure_rate": round(optional_line_failure_rate, 4),
        "best_line_failure_rate": round(best_line_failure_rate, 4),
        "no_valid_line_rate": round(no_valid_line_rate, 4),
        "branch_valid_rate": round(branch_valid_rate, 4),
        "no_valid_branch_rate": round(no_valid_branch_rate, 4),
        "average_branch_score": round(average_branch_score, 2),
        "interruption_window_count": round(interruption_window_count, 2),
        "average_interruption_risk": round(average_interruption_risk, 2),
        "ash_vulnerability_rate": round(ash_vulnerability_rate, 4),
        "imperm_vulnerability_rate": round(imperm_vulnerability_rate, 4),
        "veiler_vulnerability_rate": round(veiler_vulnerability_rate, 4),
        "droll_vulnerability_rate": round(droll_vulnerability_rate, 4),
        "crow_vulnerability_rate": round(crow_vulnerability_rate, 4),
        "nibiru_vulnerability_rate": round(nibiru_vulnerability_rate, 4),
        "recovery_route_rate": round(recovery_route_rate, 4),
        "interrupted_line_success_rate": round(interrupted_line_success_rate, 4),
        "resilience_score": round(resilience_score, 2),
        "most_common_graph_failure_reason": gameplay_report.get("most_common_graph_failure_reason"),
        "resource_valid_line_rate": round(resource_valid_line_rate, 4),
        "material_failure_rate": round(material_failure_rate, 4),
        "search_failure_rate": round(search_failure_rate, 4),
        "extra_deck_failure_rate": round(extra_deck_failure_rate, 4),
        "cost_failure_rate": round(cost_failure_rate, 4),
        "normalized_search_failure_rate": round(normalized_search_failure_rate, 4),
        "normalized_cost_failure_rate": round(normalized_cost_failure_rate, 4),
        "normalized_material_failure_rate": round(normalized_material_failure_rate, 4),
        "normalized_extra_deck_failure_rate": round(normalized_extra_deck_failure_rate, 4),
        "cost_condition_valid_rate": round(cost_condition_valid_rate, 4),
        "cost_failure_rate_normalized": round(cost_failure_rate_normalized, 4),
        "condition_failure_rate_normalized": round(condition_failure_rate_normalized, 4),
        "reveal_cost_failure_rate": round(reveal_cost_failure_rate, 4),
        "discard_cost_failure_rate": round(discard_cost_failure_rate, 4),
        "gy_condition_failure_rate": round(gy_condition_failure_rate, 4),
        "control_condition_failure_rate": round(control_condition_failure_rate, 4),
        "history_condition_failure_rate": round(history_condition_failure_rate, 4),
        "summon_history_failure_rate": round(summon_history_failure_rate, 4),
        "gy_history_failure_rate": round(gy_history_failure_rate, 4),
        "activation_history_failure_rate": round(activation_history_failure_rate, 4),
        "resolution_history_failure_rate": round(resolution_history_failure_rate, 4),
        "typed_material_valid_rate": round(typed_material_valid_rate, 4),
        "synchro_material_failure_rate": round(synchro_material_failure_rate, 4),
        "fusion_material_failure_rate": round(fusion_material_failure_rate, 4),
        "ritual_material_failure_rate": round(ritual_material_failure_rate, 4),
        "link_material_failure_rate": round(link_material_failure_rate, 4),
        "named_material_failure_rate": round(named_material_failure_rate, 4),
        "synchro_exact_level_valid_rate": round(synchro_exact_level_valid_rate, 4),
        "synchro_level_failure_rate": round(synchro_level_failure_rate, 4),
        "ritual_level_valid_rate": round(ritual_level_valid_rate, 4),
        "ritual_level_failure_rate": round(ritual_level_failure_rate, 4),
        "xyz_material_valid_rate": round(xyz_material_valid_rate, 4),
        "link_material_valid_rate": round(link_material_valid_rate, 4),
        "final_score": round(final_score, 2),
    }
    if archetype:
        try:
            from deck.package_builder import summarize_package_metrics
            from deck.package_quality import score_package_quality

            package_metrics = summarize_package_metrics(deck)
            package_quality = score_package_quality(deck, package_metrics, breakdown)
        except Exception:
            package_quality = {}

    breakdown["package_quality_score"] = round(float(package_quality.get("final_package_quality_score", 0.0) or 0.0), 2)
    breakdown["quota_violation_penalty"] = round(float(package_quality.get("quota_violation_penalty", 0.0) or 0.0), 2)
    breakdown["final_score"] = round(breakdown["final_score"] + breakdown["package_quality_score"] * 0.25 - breakdown["quota_violation_penalty"] * 0.5, 2)
    return breakdown


def _consistency_score(deck: list[dict[str, Any]], texts: list[str], archetype: str) -> float:
    search_cards = sum(1 for text in texts if "add" in text or "search" in text or "from your deck" in text)
    draw_cards = sum(1 for text in texts if "draw" in text)
    archetype_cards = sum(
        1
        for card in deck
        if card.get("archetype") and archetype.lower() in str(card.get("archetype", "")).lower()
    )
    archetype_density = archetype_cards / max(len(deck), 1)
    return min(35.0, search_cards * 1.8 + draw_cards * 2.4 + archetype_density * 12)


def _starter_score(deck: list[dict[str, Any]], texts: list[str]) -> float:
    starter_terms = ("normal summon", "add 1", "special summon this card", "from your deck", "reveal")
    starter_cards = sum(1 for text in texts if any(term in text for term in starter_terms))
    low_commitment_monsters = sum(
        1
        for card in deck
        if "monster" in str(card.get("type", "")).lower()
        and _safe_int(card.get("level")) <= 4
        and not is_extra_deck_card(card)
    )
    return min(25.0, starter_cards * 2.0 + low_commitment_monsters * 0.8)


def _extender_score(texts: list[str]) -> float:
    extender_cards = sum(
        1
        for text in texts
        if "special summon" in text
        or "summon this card" in text
        or "from your hand" in text
        or "from your graveyard" in text
        or "from your gy" in text
    )
    return min(25.0, extender_cards * 1.5)


def _interruption_score(deck: list[dict[str, Any]], texts: list[str]) -> float:
    disruption_cards = sum(
        1
        for text in texts
        if "negate" in text or "destroy" in text or "banish" in text or "shuffle" in text
    )
    quick_cards = sum(1 for text in texts if "quick effect" in text)
    traps = sum(1 for card in deck if "trap" in str(card.get("type", "")).lower())
    return min(30.0, disruption_cards * 1.4 + quick_cards * 2.0 + traps * 0.8)


def _brick_penalty(
    deck: list[dict[str, Any]],
    main_deck: list[dict[str, Any]],
    extra_deck: list[dict[str, Any]],
    card_counts: Counter[str],
) -> float:
    penalty = 0.0
    high_level_no_easy_summon = 0
    for card in main_deck:
        level = _safe_int(card.get("level"))
        text = str(card.get("desc", "")).lower()
        if level >= 7 and "special summon" not in text and "ritual" not in str(card.get("type", "")).lower():
            high_level_no_easy_summon += 1

    penalty += high_level_no_easy_summon * 1.4
    penalty += sum(max(0, count - 2) * 0.8 for count in card_counts.values())
    penalty += max(0, len(extra_deck) - 15) * 2.5
    penalty += max(0, 30 - len(main_deck)) * 0.8
    if len(deck) < 40:
        penalty += (40 - len(deck)) * 1.5
    return min(35.0, penalty)


def _endboard_score(extra_deck: list[dict[str, Any]], texts: list[str]) -> float:
    extra_score = min(15.0, len(extra_deck) * 1.0)
    boss_terms = sum(1 for text in texts if "cannot be destroyed" in text or "unaffected" in text or "negate" in text)
    return min(25.0, extra_score + boss_terms * 1.3)


def _learned_card_bonus(deck: list[dict[str, Any]], learned_profile: dict[str, Any]) -> float:
    if not learned_profile:
        return 0.0

    deltas = [learned_card_weight(card.get("name", ""), learned_profile) - 1.0 for card in deck]
    if not deltas:
        return 0.0
    return max(-6.0, min(6.0, sum(deltas) * 3.0))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
