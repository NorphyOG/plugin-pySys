# Media Library Modularization & Enrichment Architecture

Status: draft (ongoing extraction of concerns from monolithic `plugin.py`).

## Goals

- Restore & stabilize legacy ("Classic") functionality while enabling a richer "Enhanced" dashboard UI.
- Incrementally reduce the size and responsibility scope of `plugin.py` to improve testability and velocity.
- Provide clear, composable panels/services for playback, statistics, scanning, enrichment, and future features.

## Extracted Components

| Component | Module | Responsibility | Notes |
|-----------|--------|----------------|-------|
| PlayerPanel (planned) | `player_panel.py` | Encapsulate QMediaPlayer, video widget, transport + volume controls | Currently a placeholder; real logic still inline in `plugin.py` for safety until refactor completes. |
| StatsPanel | `stats_panel.py` | Wrap statistics dashboard & refresh pipeline | Uses `build_dashboard_stats` and delegates metadata + attribute loading. |
| ScanService | `scan_service.py` | Directory scanning + filesystem watcher orchestration | Abstracts `scan_source` + `FileSystemWatcher`; provides uniform API for UI actions. |
| Shelves/Dashboard | `shelves.py` + `views/enhanced/` | Enhanced mode hero, carousels, sidebar data & actions | Persists shelf order; integrates settings + command palette. |
| Command Palette | `views/enhanced/command_palette.py` | Searchable action launcher (Ctrl+Shift+P) | Lightweight, decoupled from heavy plugin state. |

## Refactor Phases

1. Recovery & Stability: Fix missing listing, crashing statistics, reintroduce Classic table view.
2. Enrichment & UX: Add hero, carousels, dynamic shelves, actions, settings panel, command palette.
3. Telemetry & Performance: Chunked loading, event loop monitor, rating/kind queries.
4. Modularization (Current): Extract stats, scan/watcher, then player, then remaining monolith utilities.
5. Future: Dedicated enrichment cache panel, asynchronous preview pipeline, playlist intelligence service.

## Current Responsibilities Snapshot

`plugin.py` (still large) currently retains:

- Player instantiation & inline controls (to migrate to `PlayerPanel`).
- Metadata detail panel rendering & selection logic.
- Gallery + table coordination & filters.
- Context menus (play, edit metadata, playlists, Kino mode, delete).
- Batch editing UI, playlist & tag management dialogs.

Moved out:

- Statistics refresh logic → `StatsPanel.refresh()`.
- Scanning & watching (add source, full scan, watcher callbacks) → `ScanService` (API: `scan_new_source`, `full_rescan`, `start_watcher`, `stop_watcher`).

## ScanService API

```python
service = ScanService(library_index, notify=notify_fn, refresh=refresh_fn)
count = service.scan_new_source(Path("/media/music"), progress=cb)
service.full_rescan(progress=cb)
service.start_watcher()
service.stop_watcher()
active = service.watcher_active
paths = service.watched_path_count()
```

Progress callback signature: `(file_path: str, current: int, total: int)`.

Watcher callbacks update the `LibraryIndex` and then invoke the provided `refresh` callable to keep UI in sync.

## StatsPanel API

```python
panel = StatsPanel()
panel.connect_refresh(lambda: panel.refresh(index, metadata_reader))  # typical wiring
panel.refresh(index, metadata_reader)
```

The panel supplies attribute tuples `(rating, tags)` via an internal `attribute_loader`, leaving metadata extraction to injected `metadata_reader` (supports test injection & caching strategies).

## PlayerPanel (Planned Extraction)

Target responsibilities:

- Manage `QMediaPlayer`, `QAudioOutput`, `QVideoWidget`.
- Provide uniform API: `load_media(path, kind)`, `play_pause()`, `stop()`, `set_position(ms)`, `set_volume(percent)`, `current_state()`.
- Emit minimal signals for UI binding (position, duration, state changes) or expose callbacks to avoid Qt signal explosion in tests.

Migration Considerations:

- Preserve existing tests expecting `_media_player` side-effects (will shim attributes until test suite updated).
- Avoid regressions in headless mode: maintain graceful fallbacks where PySide6 multimedia is absent.

## Testing Impact & Strategy

Short term: Existing tests untouched; new modules mirror old behavior through plugin delegation.
Planned additions:

- Unit tests for `ScanService` (simulate fake `scan_source` & watcher stub).
- Unit tests for `StatsPanel` using a minimal fake index and deterministic metadata objects.
- Later: PlayerPanel tests (state transitions, volume boundary cases, video visibility switching).

## Future Work Backlog

| Priority | Task | Rationale |
|----------|------|-----------|
| High | Implement real `PlayerPanel` & remove inline player UI | Shrinks monolith & enables reuse (e.g., mini-player overlay). |
| High | Document config schema interactions (view_mode, shelf_order, auto_watch) | Ensures safe migrations later. |
| Medium | Introduce enrichment queue panel | Visualize pending/active metadata enrichment tasks. |
| Medium | Add scan dry-run / diff preview | User clarity before rescans or structural changes. |
| Low | Extract context-menu action handlers to strategy registry | Cleaner extension of actions. |

