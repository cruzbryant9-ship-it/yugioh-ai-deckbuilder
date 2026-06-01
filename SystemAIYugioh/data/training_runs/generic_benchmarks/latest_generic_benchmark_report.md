# Generic Archetype Benchmark

- Mode: meta
- Runs per archetype: 3
- Filler-memory influence enabled: True
- JSON report: `SystemAIYugioh\data\training_runs\generic_benchmarks\20260530_070434_branded_kashtira_runick_tearlaments_meta_generic_benchmark.json`
- Average improvement: 1.26
- Repair success rate: 1.0
- Decks saved by repair: 6
- Decks completed by safe filler: 3
- Contextual filler uses: 3
- Decks still rejected: 0
- Targeted retests: 2
- Accepted targeted retests: 0
- Diff-index bias used count: 3
- Advisory signals applied: 6
- Suppressed low-support signals: 1
- Contested signals: 0
- Scrub removed entries: 0
- Historical average improvement: 0.5894
- Recent average improvement: 0.5894
- Average repair reliability: 0.9412
- Best improved archetype: Runick (2.43)
- Worst improved archetype: Branded (-0.47)

## Deck Diff Artifacts

- Branded: `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_branded_deck_diff.md` | `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_branded_deck_diff.html`
- Kashtira: `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_kashtira_deck_diff.md` | `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_kashtira_deck_diff.html`
- Runick: `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_runick_deck_diff.md` | `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_runick_deck_diff.html`
- Tearlaments: `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_tearlaments_deck_diff.md` | `SystemAIYugioh\data\training_runs\generic_benchmarks\deck_diffs\latest_tearlaments_deck_diff.html`

## Results

- Branded: normal 188.08, tuned 187.61, delta -0.47, repair 1.0, memory recorded_bad_pattern
  - Advisory: candidate adds historically harmful card movement: Albion the Shrouded Dragon
  - Advisory: candidate adds historically harmful card movement: Branded Loss
  - Advisory: candidate adds historically harmful card movement: Branded Regained
  - Diff-index advisory bias used; budget: {'enabled': True, 'total_cap': 0.15, 'tracked_sources': ['diagnosis', 'diff_index', 'filler_memory'], 'used_by_source': {'diagnosis': 0.05, 'diff_index': -0.1, 'filler_memory': 0.0}, 'remaining': 0.0}
- Kashtira: normal 183.36, tuned 184.58, delta 1.22, repair 1.0, memory updated
  - Diff-index advisory bias used; budget: {'enabled': True, 'total_cap': 0.15, 'tracked_sources': ['diagnosis', 'diff_index', 'filler_memory'], 'used_by_source': {'diagnosis': 0.05, 'diff_index': -0.1, 'filler_memory': 0.0}, 'remaining': 0.0}
- Runick: normal 162.98, tuned 165.41, delta 2.43, repair 1.0, memory updated
  - Completed by safe filler: 3
  - Contextual filler used 3 times; top fillers: Triple Tactics Talent (3), Triple Tactics Thrust (3)
  - Advisory: candidate adds historically harmful card movement: D.D. Crow
  - Advisory: candidate adds historically harmful card movement: Ghost Belle & Haunted Mansion
  - Advisory: candidate repeats historically harmful package movement: extenders:+1
  - Diff-index advisory bias used; budget: {'enabled': True, 'total_cap': 0.15, 'tracked_sources': ['diagnosis', 'diff_index', 'filler_memory'], 'used_by_source': {'diagnosis': 0.05, 'diff_index': -0.1, 'filler_memory': 0.0}, 'remaining': 0.0}
- Tearlaments: normal 189.38, tuned 191.23, delta 1.85, repair 1.0, memory updated

## Under-40 Repair Diagnostics

- Decks completed by safe filler: 3
- Decks still rejected: 0
- Repair strategies: {'archetype_package_repair': 9, 'contextual_safe_filler': 3}
- No unresolved under-40 diagnostics.

## Contextual Filler Selection

