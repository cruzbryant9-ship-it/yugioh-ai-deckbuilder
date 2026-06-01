# Phase 5K: Chain Windows + Interruption Modeling

Phase 5K adds a lightweight chain and interruption risk layer. It does not simulate a full opponent hand or full duel state. It estimates where a combo line opens response windows and how fragile that line is against common disruption.

## Chain Model

`deck/chain_model.py` represents simple chain windows:

```python
{
    "chain_link": 1,
    "activating_card": "Bingo Machine, Go!!!",
    "effect_type": "search",
    "response_window": True,
    "possible_responses": ["Ash Blossom", "Droll & Lock Bird"],
    "resolution_outcome": "resolved_with_risk",
}
```

Supported concepts:

- activation window
- response window
- chain link
- effect resolves
- effect negated
- activation negated
- stopped before resolution
- hand trap response
- once-per-chain approximation through unique response counting

## Interruption Profiles

`deck/interruption_profiles.py` defines common interruptions:

- Ash Blossom
- Infinite Impermanence
- Effect Veiler
- Droll & Lock Bird
- D.D. Crow
- Nibiru
- Called by the Grave

Each profile describes response targets, timing, effect, risk score, and recovery difficulty.

## Graph Integration

`LineNode` now supports:

- `opens_chain`
- `response_window`
- `vulnerable_to`
- `protected_by`
- `on_negated`
- `recovery_routes`
- `interruption_penalty`
- `bait_value`

The validator records chain windows and estimates line risk/resilience while preserving the existing Phase 5J branch and history system.

## Resilience Metrics

Reports and score breakdowns now include:

- `interruption_window_count`
- `average_interruption_risk`
- `ash_vulnerability_rate`
- `imperm_vulnerability_rate`
- `veiler_vulnerability_rate`
- `droll_vulnerability_rate`
- `crow_vulnerability_rate`
- `nibiru_vulnerability_rate`
- `recovery_route_rate`
- `interrupted_line_success_rate`
- `resilience_score`

Regression gates can reject learning if resilience drops, interrupted-line success drops, interruption risk rises, or key vulnerability rates spike.

## Limits

This is risk/resilience modeling, not a full duel simulator.

- It does not sample opponent hands.
- It does not build full chain stacks with both players making choices.
- It does not model negated activation vs negated effect with full PSCT precision.
- It does not yet evaluate bait sequencing deeply.

## Next Phase

Phase 5L should add matchup profiles and side-deck planning: expected interruption density by matchup, going-first/going-second plans, and side-package recommendations.
