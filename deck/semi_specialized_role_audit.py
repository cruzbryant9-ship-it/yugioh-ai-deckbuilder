from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from deck.archetype_role_inference import infer_archetype_roles, infer_card_roles
from deck.archetype_specialization_profiles import load_specialization_profile
from deck.card_metadata import is_extra_deck_monster
from deck.generic_deck_builder import primary_role
from deck.generic_package_extractor import extract_generic_packages
from deck.package_builder import classify_card_package
from deck.semi_specialized_quota_replay import replay_quota_sensitivity
from SystemAIYugioh.card_database import CardDatabase


PROFILE_ROLE_KEYS = (
    "starters",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "bricks_garnets",
    "extra_deck_preferences",
)

ROLE_ALIASES = {
    "starters": "starters_searchers",
    "starter": "starters_searchers",
    "searcher": "starters_searchers",
    "searchers": "starters_searchers",
    "extender": "extenders",
    "payoff": "payoffs",
    "interruption": "interruptions",
    "board_breaker": "board_breakers",
    "garnet_brick": "bricks_garnets",
    "bricks": "bricks_garnets",
    "extra_deck": "extra_deck_payoffs",
    "extra_deck_preferences": "extra_deck_payoffs",
}
CANONICAL_ROLES = (
    "starters_searchers",
    "extenders",
    "payoffs",
    "interruptions",
    "board_breakers",
    "extra_deck_payoffs",
    "bricks_garnets",
)
MAJOR_ROLES = {"payoffs", "interruptions", "extra_deck_payoffs"}


def audit_specialized_roles(archetype: str = "Kashtira", mode: str = "meta") -> dict[str, Any]:
    cards = CardDatabase().load_cards()
    profile = load_specialization_profile(archetype)
    if not profile:
        return empty_audit(archetype, mode, "no specialization profile found")
    return audit_profile_roles(profile, cards, archetype, mode)


def audit_profile_roles(
    profile: dict[str, Any],
    cards: list[dict[str, Any]],
    archetype: str = "Kashtira",
    mode: str = "meta",
) -> dict[str, Any]:
    lookup = {str(card.get("name", "")): card for card in cards if card.get("name")}
    generic_analysis = infer_archetype_roles(cards, archetype)
    package_data = extract_generic_packages(cards, archetype)
    profile_assignments = profile_role_assignments(profile)
    package_labels = package_labels_by_card(package_data)
    benchmark_usage = benchmark_package_usage(archetype, mode)
    quota_pressure = quota_replay_pressure(archetype, mode)

    confirmed_roles: dict[str, list[str]] = {role: [] for role in CANONICAL_ROLES}
    role_conflicts: list[dict[str, Any]] = []
    low_confidence: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    agreement_scores: list[float] = []

    for name, profile_roles in sorted(profile_assignments.items()):
        card = lookup.get(name)
        if card:
            generic_card = generic_analysis.get("cards", {}).get(name) or infer_card_roles(card, archetype)
            generic_roles = {normalize_role(role) for role in generic_card.get("roles", [])}
            text_roles = text_signal_roles(card, archetype)
            package_roles = package_signal_roles(card, package_labels)
            usage_count = int(benchmark_usage.get(name, 0) or 0)
            confidence = float(generic_card.get("confidence", 0) or 0)
        else:
            generic_roles = set()
            text_roles = set()
            package_roles = set()
            usage_count = 0
            confidence = 0.0
        evidence_roles = set(generic_roles) | set(text_roles) | set(package_roles)
        for role in profile_roles:
            supported = role_supported(role, evidence_roles, card)
            agreement_scores.append(1.0 if supported else 0.0)
            if supported:
                confirmed_roles.setdefault(role, []).append(name)
            else:
                conflict = conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "profile role lacks supporting generic/text/package signal")
                role_conflicts.append(conflict)
                if conflict["severity"] == "major":
                    needs_review.append(conflict)
            role_conflicts.extend(detect_role_specific_conflicts(name, role, card, generic_roles, text_roles, package_roles, usage_count))
            if confidence < 0.45 or not card:
                low_confidence.append(
                    {
                        "card": name,
                        "profile_role": role,
                        "generic_confidence": round(confidence, 4),
                        "reason": "missing card data" if not card else "generic role confidence below audit threshold",
                    }
                )

    excessive_overlaps = detect_excessive_overlap(profile_assignments)
    role_conflicts.extend(excessive_overlaps)
    needs_review.extend(conflict for conflict in excessive_overlaps if conflict.get("severity") == "major")
    major_conflicts = [conflict for conflict in role_conflicts if conflict.get("severity") == "major"]
    agreement = round(mean(agreement_scores or [0.0]), 4)
    readiness = classify_readiness(agreement, role_conflicts, major_conflicts)
    risk_flags = build_risk_flags(profile, role_conflicts, low_confidence, quota_pressure, readiness)
    return {
        "archetype": archetype,
        "mode": mode,
        "role_agreement_score": agreement,
        "readiness_classification": readiness,
        "role_conflicts": dedupe_conflicts(role_conflicts),
        "low_confidence_assignments": dedupe_conflicts(low_confidence),
        "confirmed_roles": {role: sorted(set(names)) for role, names in confirmed_roles.items() if names},
        "needs_manual_review": dedupe_conflicts(needs_review),
        "evidence": {
            "profile_role_counts": role_counts(profile_assignments),
            "generic_role_counts": generic_analysis.get("role_counts", {}),
            "package_extraction_labels": package_labels,
            "benchmark_package_usage": dict(sorted(benchmark_usage.items())),
            "quota_replay_pressure": quota_pressure,
        },
        "risk_flags": risk_flags,
        "not_activated": True,
    }