- Contextual filler uses: 3
- Top selected fillers: Triple Tactics Talent (3), Triple Tactics Thrust (3)
- Filler role distribution: consistency (6)
- Filler impact: {'average_score_with_contextual_filler': 165.01, 'average_score_without_contextual_filler': 187.36, 'impact_classification_counts': {'indeterminate': 4, 'completion_only': 2}, 'performance_positive_fillers': [], 'completion_only_fillers': ['Triple Tactics Talent', 'Triple Tactics Thrust'], 'negative_fillers': []}
- Filler impact classifications: {'classification_counts': {'indeterminate': 4, 'completion_only': 2}, 'performance_positive_fillers': [], 'completion_only_fillers': [('Triple Tactics Talent', 1), ('Triple Tactics Thrust', 1)], 'negative_fillers': [], 'shared_attribution_events': 3, 'single_card_attribution_events': 0, 'indeterminate_attribution_events': 4, 'completion_biased_cards': [], 'support_threshold_failures': [('min_archetype_breadth', 2)]}
- Filler memory cross-archetype signals: 10
- Filler memory concentration warnings: [{'card': 'Infinite Impermanence', 'dominant_archetype': 'runick', 'single_archetype_share': 0.85, 'total_observations': 60}, {'card': 'Triple Tactics Talent', 'dominant_archetype': 'runick', 'single_archetype_share': 1.0, 'total_observations': 3}, {'card': 'Triple Tactics Thrust', 'dominant_archetype': 'runick', 'single_archetype_share': 1.0, 'total_observations': 3}]
- Filler signal eligibility: {'eligible_count': 4, 'activation_ready_count': 3, 'activation_ready_fillers': ['Ash Blossom & Joyous Spring', 'Effect Veiler', 'Ghost Belle & Haunted Mansion'], 'near_eligible_count': 8, 'failed_count': 8, 'failure_counts': {'concentration_clearance': 3, 'attribution_majority': 3, 'indeterminate_suppression': 3, 'confidence_floor': 3, 'score_stability': 5, 'archetype_breadth': 2}, 'cards_closest_to_eligibility': ['Droll & Lock Bird', 'D.D. Crow', 'Cosmic Cyclone', 'Lightning Storm', 'Evenly Matched'], 'cards_blocked_by_concentration': ['Infinite Impermanence', 'Triple Tactics Talent', 'Triple Tactics Thrust'], 'cards_blocked_by_support': [], 'cards_blocked_by_archetype_breadth': ['Triple Tactics Talent', 'Triple Tactics Thrust'], 'cards_blocked_by_attribution': ['Infinite Impermanence', 'Triple Tactics Talent', 'Triple Tactics Thrust'], 'aggregate_signal_count': 12}
- Filler-memory influence: {'enabled_archetype_count': 4, 'fillers_allowed_for_influence': ['Ash Blossom & Joyous Spring', 'Effect Veiler', 'Ghost Belle & Haunted Mansion'], 'fillers_blocked_from_influence': ['Infinite Impermanence', 'Nibiru, the Primal Being'], 'rejected_due_to_not_activation_ready': ['Anti-Spell Fragrance', 'Book of Eclipse', 'Book of Lunar Eclipse', 'Book of Moon', 'Called by the Grave', 'Cosmic Cyclone', 'Crossout Designator', 'D.D. Crow', 'Dark Ruler No More', 'Droll & Lock Bird', 'Evenly Matched', 'Forbidden Droplet', 'Ghost Ogre & Snow Rabbit', "Harpie's Feather Duster", 'Infinite Impermanence', 'Lightning Storm', 'Nibiru, the Primal Being', 'Pot of Desires', 'Pot of Duality', 'Pot of Extravagance', 'Pot of Prosperity', 'Raigeki', 'Small World', 'Solemn Judgment', 'Solemn Strike', 'Solemn Warning', 'Terraforming', 'Triple Tactics Talent', 'Triple Tactics Thrust', 'Upstart Goblin'], 'filler_memory_bias_applied': {'Ash Blossom & Joyous Spring': 0.075, 'Effect Veiler': 0.015}, 'influence_changed_order_count': 0, 'selection_before_after': [{'run': 1, 'before': 'Triple Tactics Talent', 'after': 'Triple Tactics Talent', 'changed': False}, {'run': 2, 'before': 'Triple Tactics Talent', 'after': 'Triple Tactics Talent', 'changed': False}, {'run': 3, 'before': 'Triple Tactics Talent', 'after': 'Triple Tactics Talent', 'changed': False}]}
- Archetypes relying heavily on filler: Runick
- Runick best-run fillers: Triple Tactics Talent, Triple Tactics Thrust
  - Impact: {'Triple Tactics Talent': 'indeterminate', 'Triple Tactics Thrust': 'indeterminate'}
  - Filler memory: updated
  - Triple Tactics Talent selected as consistency filler (score 1.42); supports consistency pressure; fits spell/trap-heavy texture
  - Triple Tactics Thrust selected as consistency filler (score 1.33); supports consistency pressure; fits spell/trap-heavy texture

