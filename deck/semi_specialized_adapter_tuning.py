from __future__ import annotations

from typing import Any


def generate_kashtira_adapter_tuning_variants() -> list[dict[str, Any]]:
    return [
        {
            "name": "preserve_interaction_core",
            "description": "Preserve generic high-scoring hand-trap interaction before filling reconciled quota gaps.",
            "proposed_adjustment": {
                "preserve_cards": ["Ash Blossom & Joyous Spring", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being"],
                "reduce_roles": [],
                "score_estimate_bias": 1.45,
            },
            "expected_benefit": "Restores interaction cards repeatedly removed by the current experimental adapter.",
            "expected_risk": "May soften strict quota movement and reduce package-quality gain.",
            "applied": False,
        },
        {
            "name": "reduce_generic_fill",
            "description": "Lower reliance on post-quota generic fill by favoring cards already present in the generic baseline.",
            "proposed_adjustment": {
                "generic_fill_cap_delta": -6,
                "score_estimate_bias": 0.85,
            },
            "expected_benefit": "Reduces noisy filler after quota picks and should improve score parity.",
            "expected_risk": "Can leave some reconciled package quotas under-filled.",
            "applied": False,
        },
        {
            "name": "cap_book_of_eclipse",
            "description": "Cap Book of Eclipse at a lower count in the experimental adapter simulation.",
            "proposed_adjustment": {
                "card_caps": {"Book of Eclipse": 1},
                "score_estimate_bias": 0.55,
            },
            "expected_benefit": "Reduces board-breaker overcorrection found in Phase 8K.",
            "expected_risk": "May weaken going-second pressure.",
            "applied": False,
        },
        {
            "name": "balanced_quota_softening",
            "description": "Soften starter/searcher and extender quota movement rather than forcing hard counts first.",
            "proposed_adjustment": {
                "quota_softening": {"starters": -2, "extenders": 2, "board_breakers": -1},
                "score_estimate_bias": 1.15,
            },
            "expected_benefit": "Counters overcorrection away from generic starter/searcher and extender texture.",
            "expected_risk": "May reduce projected quota-balance improvement.",
            "applied": False,
        },
        {
            "name": "extra_deck_payoff_cap",
            "description": "Cap proposed Extra Deck payoff additions to prevent payoff-heavy projection from crowding utility picks.",
            "proposed_adjustment": {
                "extra_deck_payoff_cap": 2,
                "score_estimate_bias": 0.35,
            },
            "expected_benefit": "Limits Extra Deck payoff over-selection while preserving legal Extra Deck structure.",
            "expected_risk": "Could lower endboard ceiling.",
            "applied": False,
        },
        {
            "name": "hybrid_generic_interaction_overlay",
            "description": "Combine interaction preservation with softened quota movement and lower generic fill.",
            "proposed_adjustment": {
                "preserve_cards": ["Ash Blossom & Joyous Spring", "D.D. Crow", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being"],
                "quota_softening": {"starters": -1, "extenders": 2, "board_breakers": -1},
                "generic_fill_cap_delta": -5,
                "score_estimate_bias": 2.25,
            },
            "expected_benefit": "Most directly targets the Phase 8K regression causes without changing scoring or default behavior.",
            "expected_risk": "Most complex proposal; should be tested behind the fixed-seed gate before any adapter change.",
            "applied": False,
        },
    ]