def profile_role_assignments(profile: dict[str, Any]) -> dict[str, set[str]]:
    assignments: dict[str, set[str]] = defaultdict(set)
    for role_key in PROFILE_ROLE_KEYS:
        canonical = normalize_role(role_key)
        for name in profile.get(role_key, []) or []:
            assignments[str(name)].add(canonical)
    return dict(assignments)


def package_labels_by_card(package_data: dict[str, Any]) -> dict[str, list[str]]:
    labels: dict[str, set[str]] = defaultdict(set)
    analysis_roles = package_data.get("analysis", {}).get("roles", {}) if isinstance(package_data.get("analysis"), dict) else {}
    for role, names in analysis_roles.items():
        for name in names or []:
            labels[str(name)].add(normalize_role(str(role)))
    for package in package_data.get("packages", []) or []:
        role = normalize_role(str(package.get("package_type", "")))
        for name in package.get("card_names", []) or []:
            labels[str(name)].add(role)
    return {name: sorted(values) for name, values in labels.items()}


def text_signal_roles(card: dict[str, Any], archetype: str) -> set[str]:
    inferred = infer_card_roles(card, archetype)
    roles = {normalize_role(role) for role in inferred.get("roles", [])}
    package_role = normalize_role(classify_card_package(card))
    if package_role:
        roles.add(package_role)
    primary = normalize_role(primary_role(card))
    if primary:
        roles.add(primary)
    if is_extra_deck_monster(card):
        roles.add("extra_deck_payoffs")
        roles.add("payoffs")
    return roles


def package_signal_roles(card: dict[str, Any], labels: dict[str, list[str]]) -> set[str]:
    roles = set(labels.get(str(card.get("name", "")), []))
    package_role = normalize_role(classify_card_package(card))
    if package_role:
        roles.add(package_role)
    return roles


def role_supported(role: str, evidence_roles: set[str], card: dict[str, Any] | None) -> bool:
    if role in evidence_roles:
        return True
    if role == "extra_deck_payoffs" and card and is_extra_deck_monster(card):
        return True
    if role == "interruptions" and "board_breakers" in evidence_roles:
        return True
    if role == "board_breakers" and "interruptions" in evidence_roles and not archetype_card(card):
        return True
    if role == "starters_searchers" and "extenders" in evidence_roles:
        return False
    return False


def detect_role_specific_conflicts(
    name: str,
    role: str,
    card: dict[str, Any] | None,
    generic_roles: set[str],
    text_roles: set[str],
    package_roles: set[str],
    usage_count: int,
) -> list[dict[str, Any]]:
    conflicts = []
    evidence_roles = set(generic_roles) | set(text_roles) | set(package_roles)
    if role == "payoffs" and "extenders" in generic_roles and "payoffs" not in generic_roles:
        conflicts.append(conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "profile payoff but generic inference sees extender"))
    if role == "interruptions" and "interruptions" not in evidence_roles:
        conflicts.append(conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "profile interruption but no interruption signal exists"))
    if role == "board_breakers" and archetype_card(card) and "board_breakers" not in generic_roles:
        conflicts.append(conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "profile board breaker appears engine-only"))
    if role == "extra_deck_payoffs" and (not card or not is_extra_deck_monster(card)):
        conflicts.append(conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "Extra Deck payoff tag is unsupported by card metadata"))
    if role == "bricks_garnets" and usage_count >= 3:
        conflicts.append(conflict_row(name, role, generic_roles, text_roles, package_roles, usage_count, "brick/garnet tag conflicts with high benchmark usage"))
    return conflicts


