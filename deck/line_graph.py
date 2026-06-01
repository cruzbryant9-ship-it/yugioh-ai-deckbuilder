from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LineNode:
    name: str
    action_type: str
    requires_cards: tuple[str, ...] = ()
    requires_zones: tuple[str, ...] = ()
    produces_cards: tuple[str, ...] = ()
    moves_cards: tuple[tuple[str, str, str], ...] = ()
    consumes_cards: tuple[str, ...] = ()
    once_per_turn_tag: str | None = None
    normal_summon_required: bool = False
    locks_applied: tuple[str, ...] = ()
    interruption_points: tuple[str, ...] = ()
    payoff_score: float = 0.0
    from_location: str | None = None
    to_location: str | None = None
    card: str | None = None
    cards: tuple[str, ...] = ()
    required_materials: tuple[str, ...] = ()
    typed_materials: tuple[dict[str, Any], ...] = ()
    produced_materials: tuple[str, ...] = ()
    search_card: str | None = None
    summon_card: str | None = None
    summon_type: str | None = None
    extra_deck_card: str | None = None
    cost_cards: tuple[str, ...] = ()
    sends_to_gy: tuple[str, ...] = ()
    consumes_materials: tuple[str, ...] = ()
    material_location: str = "hand"
    ritual_spell: str | None = None
    ritual_level_requirement: int | None = None
    fusion_materials: tuple[dict[str, Any], ...] = ()
    synchro_requirements: tuple[dict[str, Any], ...] = ()
    link_requirements: tuple[dict[str, Any], ...] = ()
    xyz_requirements: tuple[dict[str, Any], ...] = ()
    xyz_material_count: int | None = None
    link_material_count: int | None = None
    named_materials: tuple[dict[str, Any], ...] = ()
    generic_materials: tuple[dict[str, Any], ...] = ()
    requires_in_deck: tuple[str, ...] = ()
    requires_in_extra: tuple[str, ...] = ()
    produces_to_field: tuple[str, ...] = ()
    produces_to_gy: tuple[str, ...] = ()
    costs: tuple[dict[str, Any], ...] = ()
    conditions: tuple[dict[str, Any], ...] = ()
    parsed_card_text_source: str | None = None
    branches: tuple[dict[str, Any], ...] = ()
    opens_chain: bool = False
    response_window: bool = False
    vulnerable_to: tuple[str, ...] = ()
    protected_by: tuple[str, ...] = ()
    on_negated: tuple[dict[str, Any], ...] = ()
    recovery_routes: tuple[str, ...] = ()
    interruption_penalty: float = 0.0
    bait_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action_type": self.action_type,
            "requires_cards": list(self.requires_cards),
            "requires_zones": list(self.requires_zones),
            "produces_cards": list(self.produces_cards),
            "moves_cards": [list(move) for move in self.moves_cards],
            "consumes_cards": list(self.consumes_cards),
            "once_per_turn_tag": self.once_per_turn_tag,
            "normal_summon_required": self.normal_summon_required,
            "locks_applied": list(self.locks_applied),
            "interruption_points": list(self.interruption_points),
            "payoff_score": self.payoff_score,
            "from_location": self.from_location,
            "to_location": self.to_location,
            "card": self.card,
            "cards": list(self.cards),
            "required_materials": list(self.required_materials),
            "typed_materials": list(self.typed_materials),
            "produced_materials": list(self.produced_materials),
            "search_card": self.search_card,
            "summon_card": self.summon_card,
            "summon_type": self.summon_type,
            "extra_deck_card": self.extra_deck_card,
            "cost_cards": list(self.cost_cards),
            "sends_to_gy": list(self.sends_to_gy),
            "consumes_materials": list(self.consumes_materials),
            "material_location": self.material_location,
            "ritual_spell": self.ritual_spell,
            "ritual_level_requirement": self.ritual_level_requirement,
            "fusion_materials": list(self.fusion_materials),
            "synchro_requirements": list(self.synchro_requirements),
            "link_requirements": list(self.link_requirements),
            "xyz_requirements": list(self.xyz_requirements),
            "xyz_material_count": self.xyz_material_count,
            "link_material_count": self.link_material_count,
            "named_materials": list(self.named_materials),
            "generic_materials": list(self.generic_materials),
            "requires_in_deck": list(self.requires_in_deck),
            "requires_in_extra": list(self.requires_in_extra),
            "produces_to_field": list(self.produces_to_field),
            "produces_to_gy": list(self.produces_to_gy),
            "costs": list(self.costs),
            "conditions": list(self.conditions),
            "parsed_card_text_source": self.parsed_card_text_source,
            "branches": list(self.branches),
            "opens_chain": self.opens_chain,
            "response_window": self.response_window,
            "vulnerable_to": list(self.vulnerable_to),
            "protected_by": list(self.protected_by),
            "on_negated": list(self.on_negated),
            "recovery_routes": list(self.recovery_routes),
            "interruption_penalty": self.interruption_penalty,
            "bait_value": self.bait_value,
        }


