# Phase 5M: Matchup Matrix Testing

Phase 5M expands side-deck planning into a full matchup matrix. Instead of testing one engine against one selected matchup, the matrix evaluates every supported engine variant across every matchup profile and going-first/going-second plan.

## Matrix Dimensions

Engine variants:

- `pure`
- `ritual`
- `chaos`
- `bystial`
- `horus`
- `branded`
- `handtrap_heavy`
- `board_breaker_heavy`

Matchup profiles:

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

Going plans:

- `first`
- `second`
- `both`

That creates 240 cells. Each cell can run multiple deck builds.

## Running The Matrix

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1
```

Use higher `--runs-per-cell` values for stronger data:

```powershell
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 5
```

## Reports

JSON reports are saved to:

```text
SystemAIYugioh/data/training_runs/matchup_matrix/
```

The latest readable markdown report is saved to:

```text
SystemAIYugioh/data/training_runs/matchup_matrix/latest_matchup_matrix_report.md
```

Each cell records average score, best score, package quality, playable hand rate, brick rate, resilience score, side-deck score, matchup coverage score, going-first score, going-second score, blocked-card violations, best deck, and recommended side deck.

## Rankings

The matrix ranks:

- best overall engine
- best engine by matchup
- best going-first engine
- best going-second engine
- safest low-brick engine
- best side-deck-compatible engine
- most resilient engine
- worst engine/matchup pairing

## Matchup-Aware Engine Weighting

Accepted matrix results update:

```text
SystemAIYugioh/data/deck_profiles/matchup_engine_stats.json
```

`build_deck()` now accepts optional `matchup` and `going` arguments. When accepted matrix stats exist, the builder can prefer the engine variant that performed best for that matchup and going plan. If no stats exist, old behavior is preserved.

The fallback weighted generator also applies only a small capped card-weight adjustment for the recommended matchup engine. Banlist and custom limits still apply first.

## Regression Protection

Matrix stats are not saved if regression gates detect:

- unstable matrix averages
- blocked-card violations
- sharp matchup coverage drops
- resilience drops
- side-deck score drops

Training and evaluation report whether matchup-aware weighting was used.

## Limitations

- The matrix uses matchup profiles, not real opponent decklists.
- Smoke validation uses one run per cell, which is useful for wiring but noisy strategically.
- Side decks are still recommendations only.
- Best matchup choices are based on current heuristic scores, not post-side game win rates.

## Next Phase

Phase 5N should add matchup-specific post-side simulations: compare game-one, going-first post-side, and going-second post-side plans with explicit side-in/side-out deck variants.