## Filler Signal Gates

- Eligible signals: 4
- Near-eligible signals: 8
- Failed signals: 8
- Cards closest to eligibility: Droll & Lock Bird, D.D. Crow, Cosmic Cyclone, Lightning Storm, Evenly Matched
- Blocked by concentration: Infinite Impermanence, Triple Tactics Talent, Triple Tactics Thrust
- Blocked by attribution: Infinite Impermanence, Triple Tactics Talent, Triple Tactics Thrust
- Blocked by support: none

## Advisory Bias Calibration

- Diagnosis bias used count: 4
- Diff-index bias used count: 3
- Bias changed exploration order count: 0
- Signals suppressed: 1
- Low-support signals ignored: 1
- Contested signals ignored: 0

## Tuning Hurt Archetypes

- Branded

## Historical Trends

| Archetype | Runs | Avg Improvement | Trend | Repair Reliability | Rejected |
|---|---:|---:|---|---:|---:|
| Branded | 200 | 0.0544 | stable | 1.0 | 0 |
| Kashtira | 200 | 0.52 | stable | 1.0 | 0 |
| Runick | 17 | 1.5306 | stable | 0.7647 | 4 |
| Tearlaments | 4 | 0.2525 | stable | 1.0 | 0 |

## Trend Diagnosis

| Archetype | Severity | Diagnosis | Suspected Causes | Recommended Adjustments |
|---|---|---|---|---|
| Branded | medium | Branded trend is stable; likely pressure from interruption shortage, ratio overfitting. | interruption_shortage, ratio_overfitting | Explore +1 interruption/non-engine slot in meta builds.; Retest safer baseline-adjacent ratios before trusting narrow improvements. |
| Kashtira | low | Kashtira trend is stable; likely pressure from interruption shortage. | interruption_shortage | Explore +1 interruption/non-engine slot in meta builds. |
| Runick | high | Runick trend is stable; likely pressure from starter density low, repair dependency high, ratio overfitting. | starter_density_low, repair_dependency_high, ratio_overfitting | Explore +1 to +2 starter/searcher slots and prefer cards that add from deck.; Prefer safer ratio profiles before aggressive exploration.; Retest safer baseline-adjacent ratios before trusting narrow improvements. |
| Tearlaments | low | Tearlaments trend is stable; likely pressure from ratio overfitting. | ratio_overfitting | Retest safer baseline-adjacent ratios before trusting narrow improvements. |

## Targeted Retests

| Archetype | Tested | Accepted | Improvement | Accepted Ratio | Rejected |
|---|---:|---|---:|---|---:|
| Branded | 5 | no | -4.4217 | none | 5 |
| Kashtira | 0 | no | 0 | none | 0 |
| Runick | 6 | no | -2.18 | none | 6 |
| Tearlaments | 0 | no | 0 | none | 0 |

## Card Shift Summary

- Accepted card-shift explanations: 0
- Rejected card-shift explanations: 11
- Most common harmful additions: Branded in Central Dogmatika (7), Albion the Shrouded Dragon (4), Branded Loss (3), Branded Regained (1), D.D. Crow (1)
- Most common harmful removals: Branded Disciple (5), Branded Befallen (4), The Fallen &amp; The Virtuous (3), Springans Kitt (2), Infinite Impermanence (2)
- Most common helpful additions: none
- Most common helpful removals: none
- Package movement summary: board_breakers:-1 (5), extenders:+1 (3)
- Replay package deltas: board_breakers:-1 (5), extenders:+1 (4), engine_requirement:+1 (2), interruptions:-1 (1)
- Replay risk flags: package_instability (1)

## Cross-Archetype Diff Index

- Top Helpful Additions: none
- Top Harmful Additions: Branded in Central Dogmatika (701), Albion the Shrouded Dragon (444), Kashtira Overlap (380), Kashtira Akstra (354), Branded Loss (255)
- Top Helpful Removals: none
- Top Harmful Removals: Branded Disciple (510), D.D. Crow (415), Branded Befallen (405), Nibiru, the Primal Being (319), The Fallen &amp; The Virtuous (296)
- Top Helpful Package Movements: none
- Top Harmful Package Movements: engine_requirement:+3 (669), board_breakers:-1 (510), extenders:-3 (387), engine_requirement:+1 (351), extenders:+1 (270)
- Common Risk Flags: package_instability (26), extender_loss (14)
- Archetypes Needing Review: Branded, Kashtira, Runick

