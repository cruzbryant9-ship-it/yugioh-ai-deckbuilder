from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from deck.deck_utils import blocked_card_violations, split_deck
from deck.generic_deck_builder import build_generic_deck
from deck.interaction_core_registry import interaction_core_for
from deck.semi_specialized_quota_replay import replay_quota_sensitivity
from deck.semi_specialized_role_reconciliation import reconcile_specialization_roles
from SystemAIYugioh.banlist import get_card_limit


SUPPORTED_EXPERIMENTAL_PROFILES = {"kashtira"}
PUBLIC_OVERLAY_TUNING_VARIANTS = {
    "public_overlay_reduce_generic_fill",
    "public_overlay_archetype_fill_priority",
    "public_overlay_interaction_plus_archetype_core",
    "public_overlay_restore_overlap_reduce_preparations",
}
SUPPORTED_EXPERIMENTAL_VARIANTS = {
    None,
    "",
    "hybrid_generic_interaction_overlay",
    "public_baseline_interaction_overlay",
    *PUBLIC_OVERLAY_TUNING_VARIANTS,
}
INTERACTION_CORE = interaction_core_for("Kashtira")


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
        normalized_variant = normalize_variant(variant)
        if normalized_variant in {"public_baseline_interaction_overlay", *PUBLIC_OVERLAY_TUNING_VARIANTS}:
            deck, report = build_public_baseline_overlay_candidate_deck(cards, archetype, mode, size, variant=normalized_variant)
        elif normalized_variant == "hybrid_generic_interaction_overlay":
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
            "variant": normalized_variant,
            "dry_run_variant": is_dry_run_variant(normalized_variant),
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
    baseline_dependencies = dependency_observation_summary(observations)
    candidate_dependencies = measure_candidate_dependencies(cards, archetype, mode, normalized_variant)
    dependency_gates = dependency_gate_report(baseline_dependencies, candidate_dependencies)
    filler_dependency = candidate_dependencies["filler_dependency"]
    repair_dependency = candidate_dependencies["repair_dependency"]
    blocked = sorted(set(name for row in observations for name in blocked_names_from_observation(cards, row)))

    if reconciliation.get("expected_audit_score_after_reconciliation", 0.0) < 0.95:
        failures.append("reconciled audit score below 0.95")
    if reconciliation.get("projected_conflict_count", 1) != 0:
        failures.append("reconciled role map still has unresolved conflicts")
    failures.extend(dependency_gates["failures"])
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
        "generic_filler_dependency": baseline_dependencies["filler_dependency"],
        "generic_repair_dependency": baseline_dependencies["repair_dependency"],
        "dependency_gate_report": dependency_gates,
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
    quota_stage_selected_names: list[str] = []
    generic_fill_stage_selected_names: list[str] = []
    for role in ("starters", "extenders", "interruptions", "board_breakers", "payoffs"):
        target = quota_targets.get(role, 0)
        for name in role_map.get(role, []) or []:
            card = lookup.get(name)
            if card and is_extra_deck_card(card):
                continue
            while card and package_counts[role] < target and add_legal_copy(selected, counts, card):
                package_counts[role] += 1
                quota_stage_selected_names.append(str(card.get("name", "")))
            if package_counts[role] >= target:
                break

    generic_deck, generic_report = build_generic_deck(archetype, cards, mode=mode, ratio_profile={"payoffs": 3, "max_bricks": 3})
    generic_main, generic_extra = split_deck(generic_deck)
    for card in generic_main:
        if len(selected) >= size:
            break
        if add_legal_copy(selected, counts, card):
            package_counts["generic_fill"] += 1
            generic_fill_stage_selected_names.append(str(card.get("name", "")))
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
        "safe_filler_used_count": 0,
        "repair_used": False,
        "repair_success": True,
        "repair_action_count": 0,
        "interaction_preservation_attempted": False,
        "interaction_candidates_selected": 0,
        "interaction_candidates_rejected": [],
        "interaction_rejection_reasons": [],
        "interaction_trace_metadata": {
            "quota_stage_selected_names": quota_stage_selected_names,
            "interaction_preservation_stage_selected_names": [],
            "interaction_preservation_stage_rejected_names": [],
            "interaction_preservation_stage_rejection_reasons": [],
            "generic_fill_stage_selected_names": generic_fill_stage_selected_names,
            "internal_generic_baseline_main_names": [str(card.get("name", "")) for card in generic_main],
            "final_main_names": [str(card.get("name", "")) for card in selected],
            "final_extra_names": [str(card.get("name", "")) for card in extra[:15]],
        },
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
    interaction_rejected: list[str] = []
    interaction_rejection_reasons: list[str] = []
    interaction_stage_selected_names: list[str] = []
    quota_stage_selected_names: list[str] = []
    generic_fill_stage_selected_names: list[str] = []

    for name in INTERACTION_CORE:
        card = lookup.get(name)
        generic_copies = sum(1 for generic_card in generic_main if str(generic_card.get("name", "")) == name)
        initial_generic_copies = generic_copies
        selected_before = package_counts["preserved_interaction"]
        while card and generic_copies > 0 and add_legal_copy(selected, counts, card):
            generic_copies -= 1
            package_counts["preserved_interaction"] += 1
            interaction_stage_selected_names.append(str(card.get("name", "")))
        selected_for_card = package_counts["preserved_interaction"] - selected_before
        if selected_for_card <= 0:
            interaction_rejected.append(name)
            if not card:
                interaction_rejection_reasons.append(f"{name}: card unavailable in pool")
            elif initial_generic_copies <= 0:
                interaction_rejection_reasons.append(f"{name}: absent from generic baseline main deck")
            else:
                interaction_rejection_reasons.append(f"{name}: legal copy limit prevented preservation")

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
                quota_stage_selected_names.append(str(card.get("name", "")))
            if package_counts[role] >= target:
                break

    for card in generic_main:
        if len(selected) >= size:
            break
        if add_legal_copy(selected, counts, card):
            package_counts["generic_fill"] += 1
            generic_fill_stage_selected_names.append(str(card.get("name", "")))
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
        "safe_filler_used_count": 0,
        "repair_used": False,
        "repair_success": True,
        "repair_action_count": 0,
        "interaction_preservation_attempted": True,
        "interaction_candidates_selected": int(package_counts.get("preserved_interaction", 0) or 0),
        "interaction_candidates_rejected": interaction_rejected,
        "interaction_rejection_reasons": interaction_rejection_reasons,
        "interaction_trace_metadata": {
            "quota_stage_selected_names": quota_stage_selected_names,
            "interaction_preservation_stage_selected_names": interaction_stage_selected_names,
            "interaction_preservation_stage_rejected_names": interaction_rejected,
            "interaction_preservation_stage_rejection_reasons": interaction_rejection_reasons,
            "generic_fill_stage_selected_names": generic_fill_stage_selected_names,
            "internal_generic_baseline_main_names": [str(card.get("name", "")) for card in generic_main],
            "final_main_names": [str(card.get("name", "")) for card in selected],
            "final_extra_names": [str(card.get("name", "")) for card in extra[:15]],
        },
        "generic_report_used_for_fill": {
            "builder_used": generic_report.get("builder_used"),
            "package_counts": generic_report.get("package_counts", {}),
        },
        "reconciled_role_updates": reconciliation.get("proposed_role_updates", {}),
    }


