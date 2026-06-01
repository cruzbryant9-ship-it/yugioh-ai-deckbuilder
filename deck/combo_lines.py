from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ComboLine:
    """Structured description of a playable line the simulator can detect."""

    name: str
    archetype: str
    required_cards: tuple[str, ...] = ()
    optional_cards: tuple[str, ...] = ()
    starter_cards: tuple[str, ...] = ()
    extender_cards: tuple[str, ...] = ()
    searched_cards: tuple[str, ...] = ()
    search_targets: tuple[str, ...] = ()
    normal_summon_required: bool = False
    once_per_turn_tags: tuple[str, ...] = ()
    locks: tuple[str, ...] = ()
    endboard: tuple[str, ...] = ()
    interruptions: tuple[str, ...] = ()
    follow_up: tuple[str, ...] = ()
    weak_to: tuple[str, ...] = ()
    recovery_routes: tuple[str, ...] = ()
    brick_risk: float = 0.0
    score: float = 0.0
    line_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "required_cards": list(self.required_cards),
            "optional_cards": list(self.optional_cards),
            "starter_cards": list(self.starter_cards),
            "extender_cards": list(self.extender_cards),
            "searched_cards": list(self.searched_cards),
            "search_targets": list(self.search_targets),
            "normal_summon_required": self.normal_summon_required,
            "once_per_turn_tags": list(self.once_per_turn_tags),
            "locks": list(self.locks),
            "endboard": list(self.endboard),
            "interruptions": list(self.interruptions),
            "follow_up": list(self.follow_up),
            "weak_to": list(self.weak_to),
            "recovery_routes": list(self.recovery_routes),
            "brick_risk": self.brick_risk,
            "score": self.score,
            "line_score": self.effective_score,
        }

    @property
    def effective_score(self) -> float:
        return self.score if self.line_score is None else self.line_score


