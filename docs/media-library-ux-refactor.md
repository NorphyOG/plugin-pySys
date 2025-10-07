# Media Library UX Refactor Plan

## Goals
- Dual Mode: `classic` (lightweight table) and `enhanced` (visual rich dashboard)
- Netflix/Spotify inspiration: horizontal carousels, cover-forward browsing
- Explorer inspiration: left sidebar for Sources / Playlists / Smart / Tags
- Preserve all existing feature depth (ratings, tags, playlists, stats) while reducing cognitive load.

## Phases
1. Classic Mode (DONE) – fast fallback, minimal regression risk.
2. Skeleton Enhanced Components – carousel widget, hero area, sidebar container (in progress).
3. Data Providers – functions that surface Recent, Top Rated, By Genre, By Kind; efficient batching & caching.
4. Interaction Layer – context menus, hover actions (play, open folder, edit tags) on cards.
5. Performance Work – chunked carousel population + lazy cover loading; telemetry for load time & interaction.
6. Unified Settings – user toggle for mode + ordering of shelves.
7. Documentation & Migration Notes – update README / system-tools-plan delta list.

> **2025-10-06 update:** The historic implementation has been checked into `src/mmst/plugins/media_library/legacy/`. The runtime loader now imports from that package instead of the build artefact cache, keeping classic mode intact while we grow the enhanced/ultra surfaces.

## Component Sketch

- `views/enhanced/carousel.py` – Horizontal scroll shelf; accepts loader callback; later: virtualization.
- `views/enhanced/hero.py` – Prominent large cover + quick actions (play, open, tag) + dynamic background color extraction (future).
- `views/enhanced/sidebar.py` – Tree / list navigation; emits selection -> central stacked panel.
- `views/enhanced/dashboard.py` – Assembles hero + rows; re-queries when library changes.

## Configuration Keys (proposed)

```jsonc
{
  "view_mode": "classic",            // or "enhanced"
  "enhanced": {
    "shelves": [
      {"type": "recent", "limit": 20},
      {"type": "top_rated", "limit": 20},
      {"type": "by_genre", "genre": "Rock", "limit": 15},
      {"type": "by_kind", "kind": "video", "limit": 15}
    ],
    "hero": { "mode": "random_recent" }
  }
}
```

## Telemetry (optional)

- `media_ui.carousel.populate` – duration, count
- `media_ui.hero.refresh` – duration
- `media_ui.mode.switch` – from/to

## Open Questions

- Cover prefetch strategy for shelves (shared cache vs per-shelf burst)
- Smart playlist integration as separate shelf types
- Async metadata enrichment badges on cards (deferred)

---

_Status: Draft created (phase 2 starting)._ 