def build_public_baseline_overlay_candidate_deck(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    size: int,
    variant: str | None = "public_baseline_interaction_overlay",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reconciliation = reconcile_specialization_roles(archetype, mode)
    role_map = reconciliation.get("kept_roles", {})
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    normalized_variant = normalize_variant(variant) or "public_baseline_interaction_overlay"
    from deck.builder import build_deck

    public_generic_deck, _pool = build_deck(copy.deepcopy(cards), archetype, mode=mode)
    public_generic_main, public_generic_extra = split_deck(public_generic_deck)
    internal_generic_deck, internal_generic_report = build_generic_deck(archetype, cards, mode=mode, ratio_profile={"payoffs": 3, "max_bricks": 3})
    internal_generic_main, internal_generic_extra = split_deck(internal_generic_deck)
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    package_counts: Counter[str] = Counter()
    interaction_rejected: list[str] = []
    interaction_rejection_reasons: list[str] = []
    interaction_stage_selected_names: list[str] = []
    quota_stage_selected_names: list[str] = []
    generic_fill_stage_selected_names: list[str] = []

    for name in INTERACTION_CORE:
        card = lookup.get(name)
        public_copies = sum(1 for generic_card in public_generic_main if str(generic_card.get("name", "")) == name)
        original_public_copies = public_copies
        selected_before = package_counts["preserved_interaction"]
        while card and public_copies > 0 and add_legal_copy(selected, counts, card):
            public_copies -= 1
            package_counts["preserved_interaction"] += 1
            interaction_stage_selected_names.append(str(card.get("name", "")))
        selected_for_card = package_counts["preserved_interaction"] - selected_before
        if selected_for_card <= 0:
            interaction_rejected.append(name)
            if not card:
                interaction_rejection_reasons.append(f"{name}: card unavailable in pool")
            elif get_card_limit(card) <= 0:
                interaction_rejection_reasons.append(f"{name}: blocked by custom/banlist limit")
            elif original_public_copies <= 0:
                interaction_rejection_reasons.append(f"{name}: absent from public generic baseline main deck")
            else:
                interaction_rejection_reasons.append(f"{name}: legal copy limit prevented preservation")

    softened_targets = public_overlay_quota_targets(normalized_variant)
    for role in ("starters", "extenders", "interruptions", "board_breakers", "payoffs"):
        target = softened_targets.get(role, 0)
        for name in role_map.get(role, []) or []:
            card = lookup.get(name)
            if card and is_extra_deck_card(card):
                continue
            while card and package_counts[role] < target and add_legal_copy(selected, counts, card):
                package_counts[role] += 1
                quota_stage_selected_names.append(str(card.get("name", "")))
            if package_counts[role] >= target:
                break

    archetype_fill_stage_selected_names: list[str] = []
    if normalized_variant in PUBLIC_OVERLAY_TUNING_VARIANTS:
        for card in public_overlay_archetype_fill_candidates(
            normalized_variant,
            archetype,
            public_generic_main,
            internal_generic_main,
            cards,
        ):
            if len(selected) >= size:
                break
            if add_legal_copy(selected, counts, card):
                package_counts["archetype_fill"] += 1
                archetype_fill_stage_selected_names.append(str(card.get("name", "")))

    for card in internal_generic_main:
        if len(selected) >= size:
            break
        if add_legal_copy(selected, counts, card):
            package_counts["generic_fill"] += 1
            generic_fill_stage_selected_names.append(str(card.get("name", "")))
    selected = selected[:size]
    h_variant_status: dict[str, Any] | None = None
    if normalized_variant == "public_overlay_restore_overlap_reduce_preparations":
        h_variant_status = restore_overlap_reduce_preparations(selected, counts, lookup)
        if h_variant_status.get("applied"):
            package_counts["h_restore_overlap"] += 1

    extra = []
    extra_counts: Counter[str] = Counter()
    payoff_added = 0
    for name in role_map.get("extra_deck_preferences", []) or []:
        if payoff_added >= 2:
            break
        card = lookup.get(name)
        if card and is_extra_deck_card(card) and add_legal_copy(extra, extra_counts, card):
            payoff_added += 1
    for card in public_generic_extra or internal_generic_extra:
        if len(extra) >= 15:
            break
        add_legal_copy(extra, extra_counts, card)
    deck = selected + extra[:15]
    return deck, {
        "package_counts": dict(sorted(package_counts.items())),
        "quota_warnings": [],
        "safe_filler_used_count": 0,
        "repair_used": False,
        "repair_success": True,
        "repair_action_count": 0,
        "interaction_preservation_attempted": True,
        "interaction_candidates_selected": int(package_counts.get("preserved_interaction", 0) or 0),
        "interaction_candidates_rejected": interaction_rejected,
        "interaction_rejection_reasons": interaction_rejection_reasons,
        "interaction_trace_metadata": {
            "quota_stage_selected_names": quota_stage_selected_names,
            "interaction_preservation_stage_selected_names": interaction_stage_selected_names,
            "interaction_preservation_stage_rejected_names": interaction_rejected,
            "interaction_preservation_stage_rejection_reasons": interaction_rejection_reasons,
            "archetype_fill_stage_selected_names": archetype_fill_stage_selected_names,
            "generic_fill_stage_selected_names": generic_fill_stage_selected_names,
            "public_generic_baseline_main_names": [str(card.get("name", "")) for card in public_generic_main],
            "internal_generic_baseline_main_names": [str(card.get("name", "")) for card in internal_generic_main],
            "final_main_names": [str(card.get("name", "")) for card in selected],
            "final_extra_names": [str(card.get("name", "")) for card in extra[:15]],
        },
        "generic_report_used_for_fill": {
            "builder_used": internal_generic_report.get("builder_used"),
            "package_counts": internal_generic_report.get("package_counts", {}),
            "public_baseline_used_for_interaction": True,
            "public_overlay_tuning_variant": normalized_variant,
        },
        "reconciled_role_updates": reconciliation.get("proposed_role_updates", {}),
        "public_overlay_tuning": {
            "variant": normalized_variant,
            "archetype_fill_count": int(package_counts.get("archetype_fill", 0) or 0),
            "generic_fill_count": int(package_counts.get("generic_fill", 0) or 0),
            "interaction_cards_preserved": list(interaction_stage_selected_names),
            "h_variant_status": h_variant_status,
        },
        "h_variant_status": h_variant_status,
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
            "dry_run_variant": is_dry_run_variant(gate_report.get("variant")),
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


def dependency_observation_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "filler_dependency": average_observation(rows, "safe_filler_used_count"),
        "repair_dependency": average_observation(rows, "repair_action_count"),
    }


def measure_candidate_dependencies(
    cards: list[dict[str, Any]],
    archetype: str,
    mode: str,
    variant: str | None,
) -> dict[str, float]:
    try:
        if variant in {"public_baseline_interaction_overlay", *PUBLIC_OVERLAY_TUNING_VARIANTS}:
            _deck, report = build_public_baseline_overlay_candidate_deck(cards, archetype, mode, 40, variant=variant)
        elif variant == "hybrid_generic_interaction_overlay":
            _deck, report = build_hybrid_overlay_candidate_deck(cards, archetype, mode, 40)
        else:
            _deck, report = build_candidate_deck(cards, archetype, mode, 40)
    except Exception:
        return {"filler_dependency": 9999.0, "repair_dependency": 9999.0}
    return {
        "filler_dependency": round(float(report.get("safe_filler_used_count", 0) or 0), 4),
        "repair_dependency": round(float(report.get("repair_action_count", 0) or 0), 4),
    }


def dependency_gate_report(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_filler = round(float(baseline.get("filler_dependency", 0) or 0), 4)
    baseline_repair = round(float(baseline.get("repair_dependency", 0) or 0), 4)
    candidate_filler = round(float(candidate.get("filler_dependency", 0) or 0), 4)
    candidate_repair = round(float(candidate.get("repair_dependency", 0) or 0), 4)
    gates = [
        {
            "name": "filler_dependency_gate",
            "baseline_value": baseline_filler,
            "candidate_value": candidate_filler,
            "comparison": f"{candidate_filler} > {baseline_filler}",
            "triggered": candidate_filler > baseline_filler,
            "failure": "filler dependency increased versus generic",
        },
        {
            "name": "repair_dependency_gate",
            "baseline_value": baseline_repair,
            "candidate_value": candidate_repair,
            "comparison": f"{candidate_repair} > {baseline_repair}",
            "triggered": candidate_repair > baseline_repair,
            "failure": "repair dependency increased versus generic",
        },
    ]
    return {
        "baseline": {"filler_dependency": baseline_filler, "repair_dependency": baseline_repair},
        "candidate": {"filler_dependency": candidate_filler, "repair_dependency": candidate_repair},
        "gates": gates,
        "failures": [gate["failure"] for gate in gates if gate["triggered"]],
    }


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


def is_dry_run_variant(variant: str | None) -> bool:
    return normalize_variant(variant) in {"hybrid_generic_interaction_overlay", "public_baseline_interaction_overlay", *PUBLIC_OVERLAY_TUNING_VARIANTS}


def public_overlay_quota_targets(variant: str | None) -> dict[str, int]:
    if variant in {"public_overlay_reduce_generic_fill", "public_overlay_restore_overlap_reduce_preparations"}:
        return {
            "starters": 11,
            "extenders": 9,
            "interruptions": 6,
            "board_breakers": 2,
            "payoffs": 2,
        }
    if variant == "public_overlay_archetype_fill_priority":
        return {
            "starters": 10,
            "extenders": 8,
            "interruptions": 6,
            "board_breakers": 2,
            "payoffs": 2,
        }
    if variant == "public_overlay_interaction_plus_archetype_core":
        return {
            "starters": 8,
            "extenders": 6,
            "interruptions": 4,
            "board_breakers": 1,
            "payoffs": 1,
        }
    return {
        "starters": 10,
        "extenders": 9,
        "interruptions": 6,
        "board_breakers": 2,
        "payoffs": 2,
    }


def public_overlay_archetype_fill_candidates(
    variant: str,
    archetype: str,
    public_generic_main: list[dict[str, Any]],
    internal_generic_main: list[dict[str, Any]],
    cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    public_names = {str(card.get("name", "")) for card in public_generic_main}
    pools: list[list[dict[str, Any]]]
    if variant == "public_overlay_interaction_plus_archetype_core":
        pools = [public_generic_main, internal_generic_main, cards]
    elif variant == "public_overlay_archetype_fill_priority":
        pools = [public_generic_main, internal_generic_main]
    else:
        pools = [internal_generic_main, public_generic_main]
    candidates: list[dict[str, Any]] = []
    for pool in pools:
        for card in pool:
            name = str(card.get("name", ""))
            if not name or name in INTERACTION_CORE or is_extra_deck_card(card):
                continue
            if not is_archetype_card(card, archetype):
                continue
            if variant == "public_overlay_interaction_plus_archetype_core" and pool is cards and name not in public_names:
                continue
            candidates.append(card)
    return candidates


def is_archetype_card(card: dict[str, Any], archetype: str) -> bool:
    haystack = f"{card.get('name', '')} {card.get('desc', '')} {card.get('archetype', '')}".casefold()
    return archetype.casefold() in haystack


def restore_overlap_reduce_preparations(selected: list[dict[str, Any]], counts: Counter[str], lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    add_name = "Kashtira Overlap"
    remove_name = "Kashtira Preparations"
    status = {"applied": False, "add_card": add_name, "remove_card": remove_name, "reason": None}
    remove_index = next((index for index, card in enumerate(selected) if str(card.get("name", "")) == remove_name), None)
    add_card = lookup.get(add_name)
    if remove_index is None:
        status["reason"] = f"remove card absent: {remove_name}"
        return status
    if not add_card:
        status["reason"] = f"add card unavailable: {add_name}"
        return status
    if get_card_limit(add_card) <= 0:
        status["reason"] = f"add card blocked: {add_name}"
        return status
    counts[remove_name] -= 1
    if counts[add_name] >= get_card_limit(add_card):
        counts[remove_name] += 1
        status["reason"] = f"copy limit prevents adding: {add_name}"
        return status
    selected[remove_index] = add_card
    counts[add_name] += 1
    status["applied"] = True
    status["reason"] = "applied"
    return status
