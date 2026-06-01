from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any

from deck.curated_opponent_memory import curated_opponent_name
from deck.opponent_profiles import OpponentProfile


@dataclass(frozen=True)
class OpponentLine:
    opponent_archetype: str
    line_name: str
    starter_cards: tuple[str, ...]
    extender_cards: tuple[str, ...]
    search_cards: tuple[str, ...]
    graveyard_cards: tuple[str, ...]
    field_effect_cards: tuple[str, ...]
    choke_points: tuple[str, ...]
    weak_to: tuple[str, ...]
    recovery_cards: tuple[str, ...]
    endboard: tuple[str, ...]
    line_score: float
    resilience_score: float
    required_cards: tuple[str, ...] = ()
    optional_cards: tuple[str, ...] = ()
    branch_points: tuple[str, ...] = ()
    timing_windows: tuple[str, ...] = ()
    recovery_routes: tuple[str, ...] = ()
    endboard_if_uninterrupted: tuple[str, ...] = ()
    endboard_if_interrupted: tuple[str, ...] = ()
    stop_severity: float = 0.65
    recovery_likelihood: float = 0.45
    recommended_interruptions: tuple[str, ...] = ()


OPPONENT_LINES: dict[str, tuple[OpponentLine, ...]] = {
    "Snake-Eye": (
        OpponentLine(
            "Snake-Eye",
            "Ash or Bonfire into Flamberge setup",
            ("Snake-Eye Ash", "Bonfire", "WANTED: Seeker of Sinful Spoils"),
            ("Snake-Eyes Poplar", "Original Sinful Spoils - Snake-Eye"),
            ("Snake-Eye Ash", "Bonfire", "WANTED: Seeker of Sinful Spoils"),
            ("Snake-Eye Flamberge Dragon", "Promethean Princess, Bestower of Flames"),
            ("Snake-Eye Ash", "Snake-Eyes Poplar", "Flamberge Dragon"),
            ("starter search", "Original Sinful Spoils", "Flamberge resolution", "Promethean Princess revive"),
            ("Ash Blossom", "Droll & Lock Bird", "D.D. Crow", "Ghost Belle", "Infinite Impermanence", "Effect Veiler", "Nibiru"),
            ("Snake-Eyes Poplar", "Diabellstar the Black Witch", "Flamberge Dragon"),
            ("I:P into S:P", "Flamberge recursion", "Promethean Princess follow-up"),
            9.2,
            7.2,
        ),
    ),
    "Tenpai": (
        OpponentLine(
            "Tenpai",
            "Paidra or Sangen into battle OTK",
            ("Tenpai Dragon Paidra", "Sangen Summoning", "Sangen Kaimen"),
            ("Tenpai Dragon Chundra", "Tenpai Dragon Fadra"),
            ("Paidra search", "Sangen Kaimen"),
            (),
            ("Tenpai Dragon Paidra", "Tenpai Dragon Chundra"),
            ("Sangen Summoning", "Paidra search", "battle phase synchro climb"),
            ("Droll & Lock Bird", "Cosmic Cyclone", "Infinite Impermanence", "Effect Veiler", "Book of Eclipse"),
            ("Sangen Kaimen", "Tenpai Dragon Chundra"),
            ("battle phase OTK", "Trident Dragion pressure"),
            8.8,
            6.6,
        ),
    ),
    "Labrynth": (
        OpponentLine(
            "Labrynth",
            "Welcome trap loop",
            ("Arianna the Labrynth Servant", "Big Welcome Labrynth", "Welcome Labrynth"),
            ("Arias the Labrynth Butler", "Lady Labrynth of the Silver Castle"),
            ("Arianna the Labrynth Servant",),
            ("Welcome Labrynth", "Big Welcome Labrynth"),
            ("Arianna the Labrynth Servant", "Lady Labrynth"),
            ("Arianna search", "Welcome activation", "Big Welcome resolution"),
            ("Ash Blossom", "Droll & Lock Bird", "Harpie's Feather Duster", "Lightning Storm", "Cosmic Cyclone", "Evenly Matched"),
            ("Lady Labrynth", "Transaction Rollback"),
            ("recursive trap pressure", "Lady protection"),
            8.0,
            7.4,
        ),
    ),
    "Branded": (
        OpponentLine(
            "Branded",
            "Branded Fusion into Mirrorjade",
            ("Aluber the Jester of Despia", "Branded Fusion", "Branded Opening"),
            ("Cartesia", "Quem", "Branded in Red"),
            ("Aluber the Jester of Despia", "Branded Fusion"),
            ("Albion the Branded Dragon", "Lubellion the Searing Dragon"),
            ("Aluber the Jester of Despia",),
            ("Branded Fusion", "Aluber search", "fusion material send"),
            ("Ash Blossom", "Droll & Lock Bird", "D.D. Crow", "Ghost Belle", "Bystial"),
            ("Branded in Red", "Quem", "Cartesia"),
            ("Mirrorjade banish", "fusion follow-up"),
            8.6,
            7.0,
        ),
    ),
    "Kashtira": (
        OpponentLine(
            "Kashtira",
            "Unicorn or Fenrir into Arise-Heart",
            ("Kashtira Unicorn", "Kashtira Fenrir", "Pressured Planet Wraitsoth"),
            ("Kashtira Birth", "Kashtira Riseheart"),
            ("Kashtira Unicorn", "Pressured Planet Wraitsoth"),
            (),
            ("Kashtira Unicorn", "Kashtira Fenrir", "Kashtira Riseheart"),
            ("Unicorn search", "Birth extension", "Arise-Heart summon"),
            ("Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler", "Book of Eclipse", "Kaiju"),
            ("Kashtira Birth", "Kashtira Riseheart"),
            ("Arise-Heart macro effect", "Fenrir banish"),
            8.2,
            6.8,
        ),
    ),
    "Runick": (
        OpponentLine(
            "Runick",
            "Fountain draw loop",
            ("Runick Tip", "Runick Fountain", "Hugin the Runick Wings"),
            ("Runick Flashing Fire", "Runick Freezing Curses"),
            ("Runick Tip",),
            (),
            ("Hugin the Runick Wings",),
            ("Runick Fountain", "Hugin protection", "Runick Tip"),
            ("Cosmic Cyclone", "Droll & Lock Bird", "Ash Blossom", "Harpie's Feather Duster", "Lightning Storm"),
            ("Runick Fountain", "Hugin the Runick Wings"),
            ("Fountain draw loop", "spell interruption chain"),
            7.7,
            7.5,
        ),
    ),
    "Floowandereeze": (
        OpponentLine(
            "Floowandereeze",
            "Robina normal summon chain",
            ("Floowandereeze & Robina", "Floowandereeze and the Magnificent Map"),
            ("Floowandereeze & Eglen", "Floowandereeze & Toccan"),
            ("Robina search", "Eglen search"),
            (),
            ("Floowandereeze & Robina", "Floowandereeze & Eglen"),
            ("Robina normal summon", "Map activation", "Eglen search"),
            ("Droll & Lock Bird", "Ash Blossom", "Infinite Impermanence", "Effect Veiler", "Book of Eclipse"),
            ("Floowandereeze and the Dreaming Town", "Map"),
            ("Empen floodgate", "Dreaming Town interruption"),
            7.9,
            6.4,
        ),
    ),
    "Tearlaments": (
        OpponentLine(
            "Tearlaments",
            "Mill into fusion recursion",
            ("Tearlaments Reinoheart", "Tearlaments Scheiren", "Tearlaments Havnis"),
            ("Tearlaments Sulliek", "Ishizu cards"),
            ("Reinoheart send",),
            ("Tearlaments names in GY", "Kitkallos"),
            ("Reinoheart", "Kitkallos"),
            ("mill effect", "GY fusion trigger", "Kitkallos resolution"),
            ("D.D. Crow", "Ghost Belle", "Dimension Shifter", "Called by the Grave", "Bystial"),
            ("Tearlaments Sulliek", "Tearlaments Cryme"),
            ("fusion recursion", "Kaleido-Heart pressure"),
            8.9,
            7.8,
        ),
    ),
}


