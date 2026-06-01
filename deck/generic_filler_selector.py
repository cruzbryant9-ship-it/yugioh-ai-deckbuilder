from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from deck import advisory_influence_budget as advisory_budget_module
from deck.card_metadata import is_extra_deck_monster, is_monster, is_spell, is_trap
from deck.generic_diff_index import get_diff_index_advisory_signal
from deck.generic_repair_diagnostics import SAFE_GENERIC_FILLER_NAMES, safe_filler_weight, safe_generic_filler_candidates
from SystemAIYugioh.json_utils import safe_load_json
from SystemAIYugioh.banlist import get_card_limit


MAIN_DECK_TARGET = 40
FILLER_GATE_REPORT_PATH = Path("SystemAIYugioh") / "data" / "training_runs" / "generic_benchmarks" / "latest_filler_signal_gate_report.json"
DISALLOWED_EXPERIMENT_FILLERS = {"Nibiru, the Primal Being", "Infinite Impermanence"}

HAND_TRAP_NAMES = {
    "Ash Blossom & Joyous Spring",
    "Effect Veiler",
    "Droll & Lock Bird",
    "D.D. Crow",
    "Nibiru, the Primal Being",
    "Ghost Belle & Haunted Mansion",
    "Ghost Ogre & Snow Rabbit",
}

BOARD_BREAKER_NAMES = {
    "Dark Ruler No More",
    "Evenly Matched",
    "Lightning Storm",
    "Raigeki",
    "Harpie's Feather Duster",
    "Forbidden Droplet",
    "Book of Moon",
    "Book of Eclipse",
    "Book of Lunar Eclipse",
    "Cosmic Cyclone",
}

CONSISTENCY_NAMES = {
    "Triple Tactics Talent",
    "Triple Tactics Thrust",
    "Upstart Goblin",
    "Pot of Prosperity",
    "Pot of Extravagance",
    "Pot of Desires",
    "Pot of Duality",
    "Small World",
    "Terraforming",
}

DEFENSIVE_TRAP_NAMES = {
    "Infinite Impermanence",
    "Solemn Judgment",
    "Solemn Strike",
    "Solemn Warning",
    "Dimensional Barrier",
    "Anti-Spell Fragrance",
}


