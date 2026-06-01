from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deck.curated_opponent_memory import curated_opponent_name
from deck.opponent_profiles import OpponentProfile


@dataclass(frozen=True)
class OpponentActionNode:
    node_id: str
    action_name: str
    card: str
    action_type: str
    requires_cards: tuple[str, ...] = ()
    produces_cards: tuple[str, ...] = ()
    moves_cards: tuple[str, ...] = ()
    from_location: str = ""
    to_location: str = ""
    opens_chain: bool = True
    response_window: bool = True
    timing_window: str = "on activation"
    vulnerable_to: tuple[str, ...] = ()
    protected_by: tuple[str, ...] = ()
    recovery_routes: tuple[str, ...] = ()
    if_interrupted_go_to: str | None = None
    if_resolved_go_to: str | None = None
    endboard_additions: tuple[str, ...] = ()
    risk_score: float = 0.5
    payoff_score: float = 1.0
    requires_in_hand: tuple[str, ...] = ()
    requires_in_deck: tuple[str, ...] = ()
    requires_on_field: tuple[str, ...] = ()
    requires_in_gy: tuple[str, ...] = ()
    requires_in_extra: tuple[str, ...] = ()
    consumes_from_hand: tuple[str, ...] = ()
    consumes_from_field: tuple[str, ...] = ()
    sends_to_gy: tuple[str, ...] = ()
    searches_from_deck: tuple[str, ...] = ()
    summons_from_hand: tuple[str, ...] = ()
    summons_from_deck: tuple[str, ...] = ()
    summons_from_extra: tuple[str, ...] = ()
    adds_to_hand: tuple[str, ...] = ()
    sets_to_field: tuple[str, ...] = ()
    banishes_from_gy: tuple[str, ...] = ()
    once_per_turn_tag: str = ""
    normal_summon_required: bool = False
    resource_failure_reason: str = ""


@dataclass(frozen=True)
class OpponentBranchGraph:
    opponent_archetype: str
    graph_name: str
    starter_nodes: tuple[str, ...]
    nodes: dict[str, OpponentActionNode]
    terminal_nodes: tuple[str, ...]
    expected_endboard: tuple[str, ...]
    backup_routes: tuple[str, ...]
    choke_nodes: tuple[str, ...]


def node(
    node_id: str,
    action_name: str,
    card: str,
    action_type: str,
    timing_window: str,
    vulnerable_to: tuple[str, ...],
    if_resolved_go_to: str | None,
    if_interrupted_go_to: str | None = None,
    recovery_routes: tuple[str, ...] = (),
    endboard_additions: tuple[str, ...] = (),
    risk_score: float = 0.5,
    payoff_score: float = 1.0,
    from_location: str = "",
    to_location: str = "",
    moves_cards: tuple[str, ...] = (),
    requires_in_hand: tuple[str, ...] = (),
    requires_in_deck: tuple[str, ...] = (),
    requires_on_field: tuple[str, ...] = (),
    requires_in_gy: tuple[str, ...] = (),
    requires_in_extra: tuple[str, ...] = (),
    consumes_from_hand: tuple[str, ...] = (),
    consumes_from_field: tuple[str, ...] = (),
    sends_to_gy: tuple[str, ...] = (),
    searches_from_deck: tuple[str, ...] = (),
    summons_from_hand: tuple[str, ...] = (),
    summons_from_deck: tuple[str, ...] = (),
    summons_from_extra: tuple[str, ...] = (),
    adds_to_hand: tuple[str, ...] = (),
    sets_to_field: tuple[str, ...] = (),
    banishes_from_gy: tuple[str, ...] = (),
    once_per_turn_tag: str = "",
    normal_summon_required: bool = False,
) -> OpponentActionNode:
    return OpponentActionNode(
        node_id=node_id,
        action_name=action_name,
        card=card,
        action_type=action_type,
        timing_window=timing_window,
        vulnerable_to=vulnerable_to,
        if_resolved_go_to=if_resolved_go_to,
        if_interrupted_go_to=if_interrupted_go_to,
        recovery_routes=recovery_routes,
        endboard_additions=endboard_additions,
        risk_score=risk_score,
        payoff_score=payoff_score,
        from_location=from_location,
        to_location=to_location,
        moves_cards=moves_cards,
        requires_in_hand=requires_in_hand,
        requires_in_deck=requires_in_deck,
        requires_on_field=requires_on_field,
        requires_in_gy=requires_in_gy,
        requires_in_extra=requires_in_extra,
        consumes_from_hand=consumes_from_hand,
        consumes_from_field=consumes_from_field,
        sends_to_gy=sends_to_gy,
        searches_from_deck=searches_from_deck,
        summons_from_hand=summons_from_hand,
        summons_from_deck=summons_from_deck,
        summons_from_extra=summons_from_extra,
        adds_to_hand=adds_to_hand,
        sets_to_field=sets_to_field,
        banishes_from_gy=banishes_from_gy,
        once_per_turn_tag=once_per_turn_tag,
        normal_summon_required=normal_summon_required,
    )