## Design Principles Recap

- Progressive Disclosure: Enhanced dashboard optional; Classic mode remains first-class.
- Fail-Soft: All panels/services degrade gracefully when optional deps (PySide6 multimedia, watchdog) are missing.
- Stable Contracts: Public APIs use simple callables instead of deep signal coupling where feasible.
- Incremental Refactor: Introduce modules with minimal risk before fully deleting old inline logic.

## Changelog (Modularization Track)

- vNEXT: Added `scan_service.py`, `stats_panel.py`, placeholder `player_panel.py`; updated plugin to delegate statistics + scanning.
- vNEXT+: Enhanced dashboard status row (quick stats counts, watcher activity, now playing display) and plugin helpers for dynamic updates.

## Enhanced Dashboard Additions (Productivity & Feedback Layer)

Recent iterations introduced a set of user experience upgrades inspired by modern streaming UIs (Netflix visual density, Spotify playback ergonomics, Explorer clarity). These features build atop the modular services while keeping Classic mode functional and minimal.

### 1. Scan Progress Bar

- A compact `QProgressBar` now lives in the enhanced header (dashboard). It becomes visible when a scan starts and hides automatically on completion.
- Progress source: the existing `_with_scan_progress` callback pipeline (current/total). Percentage is computed defensively (guards divide-by-zero) and label text remains minimal to avoid jitter.
- Buttons that trigger scans (Add Source, Rescan) are temporarily disabled during active scans to prevent re-entrancy.

### 2. Table Summary Row & Dynamic Reset

- Beneath the main library table a summary row displays: `Gefiltert: X / Gesamt: Y` (filtered vs total entries) plus active kind filter.
- A contextual Reset button only appears when filters/search reduce the total set, providing instant clarity and one-click restoration.

### 3. Mini Player Bar

- A persistent bottom mini player exposes: Previous ◀, Play/Pause ▶/⏸, Stop ⏹, Next ▶▶, a progress slider, and a concise time label (`mm:ss / mm:ss`).
- Synchronizes with the main player state (selection changes, play events) and updates position on a lightweight timer (optimized to avoid UI flooding).
- Navigation shortcuts (see below) integrate with this bar to enable keyboard-only browsing & playback.

### 4. Keyboard Shortcuts (Ergonomics Set)

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Focus search field |
| F5 | Full rescan (respecting progress lock) |
| Ctrl+W | Toggle filesystem watcher |
| Ctrl+H | Toggle Hero visibility (persists `hero_hidden`) |
| Ctrl+P | Play/Pause current selection |
| Ctrl+Left / Ctrl+Right | Previous / Next item navigation (wraps) |
| Ctrl+L | Focus library/table view |
| Ctrl+Shift+P | (Planned) Command Palette invocation |

Design Notes:

- Shortcuts avoid clashes with common OS-level bindings and favor mnemonic mapping (F for Find, W for Watcher, H for Hero).
- Additional reserved future keys: Ctrl+G (go to genre filter), Ctrl+T (tag filter focus), Alt+Enter (detailed metadata dialog).

### 5. Notification Overlay

- Lightweight stacked overlay (top-right) queues transient messages (auto-dismiss after timeout) without stealing focus or causing layout shifts.
- Caps the number of concurrently visible notifications (configurable constant in plugin) and gracefully removes oldest when overflowed.
- Backed by existing `CoreServices.send_notification` for consistency; overlay augments dashboard log rather than replacing it.

### 6. Watcher Tooltip Enrichment

- Watcher status label tooltip now includes: last full scan timestamp (persisted as `last_full_scan`) and current watched source count.
- Timestamp stored in plugin config on successful full scan completion for session-to-session continuity.
- Provides immediate operational context (when was data last fully validated?).

### 7. Statistics Busy State

- Invoking statistics refresh disables the stats button and injects a temporary inline spinner label (textual placeholder) to reflect active work.
- Prevents double-trigger and communicates latency cause when large datasets require aggregation.
- On completion the button is re-enabled and placeholder removed; errors restore state gracefully.

### 8. Resilience & Performance Considerations

- All new UI elements adhere to fail-soft behavior when PySide6 multimedia or optional dependencies are absent (no crashes; features silently no-op or hide).
- Progress & mini player timers use modest intervals to minimize event loop pressure (tunable if profiling suggests adjustments for >50k libraries).
- Notification overlay limits re-layout by fixed-size vertical stacking; fade/animation deferred until profiling confirms negligible cost.

### 9. Persistence Keys Added

| Key | Purpose |
|-----|---------|
| `hero_hidden` | Stores user choice to hide hero section |
| `last_full_scan` | ISO timestamp for last successful full rescan (tooltip) |

### 10. Testing Impact

- Existing logic tests remain valid; UI tests that assert widget presence may require updates if they previously depended on static button enablement during scans or statistics refresh.
- Recommended new tests (future backlog):
	- Scan progress visibility toggle (start → visible, end → hidden).
	- Summary row counts with and without active filters.
	- Mini player navigation wrap-around logic.
	- Watcher tooltip content includes persisted timestamp after scan.
	- Statistics button disabled state during refresh.

### 11. Future Enhancements (Planned)

