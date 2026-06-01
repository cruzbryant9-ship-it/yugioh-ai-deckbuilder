from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchupProfile:
    name: str
    expected_interruption_density: float
    expected_board_strength: float
    graveyard_dependency: float
    backrow_density: float
    spell_trap_density: float
    monster_effect_density: float
    going_first_priorities: tuple[str, ...]
    going_second_priorities: tuple[str, ...]
    high_value_side_cards: tuple[str, ...]
    low_value_cards: tuple[str, ...]
    risk_factors: tuple[str, ...]


MATCHUP_PROFILES: dict[str, MatchupProfile] = {
    "combo": MatchupProfile("combo", 0.8, 0.9, 0.4, 0.2, 0.4, 0.9, ("hand traps", "turn-ending traps"), ("board breakers", "hand traps"), ("Ash Blossom", "Droll & Lock Bird", "Nibiru", "Infinite Impermanence", "Effect Veiler", "Dark Ruler No More", "Evenly Matched"), ("slow traps",), ("explosive endboards", "monster effect chains")),
    "control": MatchupProfile("control", 0.5, 0.5, 0.3, 0.8, 0.8, 0.5, ("sticky threats", "backrow protection"), ("backrow removal", "grind cards"), ("Harpie's Feather Duster", "Lightning Storm", "Evenly Matched", "Cosmic Cyclone", "Solemn Judgment"), ("narrow hand traps",), ("long games", "trap density")),
    "stun": MatchupProfile("stun", 0.4, 0.4, 0.1, 0.9, 0.9, 0.3, ("spell/trap answers", "protection"), ("mass removal", "board breakers"), ("Harpie's Feather Duster", "Lightning Storm", "Evenly Matched", "Dark Ruler No More", "Book of Eclipse"), ("combo-only extenders",), ("floodgates", "normal summon denial")),
    "graveyard": MatchupProfile("graveyard", 0.6, 0.7, 0.9, 0.3, 0.4, 0.7, ("graveyard hate", "banish disruption"), ("graveyard hate", "board breakers"), ("D.D. Crow", "Ghost Belle & Haunted Mansion", "Called by the Grave", "Dimension Shifter", "Bystial Magnamhut", "Bystial Druiswurm"), ("slow traps",), ("GY recursion", "banish resilience")),
    "backrow": MatchupProfile("backrow", 0.4, 0.4, 0.2, 0.9, 0.9, 0.4, ("trap protection", "grind"), ("backrow removal", "evenly matched"), ("Harpie's Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched", "Red Reboot"), ("monster-only negation",), ("set-five openings", "floodgates")),
    "spell_heavy": MatchupProfile("spell_heavy", 0.5, 0.6, 0.3, 0.4, 0.9, 0.5, ("spell negation", "anti-search"), ("spell/trap disruption",), ("Anti-Spell Fragrance", "Cosmic Cyclone", "Droll & Lock Bird", "Solemn Judgment"), ("battle traps",), ("power spells", "draw engines")),
    "handtrap_heavy": MatchupProfile("handtrap_heavy", 0.9, 0.5, 0.4, 0.2, 0.3, 0.8, ("extenders", "called-by effects"), ("board breakers", "extenders"), ("Called by the Grave", "Crossout Designator", "Triple Tactics Talent", "Book of Eclipse"), ("fragile one-card lines",), ("multiple hand traps", "low commitment disruption")),
    "board_breaker_heavy": MatchupProfile("board_breaker_heavy", 0.3, 0.8, 0.3, 0.4, 0.7, 0.5, ("layered interaction", "floating threats"), ("OTK pressure",), ("Solemn Judgment", "The Ultimate Creature of Destruction", "Blue-Eyes Jet Dragon", "True Light"), ("all-in boards",), ("Dark Ruler", "Evenly Matched")),
    "light_dark": MatchupProfile("light_dark", 0.6, 0.7, 0.7, 0.3, 0.4, 0.8, ("banish disruption",), ("bystial pressure",), ("Bystial Magnamhut", "Bystial Druiswurm", "D.D. Crow", "Called by the Grave"), ("attribute-locked tech",), ("LIGHT/DARK graveyard value")),
    "unknown_meta": MatchupProfile("unknown_meta", 0.6, 0.6, 0.5, 0.5, 0.5, 0.6, ("balanced interaction",), ("flexible breakers",), ("Ash Blossom", "Infinite Impermanence", "D.D. Crow", "Harpie's Feather Duster", "Evenly Matched", "Book of Eclipse"), ("narrow silver bullets",), ("unknown threats",)),
}


def get_matchup_profile(name: str | None) -> MatchupProfile:
    return MATCHUP_PROFILES.get(str(name or "unknown_meta").casefold(), MATCHUP_PROFILES["unknown_meta"])


def list_matchup_names() -> tuple[str, ...]:
    return tuple(MATCHUP_PROFILES)
