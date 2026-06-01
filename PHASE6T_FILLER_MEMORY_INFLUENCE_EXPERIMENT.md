# Phase 6T: Controlled Filler-Memory Influence Experiment

Phase 6T enables a tiny, explicit, kill-switchable filler-memory ordering bias for activation-ready fillers only. It does not enable general filler-memory influence, change scoring weights, change authored Blue-Eyes behavior, or bypass legality/copy limits.

## Default Behavior

Filler-memory influence is off by default.

```powershell
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 3
```

This preserves Phase 6S behavior.

## Experiment Flag

Use the explicit flag to run the experiment:

```powershell
python generic_archetype_benchmark.py --archetypes Branded Kashtira Runick Tearlaments --mode meta --runs 3 --enable-filler-memory-influence
```

The selector also requires the module-level experiment flag and the global advisory kill switch to be clear. The benchmark sets the experiment flag only for the duration of the run, then restores the prior value.

## Allowed Cards

Only fillers that pass both eligibility gates and holdout review can receive bias:

- Ash Blossom & Joyous Spring
- Effect Veiler
- Ghost Belle & Haunted Mansion

Explicitly blocked:

- Nibiru, the Primal Being
- Infinite Impermanence

Nibiru failed holdout. Infinite Impermanence remains ineligible because older Runick-heavy/shared evidence still dominates its history.

When the experiment flag is enabled, these two named cards are excluded from the filler-memory experiment path. Default non-experiment behavior remains unchanged.

## Bias Limits

The influence is ordering-only:

- It can slightly reorder legal filler candidates.
- It cannot veto legal fillers.
- It cannot override score-based deck acceptance.
- It cannot select blocked or illegal cards.
- It cannot override banlist or copy limits.

Configured caps:

- `MAX_FILLER_MEMORY_BIAS = 0.03`
- `PER_CARD_FILLER_MEMORY_BIAS_CAP = 0.025`

The global advisory kill switch overrides all filler-memory influence.

## Reporting

Benchmark reports include:

- `filler_memory_influence_enabled`
- `fillers_allowed_for_influence`
- `fillers_blocked_from_influence`
- `filler_memory_bias_applied`
- `influence_changed_order_count`
- `selected_filler_before_bias`
- `selected_filler_after_bias`
- `rejected_due_to_not_activation_ready`

## Recommendation

This should remain experimental until repeated A/B benchmark runs show that the tiny ordering bias is consistently neutral or positive without increasing illegal decks, rejected decks, or repair dependency.