- Fade/slide animations for overlay notifications (CSS or property animation) with accessibility fallback.
- Command Palette integration with existing action set (Ctrl+Shift+P).
- PlayerPanel extraction to decouple mini player from monolithic plugin logic.
- Performance counters (scan duration ms, enrichment queue depth) appended to status row.

---

This layer completes the first productivity and feedback milestone, delivering richer situational awareness while preserving responsiveness and backwards compatibility with Classic mode.

## Enhanced Dashboard Status Row

The status row provides at-a-glance operational feedback:

Components:
 
1. Quick Stats (📁 total, Audio, Video, Bilder, Andere) – updated after library load / filter changes / scans.
2. Watcher State (👁 Aktiv/Inaktiv plus watched source count) – updates on watcher start/stop and source list changes.
3. Now Playing (▶ Title) – reflects current playback selection when available.

Initialization & Timing:
 
- Labels start with neutral placeholders (📁 Lädt…, 👁 Initialisiere…) to avoid confusing placeholders prior to data readiness.
- A single-shot delayed update (≈250 ms) runs post-construction to populate real data after the initial entry load.
- Subsequent unified refreshes route through `Plugin._update_dashboard_status()` consolidating stats + watcher state to minimize redundant UI churn.

Formatting Decisions:
 
- Emojis provide compact semantic anchors without adding icon asset overhead.
- German labels stay consistent with existing UI wording (Dateien, Bilder, Andere).
- Pipe separators (`|`) maintain readability and compactness.

Future Considerations:
 
- Conditional color accents via stylesheet (inactive watcher, high error rate) pending broader theming pass.
- Optional performance counters (recent scan duration, enrichment queue depth) may append after stabilization.

## Action Toolbar & Empty States

Added a lightweight action toolbar below the status row for rapid access to frequent tasks:

- ✚ Quelle: opens add-source dialog
- ↻ Rescan: triggers full rescan via `ScanService.full_rescan`
- 👁 Start/Stop: toggles filesystem watcher (label updates dynamically)
- 📊 Statistik: refreshes statistics panel

Hero Empty State:
 
- When the hero provider yields no items, a guidance message is shown: “Noch keine Inhalte – füge eine Quelle hinzu ✚”.
- Prevents a blank large area and directs the user to first action.

Styling:
 
- Toolbar buttons use a compact dark style and 11px font for hierarchy under main content.
- Status labels styled subtly (#bbb) to reduce visual dominance.

## Compact Header & Hero Behavior (Update)

- Statusinformationen und Aktionen wurden zu einer einzigen kompakten Kopfzeile zusammengeführt (Statistik · Watcher · Now Playing + Buttons).
- Separator "·" sorgt für leichte visuelle Trennung ohne harte Linien.
- Hero blendet sich automatisch aus, wenn keine Items geliefert werden (verhindert große leere Fläche).
- Manuelles Schließen des Hero über ein ✕ in der Hero-Kopfzeile (Session-only; keine Persistenz aktuell).
- Buttons behalten kompakte Höhe (11px Font) für reduzierte vertikale Verschwendung.

### Ergänzungen (Header v2)

- Quick Filter Chips: Alle / Audio / Video / Bilder steuern direkt den vorhandenen Kind-Filter (Combo sync) und lösen sofort Filter + Tabellen-Refresh aus.
- Watcher Label Farbcode: Aktiv = #89d185 (grünlich), Inaktiv = #888 (grau) für schnellere Erfassung.
- Hero Persistenz: Schließen (✕) setzt `hero_hidden = true` in Plugin-Config; beim nächsten Start bleibt er ausgeblendet bis ein Reset-Mechanismus implementiert ist (geplant: Einstellungsschalter im Settings-Panel).

## Leere Zustände & Platzhalter

- Carousels blenden sich jetzt automatisch aus wenn sie keine Elemente liefern (vermeidet visuelle „Löcher“ und Scroll-Leerraum).
- Wenn weder Hero sichtbar ist noch ein Carousel Inhalte zeigt, erscheint ein zentraler Platzhalter: "Keine Inhalte – füge eine Quelle hinzu ✚".
- Platzhalter verschwindet sofort sobald erste Inhalte geladen oder ein Hero wieder sichtbar wird.

## Scan Fortschritt & Interaktions-Verbesserungen

- Header zeigt während Scans ein kompaktes Label ("🔄 Scan x/y"). Nach Abschluss wird es geleert.
- Scan-Buttons (Quelle / Rescan) werden während eines laufenden Scans deaktiviert und danach wieder aktiviert (verhindert Doppel-Trigger).
- Tooltips für Hauptaktionen hinzugefügt (Quelle hinzufügen, Rescan, Watcher-Toggle, Statistik) für bessere Selbstbeschreibbarkeit.
- Watcher-Label zeigt Quellanzahl auch im Inaktiv-Zustand (z.B. "Inaktiv (2)").
- Platzhalter enthält jetzt eine "Hero anzeigen" Aktion um ausgeblendeten Hero wieder einzublenden (persistenter hero_hidden Flag wird zurückgesetzt).

---

Questions / extension ideas can be appended below this divider.