def get_opponent_lines(opponent: str | OpponentProfile | None) -> tuple[OpponentLine, ...]:
    name = curated_opponent_name(opponent)
    if not name and isinstance(opponent, OpponentProfile):
        name = opponent.archetype
    if not name:
        value = str(opponent or "")
        name = value.replace(" curated profile", "")
    return expand_branchable_lines(OPPONENT_LINES.get(str(name), ()))


def list_supported_opponents() -> tuple[str, ...]:
    return tuple(OPPONENT_LINES)


def expand_branchable_lines(lines: tuple[OpponentLine, ...]) -> tuple[OpponentLine, ...]:
    expanded: list[OpponentLine] = []
    for line in lines:
        base = enrich_line(line, "starter", ("starter line", "first choke point"), line.line_score, line.resilience_score)
        expanded.append(base)
        expanded.append(
            enrich_line(
                line,
                "extender",
                ("extender line", "plays through first interruption"),
                max(1.0, line.line_score - 0.6),
                min(10.0, line.resilience_score + 0.5),
                required=line.starter_cards[:1],
                optional=line.extender_cards,
            )
        )
        expanded.append(
            enrich_line(
                line,
                "recovery",
                ("recovery line", "post-interruption pivot"),
                max(1.0, line.line_score - 1.1),
                min(10.0, line.resilience_score + 0.8),
                required=line.recovery_cards[:1],
                optional=line.recovery_cards[1:],
                interrupted_endboard=line.endboard[:1],
            )
        )
        expanded.append(
            enrich_line(
                line,
                "backup",
                ("backup line", "lower ceiling after missed starter"),
                max(1.0, line.line_score - 1.5),
                max(1.0, line.resilience_score - 0.2),
                required=line.extender_cards[:1] or line.starter_cards[:1],
                optional=line.recovery_cards,
                interrupted_endboard=("reduced board",),
            )
        )
        expanded.append(
            enrich_line(
                line,
                "high-roll",
                ("high-roll line", "multiple extender branch"),
                min(10.0, line.line_score + 0.5),
                max(1.0, line.resilience_score - 0.4),
                required=line.starter_cards[:1],
                optional=tuple(dict.fromkeys((*line.extender_cards, *line.search_cards))),
                uninterrupted_endboard=tuple(dict.fromkeys((*line.endboard, "extra interruption"))),
            )
        )
        expanded.append(
            enrich_line(
                line,
                "post-interruption",
                ("post-interruption line", "uses recovery route after stopped starter"),
                max(1.0, line.line_score - 1.8),
                min(10.0, line.resilience_score + 1.0),
                required=line.recovery_cards[:1] or line.extender_cards[:1],
                optional=line.recovery_cards,
                interrupted_endboard=("follow-up only",),
            )
        )
    return tuple(expanded)