def select_contextual_fillers(
    archetype: str,
    mode: str,
    missing_count: int,
    card_pool: list[dict[str, Any]],
    current_deck: list[dict[str, Any]],
    package_counts: dict[str, int] | Counter[str] | None,
    diagnosis: dict[str, Any] | None = None,
    matchup: Any = None,
    enable_filler_memory_influence: bool = False,
) -> dict[str, Any]:
    """Choose legal generic fillers by role pressure and deck texture.

    The selector only ranks cards that are already legal safe-filler candidates.
    It does not veto legal improving decks or relax any banlist/copy-limit rule.
    """

    missing = max(0, min(int(missing_count or 0), MAIN_DECK_TARGET - len(non_extra_cards(current_deck))))
    if missing <= 0:
        return empty_result()

    counts = Counter(card_name(card) for card in current_deck)
    package_counter = Counter(package_counts or {})
    if not package_counter:
        package_counter = infer_package_counts(current_deck)
    context = build_context(archetype, mode, current_deck, package_counter, diagnosis, matchup)
    influence_state = filler_memory_influence_state(enable_filler_memory_influence)
    context["filler_memory_influence"] = influence_state
    legal_candidates = safe_generic_filler_candidates(card_pool, current_deck, mode)
    rejected = rejected_filler_rows(card_pool, counts, set(card_name(card) for card in legal_candidates))

    selected_cards: list[dict[str, Any]] = []
    selected_names: list[str] = []
    context_scores: dict[str, float] = {}
    filler_reasons: list[str] = []
    rounds_remaining = missing

    while rounds_remaining > 0:
        candidates = available_candidates(card_pool, counts, mode)
        if influence_state.get("enabled"):
            blocked_selected = [card_name(card) for card in candidates if card_name(card) in DISALLOWED_EXPERIMENT_FILLERS]
            if blocked_selected:
                rejected_due_to_not_ready = influence_state.setdefault("rejected_due_to_not_activation_ready", [])
                for name in blocked_selected:
                    if name not in rejected_due_to_not_ready:
                        rejected_due_to_not_ready.append(name)
                candidates = [card for card in candidates if card_name(card) not in DISALLOWED_EXPERIMENT_FILLERS]
        if not candidates:
            break
        scored = score_candidates_with_influence(candidates, mode, context)
        if influence_state.get("enabled"):
            before = sorted(((base, card) for _final, base, _bias, card in scored), key=lambda item: (item[0], safe_filler_weight(item[1], mode), card_name(item[1])), reverse=True)
            after = sorted(((final, card) for final, _base, _bias, card in scored), key=lambda item: (item[0], safe_filler_weight(item[1], mode), card_name(item[1])), reverse=True)
            if before and after:
                before_name = card_name(before[0][1])
                after_name = card_name(after[0][1])
                if not influence_state.get("selected_filler_before_bias"):
                    influence_state["selected_filler_before_bias"] = before_name
                if not influence_state.get("selected_filler_after_bias"):
                    influence_state["selected_filler_after_bias"] = after_name
                influence_state["influence_changed_order"] = bool(influence_state.get("influence_changed_order")) or before_name != after_name
        for score, _base_score, _bias, card in scored:
            context_scores[card_name(card)] = round(score, 4)
        scored.sort(key=lambda item: (item[0], safe_filler_weight(item[3], mode), card_name(item[3])), reverse=True)
        score, _base_score, _bias, chosen = scored[0]
        name = card_name(chosen)
        if counts[name] >= get_card_limit(chosen):
            rejected.append({"name": name, "reason": "copy_limit_after_context_selection"})
            break
        selected_cards.append(chosen)
        selected_names.append(name)
        counts[name] += 1
        rounds_remaining -= 1
        role = classify_filler_role(chosen)
        package_counter[role_to_package(role)] += 1
        context = build_context(archetype, mode, current_deck + selected_cards, package_counter, diagnosis, matchup)
        context["filler_memory_influence"] = influence_state
        filler_reasons.append(reason_for_selection(chosen, score, context))

    selected_set = set(selected_names)
    for score, card in sorted(
        ((score_filler(card, mode, context), card) for card in legal_candidates if card_name(card) not in selected_set),
        key=lambda item: item[0],
    )[:20]:
        rejected.append({"name": card_name(card), "reason": "lower_context_score", "score": round(score, 4)})

    roles_for_selected = [classify_filler_role(card_from_name(card_pool, name) or {"name": name}) for name in selected_names]
    roles_by_card = {name: classify_filler_role(card_from_name(card_pool, name) or {"name": name}) for name in selected_names}
    role_counts = Counter(roles_for_selected)
    return {
        "selected_fillers": selected_names,
        "filler_reasons": filler_reasons,
        "filler_roles": {"counts": dict(sorted(role_counts.items())), "by_card": roles_by_card},
        "context_scores": dict(sorted(context_scores.items())),
        "rejected_fillers": rejected[:40],
        "context": context,
        "filler_memory_influence": public_influence_state(influence_state),
        "_selected_cards": selected_cards,
    }


def empty_result() -> dict[str, Any]:
    return {
        "selected_fillers": [],
        "filler_reasons": [],
        "filler_roles": {"counts": {}, "by_card": {}},
        "context_scores": {},
        "rejected_fillers": [],
        "context": {},
        "filler_memory_influence": public_influence_state(filler_memory_influence_state(False)),
        "_selected_cards": [],
    }


def available_candidates(card_pool: list[dict[str, Any]], counts: Counter[str], mode: str) -> list[dict[str, Any]]:
    probe_deck: list[dict[str, Any]] = []
    for name, amount in counts.items():
        probe_deck.extend({"name": name} for _ in range(amount))
    return safe_generic_filler_candidates(card_pool, probe_deck, mode)


def score_filler(card: dict[str, Any], mode: str, context: dict[str, Any]) -> float:
    role = classify_filler_role(card)
    name = card_name(card)
    score = safe_filler_weight(card, mode)
    score += role_pressure_bonus(role, context)
    score += texture_bonus(card, role, context)
    score += matchup_bonus(name, role, context)
    score += diagnosis_bonus(role, context)
    score += reliance_bonus(name, role, context)
    score += diff_index_bonus(name, context)
    if role == "brick_risk":
        score -= 0.35
    return round(max(0.01, score), 6)


def score_candidates_with_influence(candidates: list[dict[str, Any]], mode: str, context: dict[str, Any]) -> list[tuple[float, float, float, dict[str, Any]]]:
    rows = []
    for card in candidates:
        base = score_filler(card, mode, context)
        bias = filler_memory_bonus(card_name(card), context)
        rows.append((round(max(0.01, base + bias), 6), base, bias, card))
    return rows


