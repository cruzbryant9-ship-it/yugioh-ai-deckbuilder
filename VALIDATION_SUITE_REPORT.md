# Validation Suite Report

## Validators Migrated

- `validate_phase7a.py`
- `validate_stabilization_m.py`
- `validate_stabilization_l.py`
- `validate_stabilization_k.py`
- `validate_stabilization_j.py`
- `validate_stabilization_n.py`

## Commands Deduplicated

- Core-suite mode skips nested validator calls inside migrated validators.
- Core-suite mode skips nested matchup matrix smoke calls inside migrated validators.
- `validate_core_suite.py` runs matchup matrix smoke once in controlled order.

## Runtime Summary

- Baseline runtime before consolidation: not measured by a historical structured runner.
- Core suite duration: 57.5093 seconds
- Runtime improvement source: nested heavy validator and matchup-matrix smoke calls are skipped in core-suite mode.
- validate_phase7a.py: 20.7037s, passed=True
- validate_stabilization_m.py: 5.0775s, passed=True
- validate_stabilization_l.py: 0.8091s, passed=True
- validate_stabilization_k.py: 2.6655s, passed=True
- validate_stabilization_j.py: 4.3696s, passed=True
- validate_stabilization_n.py: 20.5913s, passed=True
- matchup matrix smoke: 3.2926s, passed=True

## Remaining Validators Using Old Local run_command

- `validate_phase5.py`
- `validate_phase5b.py`
- `validate_phase5d.py`
- `validate_phase5e.py`
- `validate_phase5f.py`
- `validate_phase5g.py`
- `validate_phase5h.py`
- `validate_phase5i.py`
- `validate_phase5j.py`
- `validate_phase5k.py`
- `validate_phase5l.py`
- `validate_phase5m.py`
- `validate_phase5n.py`
- `validate_phase5o.py`
- `validate_phase5p.py`
- `validate_phase5q.py`
- `validate_phase5r.py`
- `validate_phase5s.py`
- `validate_phase5t.py`
- `validate_phase5u.py`
- `validate_phase5v.py`
- `validate_phase5w.py`
- `validate_phase5x.py`
- `validate_phase6a.py`
- `validate_phase6b.py`
- `validate_phase6c.py`
- `validate_phase6d.py`
- `validate_phase6e.py`
- `validate_phase6f.py`
- `validate_phase6g.py`
- `validate_phase6h.py`
- `validate_phase6i.py`
- `validate_phase6j.py`
- `validate_phase6k.py`
- `validate_phase6l.py`
- `validate_phase6m.py`
- `validate_phase6n.py`
- `validate_phase6o.py`
- `validate_phase6p.py`
- `validate_phase6q.py`
- `validate_phase6r.py`
- `validate_phase6s.py`
- `validate_phase6t.py`
- `validate_phase6u.py`
- `validate_stabilization_a.py`
- `validate_stabilization_b.py`
- `validate_stabilization_c.py`
- `validate_stabilization_d.py`
- `validate_stabilization_f.py`
- `validate_stabilization_g.py`
- `validate_stabilization_h.py`
- `validate_stabilization_i.py`

## Remaining Stdout-Fragile Checks

- Some legacy validators outside the migrated core suite still check human-readable stdout terms.
- The core suite now prefers return codes, JSON/Markdown report existence, and structured harness results where practical.