def enrich_line(
    line: OpponentLine,
    branch_type: str,
    branch_points: tuple[str, ...],
    line_score: float,
    resilience_score: float,
    required: tuple[str, ...] | None = None,
    optional: tuple[str, ...] | None = None,
    uninterrupted_endboard: tuple[str, ...] | None = None,
    interrupted_endboard: tuple[str, ...] | None = None,
) -> OpponentLine:
    return replace(
        line,
        line_name=f"{line.line_name} ({branch_type})",
        line_score=round(line_score, 2),
        resilience_score=round(resilience_score, 2),
        required_cards=tuple(required if required is not None else line.starter_cards[:1]),
        optional_cards=tuple(optional if optional is not None else line.extender_cards),
        branch_points=branch_points,
        timing_windows=infer_timing_windows(line),
        recovery_routes=line.recovery_cards,
        endboard_if_uninterrupted=tuple(uninterrupted_endboard if uninterrupted_endboard is not None else line.endboard),
        endboard_if_interrupted=tuple(interrupted_endboard if interrupted_endboard is not None else ("reduced pressure", "follow-up only")),
        stop_severity=round(min(0.95, max(0.35, 0.45 + line.line_score / 20)), 4),
        recovery_likelihood=round(min(0.95, max(0.05, resilience_score / 10)), 4),
        recommended_interruptions=line.weak_to,
    )


def infer_timing_windows(line: OpponentLine) -> tuple[str, ...]:
    windows = ["on activation"]
    if line.search_cards:
        windows.extend(["before search resolves", "after search resolves"])
    if line.field_effect_cards:
        windows.extend(["on summon", "on resolution"])
    if line.graveyard_cards:
        windows.append("in GY")
    if line.extender_cards:
        windows.append("before special summon")
    windows.extend(["after material committed", "before endboard established"])
    return tuple(dict.fromkeys(windows))