def filler_memory_influence_state(enabled: bool) -> dict[str, Any]:
    gate_report = safe_load_json(FILLER_GATE_REPORT_PATH, {})
    activation_ready = set()
    if isinstance(gate_report, dict):
        activation_ready = {
            str(name)
            for name in gate_report.get("summary", {}).get("activation_ready_fillers", []) or []
            if str(name) not in DISALLOWED_EXPERIMENT_FILLERS
        }
    effective_enabled = bool(enabled) and not advisory_budget_module.ADVISORY_KILL_SWITCH
    if not advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE:
        effective_enabled = False
    blocked = []
    if isinstance(gate_report, dict):
        for row in gate_report.get("eligible_signals", []) or []:
            name = str(row.get("card", ""))
            if not name or name in activation_ready:
                continue
            if name in DISALLOWED_EXPERIMENT_FILLERS or not row.get("holdout_passed") or not row.get("activation_ready"):
                blocked.append(name)
    return {
        "enabled": effective_enabled,
        "requested": bool(enabled),
        "global_enabled": bool(advisory_budget_module.ENABLE_FILLER_MEMORY_INFLUENCE),
        "kill_switch": bool(advisory_budget_module.ADVISORY_KILL_SWITCH),
        "allowed_activation_ready_fillers_only": bool(advisory_budget_module.ALLOWED_ACTIVATION_READY_FILLERS_ONLY),
        "max_filler_memory_bias": advisory_budget_module.MAX_FILLER_MEMORY_BIAS,
        "per_card_filler_bias_cap": advisory_budget_module.PER_CARD_FILLER_MEMORY_BIAS_CAP,
        "fillers_allowed_for_influence": sorted(activation_ready),
        "fillers_blocked_from_influence": sorted(set(blocked) | DISALLOWED_EXPERIMENT_FILLERS),
        "filler_memory_bias_applied": {},
        "rejected_due_to_not_activation_ready": [],
        "influence_changed_order": False,
        "selected_filler_before_bias": None,
        "selected_filler_after_bias": None,
    }


def filler_memory_bonus(name: str, context: dict[str, Any]) -> float:
    state = context.get("filler_memory_influence", {}) if isinstance(context.get("filler_memory_influence"), dict) else {}
    if not state.get("enabled"):
        return 0.0
    allowed = set(state.get("fillers_allowed_for_influence", []) or [])
    if advisory_budget_module.ALLOWED_ACTIVATION_READY_FILLERS_ONLY and name not in allowed:
        rejected = state.setdefault("rejected_due_to_not_activation_ready", [])
        if name not in rejected:
            rejected.append(name)
        return 0.0
    if name in DISALLOWED_EXPERIMENT_FILLERS:
        return 0.0
    per_card = abs(float(advisory_budget_module.PER_CARD_FILLER_MEMORY_BIAS_CAP))
    global_cap = abs(float(advisory_budget_module.MAX_FILLER_MEMORY_BIAS))
    applied_so_far = sum(abs(float(value or 0)) for value in state.get("filler_memory_bias_applied", {}).values())
    remaining = max(0.0, global_cap - applied_so_far)
    bias = round(min(per_card, remaining), 6)
    if bias <= 0:
        return 0.0
    state.setdefault("filler_memory_bias_applied", {})[name] = bias
    return bias


def public_influence_state(state: dict[str, Any]) -> dict[str, Any]:
    public = dict(state)
    public["fillers_allowed_for_influence"] = sorted(set(public.get("fillers_allowed_for_influence", []) or []))
    public["fillers_blocked_from_influence"] = sorted(set(public.get("fillers_blocked_from_influence", []) or []))
    public["rejected_due_to_not_activation_ready"] = sorted(set(public.get("rejected_due_to_not_activation_ready", []) or []))
    public["filler_memory_bias_applied"] = dict(sorted((public.get("filler_memory_bias_applied", {}) or {}).items()))
    return public


def role_pressure_bonus(role: str, context: dict[str, Any]) -> float:
    pressure = context.get("role_pressure", {})
    bonuses = {
        "handtrap": pressure.get("interruptions", 0) * 0.42,
        "defensive_trap": pressure.get("interruptions", 0) * 0.34,
        "board_breaker": pressure.get("board_breakers", 0) * 0.38,
        "consistency": max(pressure.get("starters_searchers", 0), pressure.get("recovery", 0)) * 0.32,
    }
    return float(bonuses.get(role, 0.08))


