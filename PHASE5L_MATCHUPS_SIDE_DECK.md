# Phase 5L: Matchups and Side-Deck Planning

Phase 5L adds matchup-aware side-deck recommendations on top of the Phase 5K chain and interruption model. The side deck remains advisory: it does not replace the main deck, overwrite learned profiles by itself, or bypass banlist and custom limit checks.

## Matchup Profiles

Matchup profiles live in `deck/matchup_profiles.py`.

Supported profiles:

- `combo`
- `control`
- `stun`
- `graveyard`
- `backrow`
- `spell_heavy`
- `handtrap_heavy`
- `board_breaker_heavy`
- `light_dark`
- `unknown_meta`

Each profile stores expected interruption density, board strength, graveyard dependency, backrow density, monster effect density, going-first priorities, going-second priorities, high-value side cards, low-value cards, and risk factors.

## Side-Deck Planner

`deck/side_deck_planner.py` exposes:

```python
build_side_deck(deck, archetype, matchup_profile, card_pool, going="both")
```

It returns:

- `side_deck`
- `reasons`
- `matchup`
- `going_first_plan`
- `going_second_plan`
- `cards_to_side_out`
- `side_deck_score`
- `matchup_coverage_score`
- `going_first_side_score`
- `going_second_side_score`

The planner ranks legal cards from the current card pool using profile priorities, common staple names, card text terms, learned-compatible scoring hooks, and current main-deck copy counts. It will recommend at most 15 cards and skips cards that violate banlist or custom limits.

## Side-In and Side-Out Logic

Side-in plans are profile priorities, such as hand traps against combo or backrow removal against control and stun. Side-out suggestions are conservative and text based. They look for profile-specific low-value cards and narrow cards that are unlikely to matter in a matchup.

## Scoring

`deck/side_deck_scoring.py` scores:

- matchup coverage
- going-first usefulness
- going-second usefulness
- anti-graveyard coverage
- anti-backrow coverage
- anti-combo coverage
- anti-control coverage
- overlap penalty
- legality

Training, evaluation, engine comparison, and regression gates now carry side-deck metrics:

- `side_deck_score`
- `matchup_coverage_score`
- `going_first_side_score`
- `going_second_side_score`

## CLI Usage

Interactive deck building now asks for matchup and going preference. Press Enter to use:

- matchup: `unknown_meta`
- going: `both`

Training and reports support:

```powershell
python train_agent.py --archetype "Blue-Eyes" --mode meta --runs 2 --matchup combo --going both
python evaluate_learning.py --archetype "Blue-Eyes" --mode meta --runs 2 --matchup combo --going both
python compare_engines.py --archetype "Blue-Eyes" --mode meta --runs-per-engine 1 --matchup combo --going both
```

## Regression Protection

`SystemAIYugioh/regression_gates.py` rejects learning if side-deck score or matchup coverage drops too far compared with the previous learned profile, or if side plans introduce blocked-card violations.

## Validation

Run:

```powershell
python validate_phase5l.py
```

The validator checks profile loading, side-deck size, blocked-card filtering, matchup-specific recommendations, side scoring schema, and smoke runs for training, evaluation, and engine comparison.

## Current Limitations

- Matchups are broad categories, not opponent decklists.
- Side-out recommendations are conservative text heuristics.
- Side-deck cards are recommendations only and are not inserted into tournament deck exports yet.
- The planner does not simulate post-side games.
- Best and worst matchup profile reporting currently reflects the matchup being evaluated, not a full matchup matrix.

## Next Phase

The natural next phase is Phase 5M: matchup matrix testing. That would run each engine against every matchup profile, compare going-first and going-second plans, and learn which engine variants are best into specific expected metas.