@dataclass(frozen=True)
class LineGraph:
    name: str
    archetype: str
    nodes: tuple[LineNode, ...]
    endboard: tuple[str, ...] = ()
    recovery_options: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "nodes": [node.to_dict() for node in self.nodes],
            "endboard": list(self.endboard),
            "recovery_options": list(self.recovery_options),
        }


BLUE_EYES_LINE_GRAPHS: tuple[LineGraph, ...] = (
    LineGraph(
        "Sage + White Stone -> Spirit Dragon",
        "Blue-Eyes",
        (
            LineNode("Normal Sage", "opener", ("Sage with Eyes of Blue",), ("normal_summon",), ("The White Stone of Ancients",), normal_summon_required=True, once_per_turn_tag="sage_search", interruption_points=("Veiler/Imperm on Sage",), payoff_score=1.5, summon_card="Sage with Eyes of Blue", summon_type="normal", search_card="The White Stone of Ancients", requires_in_deck=("The White Stone of Ancients",), opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom", "Infinite Impermanence", "Effect Veiler", "Droll & Lock Bird"), recovery_routes=("Bingo Machine, Go!!!", "Wishes for Eyes of Blue"), interruption_penalty=1.2, bait_value=0.6),
            LineNode("Stone tuner access", "search", ("The White Stone of Ancients",), produces_cards=("Blue-Eyes White Dragon",), once_per_turn_tag="stone_access", payoff_score=1.2, search_card="Blue-Eyes White Dragon", requires_in_deck=("Blue-Eyes White Dragon",)),
            LineNode("Synchro Spirit", "synchro_summon", ("The White Stone of Ancients", "Blue-Eyes White Dragon"), ("monster_zone",), consumes_cards=("The White Stone of Ancients", "Blue-Eyes White Dragon"), produces_cards=("Blue-Eyes Spirit Dragon",), payoff_score=5.0, required_materials=("The White Stone of Ancients", "Blue-Eyes White Dragon"), consumes_materials=("The White Stone of Ancients", "Blue-Eyes White Dragon"), synchro_requirements=({"tuner": True}, {"level": 8, "non_tuner": True}), material_location="hand", extra_deck_card="Blue-Eyes Spirit Dragon", summon_type="synchro"),
            LineNode("End on Spirit", "endboard", ("Blue-Eyes Spirit Dragon",), payoff_score=2.0),
        ),
        ("Blue-Eyes Spirit Dragon",),
        ("True Light", "Blue-Eyes Jet Dragon"),
    ),
    LineGraph(
        "Dictator setup -> Blue-Eyes access",
        "Blue-Eyes",
        (
            LineNode("Reveal/send for Dictator", "send_to_gy", ("Dictator of D.",), produces_cards=("Blue-Eyes access",), once_per_turn_tag="dictator_send", payoff_score=1.5, costs=({"type": "send_to_gy", "from": "deck", "requirement": {"name": "Blue-Eyes White Dragon"}},), branches=({"name": "send Blue-Eyes setup", "effects": ({"type": "mark_setup", "card": "Blue-Eyes White Dragon"},), "score": 3.0},), opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom", "Infinite Impermanence", "Effect Veiler", "D.D. Crow"), recovery_routes=("Bingo Machine, Go!!!", "True Light"), interruption_penalty=1.3, bait_value=0.8),
            LineNode("Special Dictator", "special_summon", ("Dictator of D.",), ("monster_zone",), produces_cards=("Blue-Eyes access",), once_per_turn_tag="dictator_summon", payoff_score=2.5, summon_card="Dictator of D.", summon_type="special", conditions=({"type": "was_sent_to_gy_this_turn", "card_name": "Blue-Eyes White Dragon"},)),
            LineNode("Setup follow-up", "follow_up", ("Blue-Eyes access",), produces_cards=("Blue-Eyes follow-up",), payoff_score=1.5),
        ),
        ("Blue-Eyes access",),
        ("Bingo Machine, Go!!!", "True Light"),
    ),
    LineGraph("Bingo Machine -> search line", "Blue-Eyes", (LineNode("Activate Bingo", "search", ("Bingo Machine, Go!!!",), produces_cards=("Blue-Eyes search target",), consumes_cards=("Bingo Machine, Go!!!",), once_per_turn_tag="bingo_machine", interruption_points=("Ash/Droll on Bingo",), payoff_score=4.0, cost_cards=("Bingo Machine, Go!!!",), branches=({"name": "search starter", "effects": ({"type": "search", "card": "Sage with Eyes of Blue"},), "score": 5.0}, {"name": "search payoff", "effects": ({"type": "search", "card": "Blue-Eyes Alternative White Dragon"},), "score": 7.0}, {"name": "search follow-up", "effects": ({"type": "search", "card": "True Light"},), "score": 4.0}), opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom", "Droll & Lock Bird"), recovery_routes=("Wishes for Eyes of Blue", "Dictator of D."), interruption_penalty=1.5, bait_value=1.0), LineNode("Convert search", "follow_up", ("Blue-Eyes search target",), payoff_score=1.5)), ("line access",), ("Sage with Eyes of Blue",)),
    LineGraph("Wishes for Eyes -> access line", "Blue-Eyes", (LineNode("Activate Wishes", "search", ("Wishes for Eyes of Blue",), produces_cards=("Sage with Eyes of Blue", "Blue-Eyes White Dragon"), once_per_turn_tag="wishes_for_eyes", interruption_points=("Ash/Droll on Wishes",), payoff_score=4.2, cost_cards=("Wishes for Eyes of Blue",), branches=({"name": "starter access", "effects": ({"type": "search", "card": "Sage with Eyes of Blue"},), "score": 6.0}, {"name": "Blue-Eyes access", "effects": ({"type": "search", "card": "Blue-Eyes White Dragon"},), "score": 5.0}), opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom", "Droll & Lock Bird"), recovery_routes=("Bingo Machine, Go!!!",), interruption_penalty=1.4, bait_value=0.8),), ("starter access",), ("Bingo Machine, Go!!!",)),
    LineGraph("True Light + Jet loop", "Blue-Eyes", (LineNode("Set True Light", "set_trap", ("True Light",), produces_cards=("True Light live",), once_per_turn_tag="true_light_set", payoff_score=1.8, produces_to_field=("True Light",), branches=({"name": "set support", "effects": ({"type": "activate", "card": "True Light"},), "score": 3.0},)), LineNode("Access Jet", "special_summon", ("True Light live", "Blue-Eyes Jet Dragon"), ("monster_zone",), produces_cards=("Blue-Eyes Jet Dragon"), once_per_turn_tag="jet_dragon_protection", payoff_score=4.0, summon_card="Blue-Eyes Jet Dragon", summon_type="special", conditions=({"type": "control", "requirement": {"name": "True Light"}},), branches=({"name": "summon Blue-Eyes", "effects": ({"type": "special_summon", "card": "Blue-Eyes Jet Dragon"},), "score": 8.0}, {"name": "set support approximation", "effects": ({"type": "activate", "card": "True Light"},), "score": 4.0}))), ("True Light", "Blue-Eyes Jet Dragon"), ("Blue-Eyes White Dragon",)),
    LineGraph("Chaos Form -> Chaos MAX", "Blue-Eyes", (LineNode("Hold ritual pieces", "ritual_summon", ("Chaos Form", "Blue-Eyes Chaos MAX Dragon"), requires_zones=("hand",), consumes_cards=("Chaos Form",), produces_cards=("Blue-Eyes Chaos MAX Dragon",), once_per_turn_tag="ritual_summon", interruption_points=("Dimensional Barrier",), payoff_score=5.5, required_materials=("Blue-Eyes White Dragon",), consumes_materials=("Blue-Eyes White Dragon",), ritual_spell="Chaos Form", ritual_level_requirement=8, typed_materials=({"level": 8, "monster": True},), material_location="hand", summon_card="Blue-Eyes Chaos MAX Dragon", summon_type="ritual", cost_cards=("Chaos Form",)),), ("Blue-Eyes Chaos MAX Dragon",), ("Bingo Machine, Go!!!",)),
    LineGraph("Ultimate Fusion -> fusion pressure", "Blue-Eyes", (LineNode("Activate Ultimate Fusion", "fusion_summon", ("Ultimate Fusion",), requires_zones=("spell_trap_zone",), consumes_cards=("Ultimate Fusion",), produces_cards=("Blue-Eyes fusion payoff",), once_per_turn_tag="ultimate_fusion", interruption_points=("Ash/Cosmic on Fusion",), payoff_score=4.8, required_materials=("Blue-Eyes White Dragon",), consumes_materials=("Blue-Eyes White Dragon",), named_materials=({"name": "Blue-Eyes White Dragon"},), generic_materials=({"blue_eyes": True, "monster": True},), material_location="hand", extra_deck_card="Blue-Eyes Tyrant Dragon", summon_type="fusion", cost_cards=("Ultimate Fusion",)),), ("Blue-Eyes fusion payoff",), ("True Light", "Blue-Eyes Jet Dragon")),
    LineGraph("Abyss Dragon follow-up", "Blue-Eyes", (LineNode("Resolve Abyss", "follow_up", ("Blue-Eyes Abyss Dragon",), produces_cards=("Chaos Form", "Blue-Eyes Chaos MAX Dragon"), once_per_turn_tag="abyss_dragon_search", interruption_points=("Ash on Abyss",), payoff_score=4.2, conditions=({"type": "control", "requirement": {"blue_eyes": True}},), branches=({"name": "ritual follow-up", "effects": ({"type": "search", "card": "Chaos Form"}, {"type": "search", "card": "Blue-Eyes Chaos MAX Dragon"}), "score": 7.0}, {"name": "fusion follow-up", "effects": ({"type": "search", "card": "Ultimate Fusion"},), "score": 5.0}), opens_chain=True, response_window=True, vulnerable_to=("Ash Blossom", "Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler"), recovery_routes=("True Light",), interruption_penalty=1.6, bait_value=0.7),), ("follow-up search",), ("Ultimate Fusion",)),
    LineGraph("Alternative White Dragon pressure", "Blue-Eyes", (LineNode("Reveal Blue-Eyes", "special_summon", ("Blue-Eyes Alternative White Dragon",), requires_zones=("monster_zone",), produces_cards=("Blue-Eyes Alternative White Dragon",), once_per_turn_tag="alternative_summon", payoff_score=3.0, summon_card="Blue-Eyes Alternative White Dragon", summon_type="special", costs=({"type": "reveal", "requirement": {"name": "Blue-Eyes White Dragon"}},)), LineNode("Destroy pressure", "endboard", ("Blue-Eyes Alternative White Dragon",), once_per_turn_tag="alternative_destroy", interruption_points=("Veiler/Imperm on Alternative",), payoff_score=2.2)), ("Blue-Eyes Alternative White Dragon",), ("True Light",)),
)


def line_graphs_for_archetype(archetype: str) -> list[LineGraph]:
    key = archetype.casefold()
    return [graph for graph in BLUE_EYES_LINE_GRAPHS if key in graph.archetype.casefold()]