def detect_excessive_overlap(assignments: dict[str, set[str]]) -> list[dict[str, Any]]:
    conflicts = []
    for name, roles in assignments.items():
        access_overlap = {"starters_searchers", "extenders"} & roles
        if len(access_overlap) == 2 and len(roles) >= 3:
            conflicts.append(
                {
                    "card": name,
                    "profile_role": "starters_searchers/extenders",
                    "generic_roles": [],
                    "text_roles": [],
                    "package_roles": [],
                    "benchmark_usage_count": 0,
                    "severity": "minor",
                    "reason": "starter/searcher/extender overlap is excessive",
                }
            )
    return conflicts


def conflict_row(
    name: str,
    role: str,
    generic_roles: set[str],
    text_roles: set[str],
    package_roles: set[str],
    usage_count: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "card": name,
        "profile_role": role,
        "generic_roles": sorted(generic_roles),
        "text_roles": sorted(text_roles),
        "package_roles": sorted(package_roles),
        "benchmark_usage_count": usage_count,
        "severity": "major" if role in MAJOR_ROLES and "overlap" not in reason else "minor",
        "reason": reason,
    }


def benchmark_package_usage(archetype: str, mode: str) -> Counter[str]:
    try:
        replay = replay_quota_sensitivity(archetype, mode, runs=2, movement_strengths=(0.0,))
    except Exception:
        return Counter()
    usage: Counter[str] = Counter()
    for row in replay.get("run_observations", []) or []:
        for name, count in Counter(row.get("main_card_names", []) or []).items():
            usage[name] += count
    return usage


def quota_replay_pressure(archetype: str, mode: str) -> dict[str, Any]:
    try:
        replay = replay_quota_sensitivity(archetype, mode, runs=2)
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    return {
        "available": True,
        "generic_total_gap": replay.get("generic_total_gap"),
        "stability_classification": replay.get("stability_classification"),
        "highest_pressure_roles": sorted(
            (
                {
                    "role": role,
                    "gap": row.get("gap", 0),
                    "absolute_gap": row.get("absolute_gap", 0),
                    "gap_type": row.get("gap_type", "met"),
                }
                for role, row in (replay.get("generic_balance", {}) or {}).items()
            ),
            key=lambda row: float(row.get("absolute_gap", 0) or 0),
            reverse=True,
        )[:4],
    }


def classify_readiness(agreement: float, conflicts: list[dict[str, Any]], major_conflicts: list[dict[str, Any]]) -> str:
    if major_conflicts:
        return "role_unstable"
    if agreement >= 0.82 and not conflicts:
        return "role_safe"
    return "role_safe_with_warnings"


def build_risk_flags(
    profile: dict[str, Any],
    conflicts: list[dict[str, Any]],
    low_confidence: list[dict[str, Any]],
    quota_pressure: dict[str, Any],
    readiness: str,
) -> list[str]:
    flags = list(profile.get("known_risk_flags", []) or [])
    if conflicts:
        flags.append(f"role audit found {len(conflicts)} role conflicts")
    if low_confidence:
        flags.append(f"role audit found {len(low_confidence)} low-confidence assignments")
    if readiness == "role_unstable":
        flags.append("major role conflicts block experimental builder flag")
    if quota_pressure.get("generic_total_gap", 0):
        flags.append(f"quota pressure still present: total gap {quota_pressure.get('generic_total_gap')}")
    return sorted(set(flags))


def normalize_role(role: str) -> str:
    normalized = str(role or "").casefold().replace("-", "_").replace(" ", "_")
    return ROLE_ALIASES.get(normalized, normalized)


def archetype_card(card: dict[str, Any] | None) -> bool:
    if not card:
        return False
    name = str(card.get("name", "")).casefold()
    archetype = str(card.get("archetype", "")).casefold()
    return "kashtira" in name or "kashtira" in archetype


def role_counts(assignments: dict[str, set[str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for roles in assignments.values():
        for role in roles:
            counts[role] += 1
    return dict(sorted(counts.items()))


def dedupe_conflicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for row in rows:
        key = (row.get("card"), row.get("profile_role"), row.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def empty_audit(archetype: str, mode: str, reason: str) -> dict[str, Any]:
    return {
        "archetype": archetype,
        "mode": mode,
        "role_agreement_score": 0.0,
        "readiness_classification": "role_unstable",
        "role_conflicts": [],
        "low_confidence_assignments": [],
        "confirmed_roles": {},
        "needs_manual_review": [{"reason": reason}],
        "risk_flags": [reason],
        "not_activated": True,
    }