BLUE_EYES_COMBO_LINES: tuple[ComboLine, ...] = (
    ComboLine(
        name="Sage + White Stone -> Blue-Eyes Spirit Dragon",
        archetype="Blue-Eyes",
        required_cards=("Sage with Eyes of Blue",),
        optional_cards=("The White Stone of Ancients", "The White Stone of Legend"),
        starter_cards=("Sage with Eyes of Blue",),
        extender_cards=("The White Stone of Ancients", "The White Stone of Legend"),
        searched_cards=("The White Stone of Ancients", "Effect Veiler"),
        search_targets=("Blue-Eyes White Dragon", "Blue-Eyes Spirit Dragon"),
        normal_summon_required=True,
        once_per_turn_tags=("sage_search", "stone_end_phase"),
        endboard=("Blue-Eyes Spirit Dragon",),
        interruptions=("graveyard negate", "synchro tag-out pressure"),
        follow_up=("Blue-Eyes White Dragon", "Blue-Eyes engine access"),
        weak_to=("Effect Veiler", "Infinite Impermanence", "Ash Blossom & Joyous Spring"),
        recovery_routes=("The White Stone of Ancients", "True Light"),
        brick_risk=0.18,
        score=8.4,
        line_score=8.4,
    ),
    ComboLine(
        name="Chaos Form + Chaos MAX -> Chaos MAX pressure",
        archetype="Blue-Eyes",
        required_cards=("Chaos Form", "Blue-Eyes Chaos MAX Dragon"),
        optional_cards=("Blue-Eyes White Dragon", "Blue-Eyes Chaos Dragon"),
        starter_cards=("Chaos Form",),
        extender_cards=("Blue-Eyes White Dragon", "Blue-Eyes Chaos Dragon"),
        searched_cards=("Blue-Eyes Chaos MAX Dragon", "Chaos Form"),
        search_targets=("Blue-Eyes Chaos MAX Dragon", "Chaos Form"),
        normal_summon_required=False,
        once_per_turn_tags=("ritual_summon",),
        locks=("ritual material access required",),
        endboard=("Blue-Eyes Chaos MAX Dragon",),
        interruptions=(),
        follow_up=("Blue-Eyes Chaos Dragon", "ritual follow-up"),
        weak_to=("Droll & Lock Bird", "Dimensional Barrier", "Book of Eclipse"),
        recovery_routes=("Bingo Machine, Go!!!", "The Ultimate Creature of Destruction"),
        brick_risk=0.34,
        score=7.8,
        line_score=7.8,
    ),
    ComboLine(
        name="True Light + Jet Dragon -> Jet protection loop",
        archetype="Blue-Eyes",
        required_cards=("True Light",),
        optional_cards=("Blue-Eyes Jet Dragon", "Blue-Eyes White Dragon"),
        starter_cards=("True Light",),
        extender_cards=("Blue-Eyes Jet Dragon",),
        searched_cards=("Blue-Eyes White Dragon", "Blue-Eyes Jet Dragon"),
        search_targets=("Blue-Eyes White Dragon", "Blue-Eyes Jet Dragon"),
        normal_summon_required=False,
        once_per_turn_tags=("true_light_set_or_summon", "jet_dragon_protection"),
        endboard=("True Light", "Blue-Eyes Jet Dragon"),
        interruptions=("destruction protection", "bounce pressure"),
        follow_up=("recurring Blue-Eyes access",),
        weak_to=("Cosmic Cyclone", "Evenly Matched", "Ash Blossom & Joyous Spring"),
        recovery_routes=("Blue-Eyes Jet Dragon", "The Ultimate Creature of Destruction"),
        brick_risk=0.22,
        score=7.4,
        line_score=7.4,
    ),
    ComboLine(
        name="Dictator of D. + Blue-Eyes access -> setup line",
        archetype="Blue-Eyes",
        required_cards=("Dictator of D.",),
        optional_cards=("Blue-Eyes White Dragon", "The White Stone of Ancients", "The White Stone of Legend"),
        starter_cards=("Dictator of D.",),
        extender_cards=("Blue-Eyes White Dragon", "The White Stone of Ancients", "The White Stone of Legend"),
        searched_cards=("Blue-Eyes White Dragon",),
        search_targets=("Blue-Eyes White Dragon",),
        normal_summon_required=False,
        once_per_turn_tags=("dictator_send", "dictator_summon"),
        endboard=("Blue-Eyes body access",),
        interruptions=(),
        follow_up=("graveyard setup", "Blue-Eyes access"),
        weak_to=("Ash Blossom & Joyous Spring", "D.D. Crow", "Called by the Grave"),
        recovery_routes=("Sage with Eyes of Blue", "Bingo Machine, Go!!!"),
        brick_risk=0.16,
        score=7.1,
        line_score=7.1,
    ),
    ComboLine(
        name="Bingo Machine access -> Blue-Eyes consistency line",
        archetype="Blue-Eyes",
        required_cards=("Bingo Machine, Go!!!",),
        optional_cards=("Blue-Eyes Chaos MAX Dragon", "Chaos Form", "Blue-Eyes Jet Dragon", "True Light"),
        starter_cards=("Bingo Machine, Go!!!",),
        extender_cards=(),
        searched_cards=("Blue-Eyes Chaos MAX Dragon", "Chaos Form", "Blue-Eyes Jet Dragon", "True Light"),
        search_targets=("Blue-Eyes Chaos MAX Dragon", "Chaos Form", "Blue-Eyes Jet Dragon", "True Light"),
        normal_summon_required=False,
        once_per_turn_tags=("bingo_machine",),
        endboard=("line access",),
        interruptions=(),
        follow_up=("search-selected Blue-Eyes card",),
        weak_to=("Ash Blossom & Joyous Spring", "Droll & Lock Bird"),
        recovery_routes=("Sage with Eyes of Blue", "Dictator of D."),
        brick_risk=0.08,
        score=6.8,
        line_score=6.8,
    ),
    ComboLine(
        name="Wishes for Eyes of Blue access line",
        archetype="Blue-Eyes",
        required_cards=("Wishes for Eyes of Blue",),
        optional_cards=("Sage with Eyes of Blue", "The White Stone of Ancients", "Blue-Eyes White Dragon"),
        starter_cards=("Wishes for Eyes of Blue",),
        extender_cards=("The White Stone of Ancients", "Blue-Eyes White Dragon"),
        searched_cards=("Sage with Eyes of Blue", "Blue-Eyes White Dragon"),
        search_targets=("Sage with Eyes of Blue", "Blue-Eyes White Dragon"),
        normal_summon_required=False,
        once_per_turn_tags=("wishes_for_eyes",),
        endboard=("starter access",),
        interruptions=(),
        follow_up=("Blue-Eyes access",),
        weak_to=("Ash Blossom & Joyous Spring", "Droll & Lock Bird"),
        recovery_routes=("Bingo Machine, Go!!!", "Dictator of D."),
        brick_risk=0.1,
        score=7.0,
        line_score=7.0,
    ),
    ComboLine(
        name="Ultimate Fusion pressure line",
        archetype="Blue-Eyes",
        required_cards=("Ultimate Fusion",),
        optional_cards=("Blue-Eyes White Dragon", "Blue-Eyes Alternative White Dragon", "Blue-Eyes Jet Dragon"),
        starter_cards=("Ultimate Fusion",),
        extender_cards=("Blue-Eyes White Dragon", "Blue-Eyes Alternative White Dragon", "Blue-Eyes Jet Dragon"),
        searched_cards=("Blue-Eyes Tyrant Dragon", "Blue-Eyes Alternative Ultimate Dragon"),
        search_targets=("Blue-Eyes Tyrant Dragon", "Blue-Eyes Alternative Ultimate Dragon"),
        normal_summon_required=False,
        once_per_turn_tags=("ultimate_fusion",),
        locks=("fusion material access required",),
        endboard=("Blue-Eyes Tyrant Dragon", "removal pressure"),
        interruptions=("destruction removal",),
        follow_up=("graveyard material recycling",),
        weak_to=("Ash Blossom & Joyous Spring", "Cosmic Cyclone", "D.D. Crow"),
        recovery_routes=("True Light", "Blue-Eyes Jet Dragon"),
        brick_risk=0.2,
        score=7.6,
        line_score=7.6,
    ),
    ComboLine(
        name="Spirit Dragon synchro line",
        archetype="Blue-Eyes",
        required_cards=("The White Stone of Ancients",),
        optional_cards=("Sage with Eyes of Blue", "Blue-Eyes White Dragon", "Dictator of D."),
        starter_cards=("The White Stone of Ancients", "Sage with Eyes of Blue"),
        extender_cards=("Blue-Eyes White Dragon", "Dictator of D."),
        searched_cards=("Blue-Eyes Spirit Dragon",),
        search_targets=("Blue-Eyes Spirit Dragon",),
        normal_summon_required=True,
        once_per_turn_tags=("stone_tuner_line", "spirit_dragon_summon"),
        endboard=("Blue-Eyes Spirit Dragon",),
        interruptions=("graveyard negate",),
        follow_up=("Azure-Eyes style tag-out", "Blue-Eyes access"),
        weak_to=("Effect Veiler", "Infinite Impermanence", "Nibiru, the Primal Being"),
        recovery_routes=("True Light", "Blue-Eyes Jet Dragon"),
        brick_risk=0.16,
        score=8.0,
        line_score=8.0,
    ),
    ComboLine(
        name="Abyss Dragon follow-up line",
        archetype="Blue-Eyes",
        required_cards=("Blue-Eyes Abyss Dragon",),
        optional_cards=("Blue-Eyes White Dragon", "Dictator of D.", "The White Stone of Ancients"),
        starter_cards=("Blue-Eyes Abyss Dragon",),
        extender_cards=("Blue-Eyes White Dragon", "Dictator of D."),
        searched_cards=("Chaos Form", "Polymerization", "Blue-Eyes Chaos MAX Dragon"),
        search_targets=("Chaos Form", "Blue-Eyes Chaos MAX Dragon"),
        normal_summon_required=False,
        once_per_turn_tags=("abyss_dragon_search",),
        endboard=("follow-up search",),
        interruptions=(),
        follow_up=("ritual or fusion access",),
        weak_to=("Ash Blossom & Joyous Spring", "D.D. Crow"),
        recovery_routes=("Bingo Machine, Go!!!", "Ultimate Fusion"),
        brick_risk=0.28,
        score=6.9,
        line_score=6.9,
    ),
    ComboLine(
        name="Alternative White Dragon pressure line",
        archetype="Blue-Eyes",
        required_cards=("Blue-Eyes Alternative White Dragon",),
        optional_cards=("Blue-Eyes White Dragon", "Bingo Machine, Go!!!", "Wishes for Eyes of Blue"),
        starter_cards=("Blue-Eyes Alternative White Dragon",),
        extender_cards=("Blue-Eyes White Dragon",),
        searched_cards=("Blue-Eyes White Dragon",),
        search_targets=("Blue-Eyes White Dragon",),
        normal_summon_required=False,
        once_per_turn_tags=("alternative_summon", "alternative_destroy"),
        endboard=("Blue-Eyes Alternative White Dragon", "rank/synchro pressure"),
        interruptions=("targeted destruction",),
        follow_up=("large body pressure",),
        weak_to=("Book of Moon", "Infinite Impermanence", "Effect Veiler"),
        recovery_routes=("Blue-Eyes Jet Dragon", "True Light"),
        brick_risk=0.2,
        score=7.2,
        line_score=7.2,
    ),
)


COMBO_LINES: tuple[ComboLine, ...] = BLUE_EYES_COMBO_LINES


def combo_lines_for_archetype(archetype: str) -> list[ComboLine]:
    key = archetype.casefold()
    return [line for line in COMBO_LINES if key in line.archetype.casefold()]


def card_names(cards: list[dict[str, Any]]) -> set[str]:
    return {str(card.get("name", "")) for card in cards if card.get("name")}


def line_is_available(line: ComboLine, hand_names: set[str]) -> bool:
    if not set(line.required_cards).issubset(hand_names):
        return False
    if line.optional_cards and not hand_names.intersection(line.optional_cards):
        return False
    return True
