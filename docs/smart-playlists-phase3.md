# Smart Playlists Phase 3

This document summarizes the Phase 3 enhancements to the MediaLibrary Smart Playlists engine and editor.

## Summary of Enhancements

- Rule-level NOT (negation) in addition to group-level negation.
- Stable `uid` identifiers added to `Rule` and `RuleGroup` (foundation for future diffing / external references).
- New relative time operators: `within_hours`, `within_days`, `within_weeks`, `within_months`.
- Derived fields for convenience & performance: `age_days` (integer days since `mtime`), `filesize_mb` (rounded MB from `size`).
- Advanced editor UI updates:
  - NOT column checkbox for both rules and groups.
  - Context menu NOT toggle support for rules and groups.
  - Extended operator pickers for new relative time options.
  - Live preview uses an internal signature (hash) to avoid unnecessary re‑evaluation when structure unchanged.
- Serialization & persistence now include rule-level `negate` flags (backward compatible: missing flags default to `False`).

## Data Model Changes

`Rule` dataclass:
- Added: `negate: bool = False`
- Added: `uid: str` (8 hex chars) for stable node identity.

`RuleGroup` dataclass:
- Added: `uid: str` (8 hex chars) similar purpose.

Backward compatibility: loader injects missing `uid` and `negate` defaults on legacy JSON. No schema version key required yet; migrations remain lightweight.

## Operator Reference (Incremental Additions)

| Operator | Applies To | Semantics |
|----------|------------|-----------|
| within_hours | mtime | `mtime >= now - hours*3600` |
| within_days  | mtime | `mtime >= now - days*86400` |
| within_weeks | mtime | `mtime >= now - weeks*604800` |
| within_months| mtime | Approx month (30.44 days) window |
| between (extended) | duration, age_days, filesize_mb | Inclusive range check |

## Derived Fields

| Field | Source | Description |
|-------|--------|-------------|
| age_days | mtime | Floor of elapsed days since `mtime` (epoch). 0 / None if invalid. |
| filesize_mb | size  | Size in megabytes (two decimal places). |

These are computed in the evaluation value provider; no on-disk storage.

## Editor Behavior Notes

- Drag & drop still relies on Qt internal move; after a drop, the tree is traversed to rebuild the `RuleGroup` structure maintaining new order.
- Undo/redo tracks serialized snapshots (including rule-level negation state) and refreshes the live preview.
- Cache signature includes rule-level negation & group negation; a change to a NOT checkbox invalidates the signature.

## Persistence Guarantees

- Rule and group order are preserved as list order in JSON arrays.
- Missing fields (legacy playlists) are upgraded in memory only; saving writes new keys.
- Negated rules evaluate as inverted boolean results of their base predicate after type coercion.

## Testing Additions

New test coverage (Phase 3):
- `test_smart_new_phase3.py`: rule-level negate, new relative time ops, derived fields between usage.
- `test_smart_ordering.py`: ensures ordering and rule-level negation persist across save/load cycles.

## Future Considerations (Phase 4 Ideas)

- Incremental evaluation cache keyed by library revision counter (current code only caches preview inside editor session).
- Inline multi-value editors for list-based fields (e.g., tags) with auto-suggestion.
- Export/import of smart playlist definitions with schema version stamping.
- Visual diff view when comparing two playlists.

## Migration Guidance

No manual user action needed. Simply opening & saving an existing smart playlist will emit the enriched schema (including `uid` and rule-level `negate` = false by default).

## Troubleshooting

| Symptom | Possible Cause | Resolution |
|---------|----------------|-----------|
| Rule NOT checkbox ignored | Old cached editor dialog | Reopen editor, ensure rule serialized with `negate` key. |
| Derived fields not available | UI file not reloaded / stale install | Reinstall editable package and restart app. |
| Unexpected ordering after drag | Nested group restructure logic | Verify drop target highlight, then re-open editor to confirm persisted order. |

---
Generated as part of Phase 3 implementation (2025-10-05).