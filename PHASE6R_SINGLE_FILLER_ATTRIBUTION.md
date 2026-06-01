# Phase 6R: Single-Card Filler Attribution Data Collection

Phase 6R adds a controlled data-collection benchmark for filler cards. It does not activate filler-memory influence, change scoring, change authored Blue-Eyes behavior, or relax legality rules.

## Purpose

Phase 6Q proved that no filler card currently has enough clean evidence to influence deckbuilding. Phase 6R collects cleaner observations by testing one candidate filler card at a time across multiple generic archetypes.

## Runner

Run:

```powershell
python single_filler_attribution_benchmark.py --archetypes Branded Kashtira Runick --mode meta --runs 3
```

If fewer than four archetypes are provided, the runner attempts to add one extra available generic archetype, such as Tearlaments or Labrynth, to improve breadth.

## Controlled Comparison

Each test:

1. Builds a baseline generic deck.
2. Chooses one legal candidate filler.
3. Replaces one low-priority or existing filler card.
4. Scores baseline and candidate decks.
5. Records the deck copy delta.
6. Marks the event clean only when the candidate deck has exactly one filler increase and one replacement decrease.

Clean events are recorded with:

```text
attribution_model = single_card
attribution_confidence = 1.0
```

If more than one card changes, the event is recorded as shared/indeterminate and does not provide full positive or negative credit.

## Candidate Filler Pool

The default candidate pool is:

- Infinite Impermanence
- Ash Blossom & Joyous Spring
- Effect Veiler
- Droll & Lock Bird
- Nibiru, the Primal Being
- D.D. Crow
- Ghost Belle & Haunted Mansion
- Cosmic Cyclone
- Lightning Storm
- Evenly Matched

All candidates still respect banlist, custom limits, copy limits, and blocked-card checks.

## Reports

Reports are saved to:

```text
SystemAIYugioh/data/training_runs/filler_attribution/
```

The latest readable report is:

```text
SystemAIYugioh/data/training_runs/filler_attribution/latest_filler_attribution_report.md
```

The report includes:

- clean single-card events
- shared or failed attribution events
- score deltas by filler
- archetype breadth by filler
- gate progress after memory update
- cards closest to eligibility

## Memory Safety

Only clean single-card comparisons increase single-card attribution counts and attribution confidence. Shared events remain indeterminate.

Filler memory influence remains disabled. The filler selector still does not read filler memory.

## Phase 6S Recommendation

Phase 6S should analyze whether the newly collected single-card evidence improves gate progress enough to justify another eligibility review. Influence should remain disabled until at least one card passes Phase 6Q gates with clean, broad, stable support.
