from __future__ import annotations

from collections import Counter
from typing import Any

from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.semi_specialized_quota_replay import replay_quota_sensitivity
from deck.semi_specialized_role_reconciliation import reconcile_specialization_roles
from SystemAIYugioh.banlist import get_card_limit


SUPPORTED_EXPERIMENTAL_PROFILES = {"kashtira"}
SUPPORTED_EXPERIMENTAL_VARIANTS = {None, "", "hybrid_generic_interaction_overlay"}
INTERACTION_CORE = ("Ash Blossom & Joyous Spring", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being")


def build_experimental_semi_specialized_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str = "meta",
    profile: str | None = None,
    size: int = 40,
    variant: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gate_report = evaluate_experimental_gates(cards, archetype, mode, profile, variant=variant)
    if not gate_report["eligible"]:
        return fallback_generic(cards, archetype, mode, size, gate_report)

    try:
        if normalize_variant(variant) == "hybrid_generic_interaction_overlay":
            deck, report = build_hybrid_overlay_candidate_deck(cards, archetype, mode, size)
        else:
            deck, report = build_candidate_deck(cards, archetype, mode, size)
    except Exception as exc:
        gate_report["gate_failures"].append(f"experimental build exception: {exc}")
        return fallback_generic(cards, archetype, mode, size, gate_report)

    main, extra = split_deck(deck)
    violations = legality_violations(deck, size)
    if violations:
        gate_report["gate_failures"].extend(violations)
        return fallback_generic(cards, archetype, mode, size, gate_report)

    report.update(
        {
            "builder_used": "semi_specialized_experimental",
            "experimental": True,
            "not_default": True,
            "fallback_used": False,
            "experimental_profile": profile,
            "variant": normalize_variant(variant),
            "dry_run_variant": normalize_variant(variant) == "hybrid_generic_interaction_overlay",
            "experimental_gate_report": gate_report,
            "main_deck_count": len(main),
            "extra_deck_count": len(extra),
        }
    )
    return deck, report


def evaluate_experimental_gates(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    profile: str | None,
    variant: str | None = None,
) -> dict[str, Any]:
    requested = str(profile or "")
    failures = []
    if archetype.casefold() not in SUPPORTED_EXPERIMENTAL_PROFILES:
        failures.append("unsupported archetype for experimental semi-specialization")
    if requested.casefold() != archetype.casefold():
        failures.append("requested specialization profile must exactly match archetype")
    normalized_variant = normalize_variant(variant)
    if normalized_variant not in SUPPORTED_EXPERIMENTAL_VARIANTS:
        failures.append(f"unsupported experimental variant: {variant}")
    reconciliation = reconcile_specialization_roles(archetype, mode) if not failures or archetype.casefold() in SUPPORTED_EXPERIMENTAL_PROFILES else {}
    replay = replay_quota_sensitivity(archetype, mode, runs=2) if archetype.casefold() in SUPPORTED_EXPERIMENTAL_PROFILES else {}
    full = sensitivity_result(replay, 1.0)
    observations = replay.get("run_observations", []) or []
    filler_dependency = average_observation(observations, "safe_filler_used_count")
    repair_dependency = average_observation(observations, "repair_action_count")
    blocked = sorted(set(name for row in observations for name in blocked_names_from_observation(cards, row)))

    if reconciliation.get("expected_audit_score_after_reconciliation", 0.0) < 0.95:
        failures.append("reconciled audit score below 0.95")
    if reconciliation.get("projected_conflict_count", 1) != 0:
        failures.append("reconciled role map still has unresolved conflicts")
    if filler_dependency > average_observation(observations, "safe_filler_used_count"):
        failures.append("filler dependency increased versus generic")
    if repair_dependency > average_observation(observations, "repair_action_count"):
        failures.append("repair dependency increased versus generic")
    if blocked:
        failures.append(f"blocked-card violations in generic evidence: {', '.join(blocked[:8])}")
    recommendation = "eligible_for_experimental_flag" if not failures and full.get("total_gap", 9999) < replay.get("generic_total_gap", 0) else "do_not_activate"
    if recommendation != "eligible_for_experimental_flag":
        failures.append("Phase 8H recommendation is not eligible_for_experimental_flag")
    return {
        "eligible": not failures,
        "gate_failures": sorted(set(failures)),
        "phase8h_recommendation": recommendation,
        "reconciled_audit_score": reconciliation.get("expected_audit_score_after_reconciliation", 0.0),
        "unresolved_conflicts": reconciliation.get("projected_conflict_count"),
        "generic_quota_gap": replay.get("generic_total_gap"),
        "reconciled_projected_gap": full.get("total_gap"),
        "filler_dependency": filler_dependency,
        "repair_dependency": repair_dependency,
        "blocked_card_violations": blocked,
        "not_activated_default": True,
        "variant": normalized_variant,
    }


def build_candidate_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reconciliation = reconcile_specialization_roles(archetype, mode)
    role_map = reconciliation.get("kept_roles", {})
    quota_targets = {
        "starters": 12,
        "extenders": 7,
        "interruptions": 9,
        "board_breakers": 3,
        "payoffs": 3,
        "bricks_garnets": 0,
    }
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    for role in ("starters", "extenders", "interruptions", "board_breakers", "payoffs"):
        target = quota_targets.get(role, 0)
        for name in role_map.get(role, []) or []:
            card = lookup.get(name)
            if card and is_extra_deck_card(card):
                continue
            while card and package_counts[role] < target and add_legal_copy(selected, counts, card):
                package_counts[role] += 1
            if package_counts[role] >= target:
                break

    generic_deck, generic_report = build_generic_deck(archetype, cards, mode=mode, ratio_profile={"payoffs": 3, "max_bricks": 3})
    generic_main, generic_extra = split_deck(generic_deck)
    for card in generic_main:
        if len(selected) >= size:
            break
        if add_legal_copy(selected, counts, card):
            package_counts["generic_fill"] += 1
    selected = selected[:size]

    extra = []
    extra_counts: Counter[str] = Counter()
    for name in role_map.get("extra_deck_preferences", []) or []:
        card = lookup.get(name)
        if card and is_extra_deck_card(card) and add_legal_copy(extra, extra_counts, card):
            pass
    for card in generic_extra:
        if len(extra) >= 15:
            break
        add_legal_copy(extra, extra_counts, card)
    deck = selected + extra[:15]
    return deck, {
        "package_counts": dict(sorted(package_counts.items())),
        "quota_warnings": [],
        "generic_report_used_for_fill": {
            "builder_used": generic_report.get("builder_used"),
            "package_counts": generic_report.get("package_counts", {}),
        },
        "reconciled_role_updates": reconciliation.get("proposed_role_updates", {}),
    }


def build_hybrid_overlay_candidate_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reconciliation = reconcile_specialization_roles(archetype, mode)
    role_map = reconciliation.get("kept_roles", {})
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    generic_deck, generic_report = build_generic_deck(archetype, cards, mode=mode, ratio_profile={"payoffs": 3, "max_bricks": 3})
    generic_main, generic_extra = split_deck(generic_deck)
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()

    for name in INTERACTION_CORE:
        card = lookup.get(name)
        generic_copies = sum(1 for generic_card in generic_main if str(generic_card.get("name", "")) == name)
        while card and generic_copies > 0 and add_legal_copy(selected, counts, card):
            generic_copies -= 1
            package_counts["preserved_interaction"] += 1

    softened_targets = {
        "starters": 10,
        "extenders": 9,
        "interruptions": 6,
        "board_breakers": 2,
        "payoffs": 2,
    }
    for role in ("starters", "extenders", "interruptions", "board_breakers", "payoffs"):
        target = softened_targets.get(role, 0)
        for name in role_map.get(role, []) or []:
            card = lookup.get(name)
            if card and is_extra_deck_card(card):
                continue
            while card and package_counts[role] < target and add_legal_copy(selected, counts, card):
                package_counts[role] += 1
            if package_counts[role] >= target:
                break

    for card in generic_main:
        if len(selected) >= size:
            break
        if add_legal_copy(selected, counts, card):
            package_counts["generic_fill"] += 1
    selected = selected[:size]

    extra = []
    extra_counts: Counter[str] = Counter()
    payoff_added = 0
    for name in role_map.get("extra_deck_preferences", []) or []:
        if payoff_added >= 2:
            break
        card = lookup.get(name)
        if card and is_extra_deck_card(card) and add_legal_copy(extra, extra_counts, card):
            payoff_added += 1
    for card in generic_extra:
        if len(extra) >= 15:
            break
        add_legal_copy(extra, extra_counts, card)
    deck = selected + extra[:15]
    return deck, {
        "package_counts": dict(sorted(package_counts.items())),
        "quota_warnings": [],
        "generic_report_used_for_fill": {
            "builder_used": generic_report.get("builder_used"),
            "package_counts": generic_report.get("package_counts", {}),
        },
        "reconciled_role_updates": reconciliation.get("proposed_role_updates", {}),
    }


def fallback_generic(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    size: int,
    gate_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    deck, report = build_generic_deck(archetype, cards, mode=mode)
    main, extra = split_deck(deck)
    report.update(
        {
            "builder_used": "generic",
            "experimental": False,
            "not_default": True,
            "fallback_used": True,
            "variant": gate_report.get("variant"),
            "dry_run_variant": gate_report.get("variant") == "hybrid_generic_interaction_overlay",
            "experimental_gate_report": gate_report,
            "quota_warnings": sorted(set((report.get("quota_warnings", []) or []) + gate_report.get("gate_failures", []))),
            "main_deck_count": len(main),
            "extra_deck_count": len(extra),
        }
    )
    return deck[: size + len(extra)], report


def legality_violations(deck: list[dict[str, Any]], size: int) -> list[str]:
    main, extra = split_deck(deck)
    violations = []
    if len(main) < size:
        violations.append(f"experimental main deck under {size} cards")
    if len(extra) > 15:
        violations.append("experimental Extra Deck exceeds 15 cards")
    violations.extend(f"blocked card selected: {name}" for name in blocked_card_violations(deck))
    counts = Counter(str(card.get("name", "")) for card in deck)
    by_name = {str(card.get("name", "")): card for card in deck}
    for name, count in counts.items():
        if count > get_card_limit(by_name[name]):
            violations.append(f"copy limit exceeded: {name} {count}>{get_card_limit(by_name[name])}")
    return sorted(set(violations))


def add_legal_copy(deck: list[dict[str, Any]], counts: Counter[str], card: dict[str, Any]) -> bool:
    name = str(card.get("name", ""))
    if not name or get_card_limit(card) <= 0 or counts[name] >= get_card_limit(card):
        return False
    deck.append(card)
    counts[name] += 1
    return True


def is_extra_deck_card(card: dict[str, Any]) -> bool:
    return any(term in str(card.get("type", "")).casefold() for term in ("fusion", "synchro", "xyz", "link"))


def sensitivity_result(replay: dict[str, Any], strength: float) -> dict[str, Any]:
    for result in replay.get("sensitivity_results", []) or []:
        if round(float(result.get("movement_strength", -1)), 4) == round(float(strength), 4):
            return result
    return {}


def average_observation(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row.get(key, 0) or 0) for row in rows) / len(rows), 4)


def blocked_names_from_observation(cards: list[dict[str, Any]], row: dict[str, Any]) -> list[str]:
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    blocked = []
    for name in [*(row.get("main_card_names", []) or []), *(row.get("extra_card_names", []) or [])]:
        card = lookup.get(str(name))
        if card and get_card_limit(card) <= 0:
            blocked.append(str(name))
    return blocked


def normalize_variant(variant: str | None) -> str | None:
    if variant is None:
        return None
    normalized = str(variant).strip()
    return normalized or None
