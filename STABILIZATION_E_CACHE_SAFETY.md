# Stabilization E: Cache Safety

Stabilization Pass E focuses on cache correctness and durable-memory safety. It does not add gameplay systems or change scoring semantics.

## Cache Fingerprinting

Persistent matchup matrix cache entries now include a deterministic fingerprint. The fingerprint includes:

- `cards.json`, `metadata.json`, and `latest_update_analysis.json` file size, mtime, and SHA-256 hash
- custom card limits
- `ENGINE_VARIANTS`
- report/cache versions
- matrix smoke/full side-plan settings and smoke matrix limits

The fingerprint is included in the cache key and the persisted payload. If any material input changes, old entries become misses instead of warm hits.

## Failed-Cell Handling

Failed matrix cells are not persisted as authoritative cache entries. A cell with `failed_cell=true`, no successful runs, or a `failure_rate` of `1.0` is skipped by the persistent cache. This prevents transient runtime exceptions from poisoning future warm runs.

## Cache Load Safety

Matrix cache reads now validate the cached cell schema before returning data. Invalid, truncated, stale, or older-schema payloads become cache misses. Cache reads return defensive deep copies so callers cannot mutate shared cached state.

## Memory Protection

Before matrix results update durable memory files such as matchup engine stats or curated opponent memory, the report runs a memory-safety check. This re-validates cached and fresh cells for blocked cards in:

- best main deck
- best Extra Deck
- recommended side deck
- per-run main/extra/side cards

If cached data contains blocked cards or illegal side recommendations, the regression gate may still be accepted, but durable memory updates are blocked.

## Validation

`validate_stabilization_e.py` verifies:

- fingerprint changes invalidate cache entries
- failed cells are not persisted
- cached matrix cells must pass schema checks
- cache reads are defensive copies
- a cold cell and warm cached cell are equivalent except allowed runtime fields
- illegal cached decks fail the memory-safety gate
- JSON writes use the atomic helper path

## Remaining Risks

The cache fingerprint is conservative for local card data files and core settings, but it does not hash every Python source file that can affect scoring. Cache invalidation still relies partly on report/cache version changes for code-only behavior updates. Full source-level dependency hashing can be added later if runtime cost remains acceptable.