## Accepted Card Shifts

- None

## Rejected Card Shifts

- Branded: Candidate declined by -7.805. Added Albion the Shrouded Dragon, Branded Loss, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple, The Fallen &amp; The Virtuous. Role gains: +1 extenders. Role losses: -1 board_breakers.
- Branded: Candidate declined by -8.475. Added Albion the Shrouded Dragon, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple. Role gains: +1 engine_requirement. Role losses: -1 board_breakers.
- Branded: Candidate declined by -4.4217. Added Branded in Central Dogmatika; removed Branded Disciple. Role gains: +1 engine_requirement. Role losses: -1 board_breakers.
- Branded: Candidate declined by -6.8883. Added Albion the Shrouded Dragon, Branded Loss, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple, Springans Kitt. Role gains: +1 extenders. Role losses: -1 board_breakers.
- Branded: Candidate declined by -7.6883. Added Albion the Shrouded Dragon, Branded Loss, Branded Regained; removed Branded Befallen, Branded Disciple, Screams of the Branded. Role gains: +1 extenders. Role losses: -1 board_breakers. Risks: package_instability.
- Runick: Candidate declined by -4.27. Added no major additions; removed no major removals.
- Runick: Candidate declined by -2.18. Added no major additions; removed no major removals.
- Runick: Candidate declined by -2.8033. Added no major additions; removed no major removals.

## Before/After Package Replay

### Accepted Replay Sections

- None

### Rejected Replay Sections

### Branded Package Replay

- Score delta: -7.805
- Main count: 40 -> 40
- Extra count: 1 -> 1
- Risk flags: none
- Explanation: Candidate declined by -7.805. Added Albion the Shrouded Dragon, Branded Loss, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple, The Fallen &amp; The Virtuous. Role gains: +1 extenders. Role losses: -1 board_breakers.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| board_breakers | 1 | 0 | -1 |
| engine_requirement | 35 | 35 | +0 |
| extenders | 1 | 2 | +1 |
| interruptions | 3 | 3 | +0 |

| Card | Delta | Change |
|---|---:|---|
| Albion the Shrouded Dragon | +1 | added/increased |
| Branded Befallen | -1 | removed/decreased |
| Branded Disciple | -1 | removed/decreased |
| Branded Loss | +1 | added/increased |
| Branded in Central Dogmatika | +1 | added/increased |
| The Fallen &amp; The Virtuous | -1 | removed/decreased |

### Branded Package Replay

- Score delta: -8.475
- Main count: 40 -> 40
- Extra count: 1 -> 1
- Risk flags: none
- Explanation: Candidate declined by -8.475. Added Albion the Shrouded Dragon, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple. Role gains: +1 engine_requirement. Role losses: -1 board_breakers.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| board_breakers | 1 | 0 | -1 |
| engine_requirement | 35 | 36 | +1 |
| extenders | 1 | 1 | +0 |
| interruptions | 3 | 3 | +0 |

| Card | Delta | Change |
|---|---:|---|
| Albion the Shrouded Dragon | +1 | added/increased |
| Branded Befallen | -1 | removed/decreased |
| Branded Disciple | -1 | removed/decreased |
| Branded in Central Dogmatika | +1 | added/increased |

### Branded Package Replay

- Score delta: -4.4217
- Main count: 40 -> 40
- Extra count: 1 -> 1
- Risk flags: none
- Explanation: Candidate declined by -4.4217. Added Branded in Central Dogmatika; removed Branded Disciple. Role gains: +1 engine_requirement. Role losses: -1 board_breakers.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| board_breakers | 1 | 0 | -1 |
| engine_requirement | 35 | 36 | +1 |
| extenders | 1 | 1 | +0 |
| interruptions | 3 | 3 | +0 |

| Card | Delta | Change |
|---|---:|---|
| Branded Disciple | -1 | removed/decreased |
| Branded in Central Dogmatika | +1 | added/increased |

### Branded Package Replay