def texture_bonus(card: dict[str, Any], role: str, context: dict[str, Any]) -> float:
    bonus = 0.0
    if context.get("spell_trap_heavy"):
        if is_spell(card) or is_trap(card):
            bonus += 0.18
        if role == "consistency":
            bonus += 0.08
    if context.get("monster_heavy") and role == "handtrap":
        bonus += 0.1
    if context.get("mode") == "meta" and role in {"handtrap", "defensive_trap"}:
        bonus += 0.08
    if context.get("mode") == "innovation" and role in {"consistency", "board_breaker"}:
        bonus += 0.06
    return bonus


def matchup_bonus(name: str, role: str, context: dict[str, Any]) -> float:
    matchup = str(context.get("matchup", "")).casefold()
    going = str(context.get("going", "")).casefold()
    bonus = 0.0
    if matchup in {"combo", "handtrap_heavy"} and role in {"handtrap", "defensive_trap"}:
        bonus += 0.18
    if matchup in {"graveyard", "tearlaments"} and name in {"D.D. Crow", "Ghost Belle & Haunted Mansion", "Called by the Grave"}:
        bonus += 0.24
    if matchup in {"backrow", "stun", "control"} and name in {"Cosmic Cyclone", "Harpie's Feather Duster", "Lightning Storm", "Evenly Matched"}:
        bonus += 0.22
    if matchup in {"spell_heavy", "runick"} and name in {"Anti-Spell Fragrance", "Droll & Lock Bird", "Cosmic Cyclone"}:
        bonus += 0.18
    if going == "second" and role == "board_breaker":
        bonus += 0.18
    if going == "first" and role in {"defensive_trap", "handtrap"}:
        bonus += 0.12
    return bonus


def diagnosis_bonus(role: str, context: dict[str, Any]) -> float:
    causes = set(context.get("diagnosis_causes", []))
    bonus = 0.0
    if "interruption_shortage" in causes and role in {"handtrap", "defensive_trap"}:
        bonus += 0.2
    if "starter_density_low" in causes and role == "consistency":
        bonus += 0.18
    if "brick_pressure_high" in causes and role != "brick_risk":
        bonus += 0.08
    if "board_breaker_overfill" in causes and role == "board_breaker":
        bonus -= 0.2
    if "repair_dependency_high" in causes and role in {"consistency", "handtrap"}:
        bonus += 0.08
    return bonus


def reliance_bonus(name: str, role: str, context: dict[str, Any]) -> float:
    bonus = 0.0
    if context.get("graveyard_reliance") and name in {"Called by the Grave", "Ghost Belle & Haunted Mansion"}:
        bonus += 0.1
    if context.get("banish_reliance") and name in {"Pot of Desires", "Pot of Extravagance", "Pot of Prosperity"}:
        bonus -= 0.16
    if context.get("extra_deck_reliance") and name in {"Pot of Extravagance", "Pot of Prosperity"}:
        bonus -= 0.14
    if role == "consistency" and context.get("search_access_need"):
        bonus += 0.08
    return bonus


def diff_index_bonus(name: str, context: dict[str, Any]) -> float:
    signal = get_diff_index_advisory_signal(
        str(context.get("archetype", "unknown")),
        {"copy_increases": {name: 1}, "copy_decreases": {}},
    )
    hints = signal.get("hints", []) or []
    if not hints:
        return 0.0
    # Keep this smaller than the Phase 6M advisory cap; it only affects filler order.
    return max(-0.02, min(0.02, float(signal.get("capped_signal", 0) or 0)))


