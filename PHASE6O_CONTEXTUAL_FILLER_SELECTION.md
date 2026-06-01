# Phase 6O: Contextual Filler Selection

Phase 6O improves the generic repair layer that completes under-40 generic decks. Phase 6N added a conservative safe filler pool; Phase 6O keeps that same legality-first pool but ranks filler choices by deck context before adding them.

## What Was Added

- `deck/generic_filler_selector.py`
  - Selects legal safe fillers for missing main-deck slots.
  - Scores fillers by package pressure, deck texture, mode, matchup hints, diagnosis hints, and small advisory diff-index signals.
  - Returns selected cards, reasons, role distribution, context scores, and rejected filler reasons.
- `deck/generic_deck_repair.py`
  - Uses contextual filler selection instead of the old static safe-filler order.
  - Records contextual filler metadata in repair output.
- `deck/generic_deck_builder.py`
  - Surfaces contextual filler metadata in generic build reports.
- `deck/generic_tuner.py`
  - Aggregates contextual filler use across tuning variants.
- `generic_archetype_benchmark.py`
  - Reports selected fillers, role distribution, score impact, and archetypes that rely heavily on filler.

## Filler Quality Scoring

The selector only considers cards that are already legal safe-filler candidates. It never relaxes banlist, custom blocklist, or copy-limit enforcement.

Filler score considers:

- Missing starter/searcher pressure.
- Missing interruption pressure.
- Missing board-breaker pressure.
- Spell/trap-heavy versus monster-heavy texture.
- Graveyard, banish, and Extra Deck reliance.
- `meta` versus `innovation` mode.
- Optional matchup and going-first/second hints.
- Diagnosis causes such as `interruption_shortage`, `starter_density_low`, and `brick_pressure_high`.
- Small advisory-only diff-index signals when they have enough safe support.

## Metadata

Repair/build/tuning reports now include:

- `contextual_filler_used`
- `selected_fillers`
- `filler_reasons`
- `filler_roles`
- `filler_context_scores`
- `rejected_filler_reasons`

Benchmark summaries also include:

- `contextual_filler_usage_count`
- `selected_filler_counts`
- `filler_role_distribution`
- `filler_impact_summary`
- `archetypes_relying_on_contextual_filler`

## Safety Rules

Contextual filler is advisory selection only. It cannot:

- Add blocked cards.
- Exceed legal copy limits.
- Overfill above 40 cards.
- Override score-based acceptance.
- Increase Phase 6M advisory bias strength.
- Replace authored Blue-Eyes logic.

## Current Limitations

- Filler texture scoring is heuristic and lightweight.
- Matchup support is optional and broad.
- Filler impact is reported observationally; it is not a causal attribution model.
- Diff-index signals only affect ordering slightly and are ignored when low-support or contested.

## Validation

Run:

```powershell
python validate_phase6o.py
python validate_phase6n.py
python validate_phase6m.py
python validate_stabilization_g.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick --mode meta --runs 3 --show-replay
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```
