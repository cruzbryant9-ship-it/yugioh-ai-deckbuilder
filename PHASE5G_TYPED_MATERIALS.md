# Phase 5G Typed Materials

## What Phase 5G Adds

Phase 5G gives graph validation basic card metadata awareness. Resource validation can now check material requirements by name, archetype, type text, attribute, level, tuner status, non-tuner status, Dragon type, and Blue-Eyes identity.

## Card Metadata Helpers

`deck/card_metadata.py` provides helpers such as:

- `get_card_name`
- `get_card_level`
- `get_card_type`
- `is_monster`
- `is_spell`
- `is_trap`
- `is_tuner`
- `is_dragon`
- `is_light`
- `is_dark`
- `is_blue_eyes`
- `is_extra_deck_monster`
- `is_fusion`
- `is_synchro`
- `is_xyz`
- `is_link`
- `card_matches_requirement`

## Requirement Examples

```python
{"name": "Blue-Eyes White Dragon"}
{"archetype": "Blue-Eyes"}
{"type_contains": "Dragon"}
{"attribute": "LIGHT"}
{"level": 8}
{"tuner": True}
{"non_tuner": True}
```

## Supported Material Validation

The graph validator now supports:

- Synchro requirements such as tuner + Level 8 non-tuner
- Fusion named materials and generic materials
- Ritual spell and ritual level requirements
- Link material requirement lists
- Extra Deck card availability

## New Metrics

`real_combo_report()` and score breakdowns now include:

- `typed_material_valid_rate`
- `synchro_material_failure_rate`
- `fusion_material_failure_rate`
- `ritual_material_failure_rate`
- `link_material_failure_rate`
- `named_material_failure_rate`

Regression gates can reject learning when typed material validity drops or typed material failures spike.

## Limitations

This is still not a full rules engine. It does not yet model exact Synchro level sums, Xyz level matching, Link ratings, substitution materials, "treated as" clauses, or card-specific exceptions. It is a typed material filter layered on top of string-based resource tracking.

## Next Phase

Phase 5H should add summon math: Synchro level totals, Ritual tribute totals with overpay rules, Xyz equal-level materials, Link ratings, and material substitution effects.