def make_graph(archetype: str, graph_name: str, nodes: tuple[OpponentActionNode, ...], expected_endboard: tuple[str, ...], backup_routes: tuple[str, ...], choke_nodes: tuple[str, ...]) -> OpponentBranchGraph:
    return OpponentBranchGraph(
        opponent_archetype=archetype,
        graph_name=graph_name,
        starter_nodes=(nodes[0].node_id,),
        nodes={item.node_id: item for item in nodes},
        terminal_nodes=tuple(item.node_id for item in nodes if item.if_resolved_go_to is None),
        expected_endboard=expected_endboard,
        backup_routes=backup_routes,
        choke_nodes=choke_nodes,
    )


OPPONENT_GRAPHS: dict[str, OpponentBranchGraph] = {
    "Snake-Eye": make_graph(
        "Snake-Eye",
        "Snake-Eye Ash into Flamberge graph",
        (
            node("se_ash", "Resolve Snake-Eye Ash search", "Snake-Eye Ash", "search", "before search resolves", ("Ash Blossom", "Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler"), "se_poplar", "se_diabellstar", ("Diabellstar the Black Witch",), risk_score=0.95, payoff_score=3.0, requires_in_hand=("Snake-Eye Ash",), searches_from_deck=("Snake-Eyes Poplar",), summons_from_hand=("Snake-Eye Ash",), once_per_turn_tag="snake_eye_ash", normal_summon_required=True),
            node("se_poplar", "Special Poplar and access Spoils", "Snake-Eyes Poplar", "special_summon", "on summon", ("Infinite Impermanence", "Effect Veiler", "Droll & Lock Bird"), "se_spoils", "se_oak", ("Snake-Eye Oak",), risk_score=0.75, payoff_score=2.4, requires_in_hand=("Snake-Eyes Poplar",), summons_from_hand=("Snake-Eyes Poplar",), searches_from_deck=("Original Sinful Spoils - Snake-Eye",), once_per_turn_tag="snake_eyes_poplar"),
            node("se_spoils", "Original Sinful Spoils summon from deck", "Original Sinful Spoils - Snake-Eye", "deck_summon", "on activation", ("Ash Blossom", "Ghost Belle", "Droll & Lock Bird"), "se_flamb", "se_oak", ("Snake-Eye Oak",), risk_score=0.9, payoff_score=3.2, requires_in_hand=("Original Sinful Spoils - Snake-Eye",), consumes_from_hand=("Original Sinful Spoils - Snake-Eye",), summons_from_deck=("Snake-Eye Flamberge Dragon",), sends_to_gy=("Snake-Eyes Poplar",)),
            node("se_flamb", "Flamberge sets recursion", "Snake-Eye Flamberge Dragon", "field_effect", "on resolution", ("Infinite Impermanence", "Effect Veiler", "Ghost Belle"), "se_princess", "se_recovery", ("Promethean Princess, Bestower of Flames",), ("Flamberge recursion",), risk_score=0.85, payoff_score=3.6, requires_on_field=("Snake-Eye Flamberge Dragon",), sets_to_field=("Snake-Eyes Poplar",), sends_to_gy=("Promethean Princess, Bestower of Flames",), once_per_turn_tag="flamberge_effect"),
            node("se_princess", "Promethean Princess revive", "Promethean Princess, Bestower of Flames", "gy_effect", "in GY", ("D.D. Crow", "Ghost Belle", "Bystial", "Called by the Grave"), "se_end", "se_recovery", ("Snake-Eyes Poplar",), ("I:P into S:P",), risk_score=0.8, payoff_score=2.8, from_location="graveyard", to_location="field", requires_in_gy=("Promethean Princess, Bestower of Flames",), summons_from_extra=("S:P Little Knight",), once_per_turn_tag="promethean_princess"),
            node("se_diabellstar", "Backup Diabellstar line", "Diabellstar the Black Witch", "backup", "on activation", ("Ash Blossom", "Droll & Lock Bird"), "se_spoils", None, risk_score=0.55, payoff_score=1.8, requires_in_hand=("Diabellstar the Black Witch",), summons_from_hand=("Diabellstar the Black Witch",), searches_from_deck=("Original Sinful Spoils - Snake-Eye",)),
            node("se_oak", "Oak recovery route", "Snake-Eye Oak", "recovery", "on summon", ("Infinite Impermanence", "Effect Veiler"), "se_flamb", None, risk_score=0.45, payoff_score=1.5, requires_in_deck=("Snake-Eye Oak",), summons_from_deck=("Snake-Eye Oak",), sends_to_gy=("Snake-Eye Flamberge Dragon",)),
            node("se_recovery", "Reduced Snake-Eye follow-up", "Snake-Eyes Poplar", "terminal", "before endboard established", ("Nibiru", "Book of Eclipse"), None, None, endboard_additions=("follow-up only",), risk_score=0.35, payoff_score=1.0),
            node("se_end", "Snake-Eye endboard", "S:P Little Knight", "endboard", "before endboard established", ("Nibiru", "Book of Eclipse"), None, None, endboard_additions=("S:P Little Knight", "Flamberge recursion"), risk_score=0.3, payoff_score=4.0),
        ),
        ("S:P Little Knight", "Flamberge recursion", "Promethean Princess follow-up"),
        ("se_diabellstar", "se_oak", "se_recovery"),
        ("se_ash", "se_spoils", "se_flamb", "se_princess"),
    ),
}