- Score delta: -6.8883
- Main count: 40 -> 40
- Extra count: 1 -> 1
- Risk flags: none
- Explanation: Candidate declined by -6.8883. Added Albion the Shrouded Dragon, Branded Loss, Branded in Central Dogmatika; removed Branded Befallen, Branded Disciple, Springans Kitt. Role gains: +1 extenders. Role losses: -1 board_breakers.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| board_breakers | 1 | 0 | -1 |
| engine_requirement | 35 | 35 | +0 |
| extenders | 1 | 2 | +1 |
| interruptions | 3 | 3 | +0 |

| Card | Delta | Change |
|---|---:|---|
| Albion the Shrouded Dragon | +1 | added/increased |
| Branded Befallen | -1 | removed/decreased |
| Branded Disciple | -1 | removed/decreased |
| Branded Loss | +1 | added/increased |
| Branded in Central Dogmatika | +2 | added/increased |
| Springans Kitt | -1 | removed/decreased |
| The Fallen &amp; The Virtuous | -1 | removed/decreased |

### Branded Package Replay

- Score delta: -7.6883
- Main count: 40 -> 40
- Extra count: 1 -> 1
- Risk flags: package_instability
- Explanation: Candidate declined by -7.6883. Added Albion the Shrouded Dragon, Branded Loss, Branded Regained; removed Branded Befallen, Branded Disciple, Screams of the Branded. Role gains: +1 extenders. Role losses: -1 board_breakers. Risks: package_instability.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| board_breakers | 1 | 0 | -1 |
| engine_requirement | 35 | 35 | +0 |
| extenders | 1 | 2 | +1 |
| interruptions | 3 | 3 | +0 |

| Card | Delta | Change |
|---|---:|---|
| Albion the Shrouded Dragon | +1 | added/increased |
| Branded Befallen | -1 | removed/decreased |
| Branded Disciple | -1 | removed/decreased |
| Branded Loss | +1 | added/increased |
| Branded Regained | +1 | added/increased |
| Branded in Central Dogmatika | +2 | added/increased |
| Screams of the Branded | -1 | removed/decreased |
| Springans Kitt | -1 | removed/decreased |
| The Fallen &amp; The Virtuous | -1 | removed/decreased |

### Runick Package Replay

- Score delta: -4.27
- Main count: 40 -> 40
- Extra count: 5 -> 5
- Risk flags: none
- Explanation: Candidate declined by -4.27. Added no major additions; removed no major removals.

| Package | Before | After | Delta |
|---|---:|---:|---:|
| engine_requirement | 29 | 29 | +0 |
| extenders | 1 | 1 | +0 |
| interruptions | 10 | 10 | +0 |

| Card | Delta | Change |
|---|---:|---|
| None | 0 | no change |


### Compact Card-Delta Table

| Archetype | Card | Delta | Change |
|---|---|---:|---|
| Branded | Albion the Shrouded Dragon | +1 | added/increased |
| Branded | Branded Befallen | -1 | removed/decreased |
| Branded | Branded Disciple | -1 | removed/decreased |
| Branded | Branded Loss | +1 | added/increased |
| Branded | Branded in Central Dogmatika | +1 | added/increased |
| Branded | The Fallen &amp; The Virtuous | -1 | removed/decreased |
| Branded | Albion the Shrouded Dragon | +1 | added/increased |
| Branded | Branded Befallen | -1 | removed/decreased |
| Branded | Branded Disciple | -1 | removed/decreased |
| Branded | Branded in Central Dogmatika | +1 | added/increased |
| Branded | Branded Disciple | -1 | removed/decreased |
| Branded | Branded in Central Dogmatika | +1 | added/increased |
| Branded | Albion the Shrouded Dragon | +1 | added/increased |
| Branded | Branded Befallen | -1 | removed/decreased |
| Branded | Branded Disciple | -1 | removed/decreased |
| Branded | Branded Loss | +1 | added/increased |
| Branded | Branded in Central Dogmatika | +2 | added/increased |
| Branded | Springans Kitt | -1 | removed/decreased |
| Branded | The Fallen &amp; The Virtuous | -1 | removed/decreased |
| Branded | Albion the Shrouded Dragon | +1 | added/increased |

## Long-Term Leaders

- Runick: 1.5306
- Kashtira: 0.52
- Tearlaments: 0.2525
- Branded: 0.0544

## Follow-Up Archetypes

- Branded
- Runick