def build_context(
    archetype: str,
    mode: str,
    current_deck: list[dict[str, Any]],
    package_counts: Counter[str],
    diagnosis: dict[str, Any] | None,
    matchup: Any,
) -> dict[str, Any]:
    main = non_extra_cards(current_deck)
    spell_trap_ratio = sum(1 for card in main if is_spell(card) or is_trap(card)) / max(1, len(main))
    monster_ratio = sum(1 for card in main if is_monster(card)) / max(1, len(main))
    diagnosis = diagnosis or {}
    matchup_name, going = normalize_matchup(matchup)
    role_pressure = {
        "starters_searchers": missing_pressure(package_counts.get("starters_searchers", 0), 8),
        "interruptions": missing_pressure(package_counts.get("interruptions", 0), 8 if mode == "meta" else 5),
        "board_breakers": missing_pressure(package_counts.get("board_breakers", 0), 2 if mode == "meta" else 3),
        "recovery": missing_pressure(package_counts.get("recovery", 0), 2),
    }
    text = " ".join(f"{card.get('name', '')} {card.get('type', '')} {card.get('desc', '')}" for card in main).casefold()
    return {
        "archetype": archetype,
        "mode": mode,
        "matchup": matchup_name,
        "going": going,
        "spell_trap_heavy": spell_trap_ratio >= 0.55,
        "monster_heavy": monster_ratio >= 0.55,
        "spell_trap_ratio": round(spell_trap_ratio, 4),
        "monster_ratio": round(monster_ratio, 4),
        "role_pressure": role_pressure,
        "diagnosis_causes": list(diagnosis.get("suspected_causes", []) or []),
        "graveyard_reliance": "gy" in text or "graveyard" in text,
        "banish_reliance": "banish" in text,
        "extra_deck_reliance": sum(1 for card in current_deck if is_extra_deck_monster(card)) >= 8,
        "search_access_need": role_pressure["starters_searchers"] > 0.25,
    }


def normalize_matchup(matchup: Any) -> tuple[str, str]:
    if isinstance(matchup, dict):
        return str(matchup.get("name") or matchup.get("matchup") or ""), str(matchup.get("going") or "")
    return str(matchup or ""), ""


def missing_pressure(current: int, target: int) -> float:
    if target <= 0:
        return 0.0
    return round(max(0.0, min(1.0, (target - int(current or 0)) / target)), 4)


def classify_filler_role(card: dict[str, Any]) -> str:
    name = card_name(card)
    text = f"{name} {card.get('type', '')} {card.get('desc', '')}".casefold()
    if name in HAND_TRAP_NAMES:
        return "handtrap"
    if name in DEFENSIVE_TRAP_NAMES:
        return "defensive_trap"
    if name in BOARD_BREAKER_NAMES:
        return "board_breaker"
    if name in CONSISTENCY_NAMES:
        return "consistency"
    if "negate" in text or "quick effect" in text or "banish" in text:
        return "handtrap"
    if "draw" in text or "add " in text or "from your deck" in text:
        return "consistency"
    if "destroy" in text or "send" in text:
        return "board_breaker"
    return "generic_safe_filler"


def role_to_package(role: str) -> str:
    if role in {"handtrap", "defensive_trap"}:
        return "interruptions"
    if role == "board_breaker":
        return "board_breakers"
    if role == "consistency":
        return "starters_searchers"
    return "core"


def infer_package_counts(deck: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for card in non_extra_cards(deck):
        counter[role_to_package(classify_filler_role(card))] += 1
    return counter


def reason_for_selection(card: dict[str, Any], score: float, context: dict[str, Any]) -> str:
    role = classify_filler_role(card)
    pressure = context.get("role_pressure", {})
    reason = f"{card_name(card)} selected as {role} filler (score {round(score, 3)})"
    if role in {"handtrap", "defensive_trap"} and pressure.get("interruptions", 0) > 0:
        reason += "; covers interruption pressure"
    elif role == "board_breaker" and pressure.get("board_breakers", 0) > 0:
        reason += "; covers board-breaker pressure"
    elif role == "consistency" and pressure.get("starters_searchers", 0) > 0:
        reason += "; supports consistency pressure"
    if context.get("spell_trap_heavy") and (is_spell(card) or is_trap(card)):
        reason += "; fits spell/trap-heavy texture"
    if context.get("matchup"):
        reason += f"; matchup context {context.get('matchup')}"
    return reason


def rejected_filler_rows(card_pool: list[dict[str, Any]], counts: Counter[str], legal_names: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for card in card_pool:
        name = card_name(card)
        if name not in SAFE_GENERIC_FILLER_NAMES or name in seen or name in legal_names:
            continue
        seen.add(name)
        if is_extra_deck_monster(card):
            reason = "extra_deck_card"
        elif get_card_limit(card) <= 0:
            reason = "blocked_or_forbidden"
        elif counts[name] >= get_card_limit(card):
            reason = "copy_limit_reached"
        else:
            reason = "not_selected"
        rows.append({"name": name, "reason": reason})
    return rows


def card_from_name(card_pool: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for card in card_pool:
        if card_name(card) == name:
            return card
    return None


def non_extra_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for card in cards if not is_extra_deck_monster(card)]


def card_name(card: Any) -> str:
    return str(card.get("name", card)) if isinstance(card, dict) else str(card)
