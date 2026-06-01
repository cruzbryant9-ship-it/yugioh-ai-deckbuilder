# Stabilization H: Filler Memory Integrity

Stabilization H hardens Phase 6P filler memory before any future phase is allowed to use that memory as selection bias.

## Attribution Model

Filler impact now records attribution quality:

- `single_card`: exactly one filler card was added. This can receive full attribution.
- `shared`: multiple filler cards were added in the same repair event. Attribution confidence is reduced to `1 / filler_count`.
- `none`: no filler card was added.

Shared positive or negative events are marked `indeterminate` at the per-card level. This prevents every filler card in a batch from receiving full credit or blame for the same score delta.

## Completion-Only Suppression

Filler memory now marks cards as completion-biased when:

```text
completion_only_count / times_used >= 0.50
```

Completion-biased cards:

- remain visible in reports,
- can still be used for legal deck completion,
- cannot become eligible positive filler-memory signals.

## Archetype-First Memory

The primary memory structure remains:

```text
archetype -> mode -> filler card
```

A derived `cross_archetype_index` is generated only when a card has enough support and observations across multiple archetypes. Runick-only evidence remains Runick-local.

## Eligibility Gates

`is_filler_signal_eligible(...)` requires:

- minimum use count,
- minimum archetype breadth for cross-archetype reads,
- valid provenance,
- legal observations only,
- no completion-bias flag.

These gates prepare future read-time safety. Stabilization H does not activate filler memory influence.

## Advisory Budget

`deck/advisory_influence_budget.py` now tracks:

- `diagnosis`
- `diff_index`
- `filler_memory`

The existing global kill switch disables all advisory sources.

## Concentration Monitoring

Memory reports concentration warnings when a filler card's observations are dominated by one archetype:

```text
single_archetype_share > 70%
```

The warning includes dominant archetype, concentration percentage, and total observations.

## Validation

Run:

```powershell
python validate_stabilization_h.py
python validate_phase6p.py
python validate_phase6o.py
python validate_stabilization_g.py
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick --mode meta --runs 3 --show-replay
python matchup_matrix.py --archetype "Blue-Eyes" --mode meta --runs-per-cell 1 --use-curated-opponents --smoke
```

## Remaining Risks

- Shared attribution is conservative but still observational.
- Cross-archetype signals are derived, not causal.
- Filler memory is still report-only and must remain disabled until a separate review phase approves influence.