def simple_graph(archetype: str, starter: str, extender: str, endboard: str, counters: tuple[str, ...], timing: str = "before search resolves") -> OpponentBranchGraph:
    key = archetype.lower().replace(" ", "_").replace("-", "_")
    return make_graph(
        archetype,
        f"{archetype} compact branch graph",
        (
            node(f"{key}_starter", f"{starter} starter action", starter, "starter", timing, counters, f"{key}_extender", f"{key}_backup", (extender,), risk_score=0.8, payoff_score=2.5, requires_in_hand=(starter,), searches_from_deck=(extender,), summons_from_hand=(starter,), once_per_turn_tag=f"{key}_starter", normal_summon_required=True),
            node(f"{key}_extender", f"{extender} extension", extender, "extender", "on summon", counters, f"{key}_end", f"{key}_backup", risk_score=0.65, payoff_score=2.0, requires_in_hand=(extender,), summons_from_hand=(extender,), once_per_turn_tag=f"{key}_extender"),
            node(f"{key}_backup", f"{archetype} backup route", extender, "backup", "before endboard established", ("Nibiru", "Book of Eclipse", *counters[:2]), f"{key}_end", None, risk_score=0.45, payoff_score=1.2, requires_in_deck=(extender,), summons_from_deck=(extender,)),
            node(f"{key}_end", f"{archetype} terminal endboard", endboard, "endboard", "before endboard established", ("Nibiru", "Book of Eclipse"), None, None, endboard_additions=(endboard,), risk_score=0.35, payoff_score=3.0),
        ),
        (endboard,),
        (f"{key}_backup",),
        (f"{key}_starter", f"{key}_extender"),
    )


OPPONENT_GRAPHS.update(
    {
        "Tenpai": simple_graph("Tenpai", "Tenpai Dragon Paidra", "Tenpai Dragon Chundra", "Trident Dragion pressure", ("Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler", "Cosmic Cyclone")),
        "Labrynth": simple_graph("Labrynth", "Arianna the Labrynth Servant", "Big Welcome Labrynth", "recursive trap pressure", ("Ash Blossom", "Cosmic Cyclone", "Harpie's Feather Duster", "Evenly Matched"), "on activation"),
        "Branded": simple_graph("Branded", "Branded Fusion", "Albion the Branded Dragon", "Mirrorjade banish", ("Ash Blossom", "Droll & Lock Bird", "D.D. Crow", "Ghost Belle")),
        "Kashtira": simple_graph("Kashtira", "Kashtira Unicorn", "Kashtira Birth", "Arise-Heart pressure", ("Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler", "Book of Eclipse")),
        "Runick": simple_graph("Runick", "Runick Tip", "Runick Fountain", "Fountain draw loop", ("Ash Blossom", "Droll & Lock Bird", "Cosmic Cyclone", "Harpie's Feather Duster"), "on activation"),
        "Floowandereeze": simple_graph("Floowandereeze", "Floowandereeze & Robina", "Floowandereeze & Eglen", "Empen floodgate", ("Ash Blossom", "Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler")),
        "Tearlaments": simple_graph("Tearlaments", "Tearlaments Reinoheart", "Tearlaments Kitkallos", "fusion recursion", ("D.D. Crow", "Ghost Belle", "Bystial", "Dimension Shifter"), "in GY"),
    }
)


def get_opponent_graph(opponent: str | OpponentProfile | None) -> OpponentBranchGraph | None:
    name = curated_opponent_name(opponent)
    if not name and isinstance(opponent, OpponentProfile):
        name = opponent.archetype
    if not name:
        name = str(opponent or "").replace(" curated profile", "")
    return OPPONENT_GRAPHS.get(str(name))


def list_opponent_graphs() -> tuple[str, ...]:
    return tuple(OPPONENT_GRAPHS)
