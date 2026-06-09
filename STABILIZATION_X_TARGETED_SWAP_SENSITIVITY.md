# Stabilization X: Targeted Swap Sensitivity

Targeted sensitivity analysis only. No experimental builder promotion, default semi-specialized activation, scoring weight change, regression threshold change, Blue-Eyes authored behavior change, memory influence, generic builder behavior change, active adapter behavior change, neural method, reinforcement learning, self-play, duel engine, or combo graph work was introduced.

## Files Created

- `kashtira_targeted_swap_sensitivity.py`
- `validate_stabilization_x.py`
- `STABILIZATION_X_TARGETED_SWAP_SENSITIVITY.md`

## Files Changed

- None; this phase adds proposed-only analysis/reporting files.

## Best Adjustment

- Best adjustment: `H_restore_overlap_reduce_preparations`
- Classification: `helpful`
- Score delta vs public overlay: `3.0887`
- Recommendation: `test_adjusted_variant_next`

## Swap Variants Tested

- `A_book_over_akstra`: `harmful`, score `187.142`, vs generic `-0.768`, vs public overlay `-0.87`
- `B_book_over_overlap`: `harmful`, score `185.482`, vs generic `-2.428`, vs public overlay `-2.53`
- `C_book_over_tearlaments`: `harmful`, score `186.173`, vs generic `-1.737`, vs public overlay `-1.839`
- `D_preparations_over_akstra`: `inconclusive`, score `187.906`, vs generic `-0.004`, vs public overlay `-0.106`
- `E_preparations_over_overlap`: `inconclusive`, score `188.009`, vs generic `0.099`, vs public overlay `-0.003`
- `F_preparations_over_tearlaments`: `inconclusive`, score `188.077`, vs generic `0.167`, vs public overlay `0.065`
- `G_restore_akstra_reduce_book`: `inconclusive`, score `188.072`, vs generic `0.162`, vs public overlay `0.06`
- `H_restore_overlap_reduce_preparations`: `helpful`, score `191.1007`, vs generic `3.1907`, vs public overlay `3.0887`
- `I_reduce_book_restore_tearlaments`: `harmful`, score `187.223`, vs generic `-0.687`, vs public overlay `-0.789`
- `J_reduce_preparations_restore_tearlaments`: `helpful`, score `188.451`, vs generic `0.541`, vs public overlay `0.439`

## Harmful Adjustments

- `['A_book_over_akstra', 'B_book_over_overlap', 'C_book_over_tearlaments', 'I_reduce_book_restore_tearlaments']`

## Validation Results

- Passed: True
- Duration seconds: 945.8224
- PASS: targeted analyzer runs
- PASS: all swap variants are tested
- PASS: no builder behavior changes
- PASS: no active adapter behavior changes
- PASS: generic builder remains unchanged
- PASS: classification exists for each swap
- PASS: recommendation follows rules
- PASS: Stabilization W validator still passes
- PASS: Stabilization V validator still passes
- PASS: Phase 8A validator still passes
- PASS: core suite still passes
- PASS: matchup matrix smoke still passes

## Recommended Next Step

- Stabilization Y should run a proposed-only larger sample for the best restoration adjustment before any adapter change is considered.
