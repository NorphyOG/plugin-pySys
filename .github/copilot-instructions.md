# MMST Copilot Instructions

### FileManager (`src/mmst/plugins/file_manager/`)
- **Duplicate scanning:** `scanner.py` groups files by size, then hashes with SHA-256 in a `ThreadPoolExecutor`. Progress surfaces via Qt signals (`scan_progress`, `scan_completed`). Preserve the "at least one survivor per group" guard when changing delete flows.
- **Backup engine:** `backup.py` computes diff plans, handles mirror deletions through `send2trash`, and streams progress (`BackupResult`, `BackupStats`). UI updates live in `FileManagerWidget` slots (`backup_progress_init`, `backup_progress`).
- **UI conventions:** Tabs named "Duplikate" and "Backup" with log consoles and action buttons. When extending functionality (dry runs, presets), keep controls grouped in `QGroupBox` forms.
- **Tests:** `tests/test_duplicate_scanner.py` and `tests/test_backup.py` provide fixtures for temporary directories, verifying hash grouping, trash logic, and summary strings.
- **Scheduling:** The backup system now supports scheduled operations (hourly/daily/weekly/monthly) with persistent configuration and background execution.
- **Smart selection:** Duplicate scanner provides intelligent selection modes (keep oldest, keep smallest, filter by folder) to simplify user workflow.ick orientation
- **Run the dashboard:** `python -m mmst.core.app` launches the PySide6 shell and auto-loads plugins. The command works from the repo root; the core reads persisted window/plugin state from `%APPDATA%/mmst` (Windows) or `$XDG_CONFIG_HOME/mmst` (Linux).
- **Install dependencies:** `python -m pip install -e .[dev]` gives you the editable package, PySide6, pytest, and optional helpers like `send2trash` and `mutagen`.
- **Execute tests:** `python -m pytest` exercises all logic-heavy modules. GUI-dependent tests skip themselves when PySide6 is missing (`pytest.importorskip("PySide6")`). Use `-k` filters to target plugin suites (for example, `python -m pytest -k media_library`).
- **Developer tooling:** `scripts/build.py` wraps install → test → packaging → optional portable bundle. Flags such as `--no-tests`, `--portable-only`, or `--dist <path>` let you stage CI-like pipelines locally.
- **Reference docs:** Deep dives live in `docs/` (for example, `filesystem-watcher.md`, `metadata-engine.md`, `system-tools-plan.md`). Always cross-check there before making architectural changes.
- **Diagnostics tools:** Use `scripts/diag_media_library_plugin.py` to generate test data, run benchmarks, and analyze MediaLibrary performance (supports commands like `generate` for synthetic datasets).

## Architecture map
- **Core entry (`src/mmst/core/app.py`):** Provides `DashboardWindow` with sidebar plugin list, start/stop/configure actions, and a stacked central view. Window geometry, selected plugin, and started plugin set persist via `CoreServices.get_app_config()`.
- **Plugin lifecycle:** `PluginManager` (`core/plugin_manager.py`) discovers `mmst.plugins.<name>.plugin` modules, instantiates a `Plugin` class (subclass of `BasePlugin`), and tracks `PluginRecord` state (`LOADED → STARTED/STOPPED/FAILED`). `PluginState` drives sidebar coloring.
- **Shared services:** `CoreServices` (`core/services.py`) owns the logger hierarchy, notification pub/sub, config store, audio device service, and plugin data directories. Plugins access it through the constructor to request logger instances, persist settings, or emit user-facing notifications.
- **Configuration store:** `CoreServices` wraps `ConfigStore` (`core/config.py`). Config lives in `config.json` inside the per-user data dir and exposes `get_plugin(identifier)` / `write_plugin(identifier, payload)` for JSON-like dictionaries.
- **UI expectations:** PySide6 widgets should stay responsive. Long-running work (hashing, scanning, metadata enrichment, conversions) is offloaded to worker threads (`concurrent.futures` executors) or background Qt signals. Keep dialogs and progress indicators in line with existing widgets (`FileManagerWidget`, `MediaLibraryView`).

## Core patterns & services
- **Notifications:** Use `CoreServices.send_notification(message, level="info", source=plugin_id)` so users see toasts and logs. Levels map to sidebar colors via `_set_status` in `DashboardWindow`.
- **Data folders:** Call `CoreServices.ensure_subdirectories()` to create per-plugin storage (`covers`, `reports`, `cache`, etc). Tests rely on these directories being idempotent.
- **Audio devices:** `AudioDeviceService` (`core/audio.py`) normalizes `sounddevice` enumeration, caches descriptors, and provides loopback handling hints. Audio-centric plugins should request devices via this service, never directly through `sounddevice`.
- **Config schemas:** Follow existing JSON payloads documented in `docs/plugin-concepts.md`. Example: FileManager stores `duplicate_scanner.last_path` and `backup.mode`; MediaLibrary stores library roots, filter presets, and playlist definitions.
- **Progress system:** The dashboard now includes a global progress dialog for tracking multi-task operations across plugins, ensuring consistent user feedback.

## Plugin specifics
### AudioTools (`src/mmst/plugins/audio_tools/`)
- **Primary modules:** `plugin.py` handles the Qt view with Equalizer & Recorder tabs; `equalizer.py` encapsulates DSP filters with real-time spectrum analysis; `recorder.py` orchestrates `sounddevice` streams and writes metadata via `mutagen`.
- **Device management:** Uses `AudioDeviceService` for platform detection. Windows backends plan to integrate `pycaw`; Linux uses `pulsectl`. Preserve graceful fallbacks when dependencies are missing.
- **Presets & config:** Slider states and recorder quality land in the plugin config bucket. Tests in `tests/test_audio_tools_plugin.py` assert that presets persist and recorder logs include metadata.
- **Threading:** Recording runs in background threads; ensure UI buttons stay enabled/disabled via Qt signals. When adding DSP visualizations, emit minimal data to avoid freezing.

### FileManager (`src/mmst/plugins/file_manager/`)
- **Duplicate scanning:** `scanner.py` groups files by size, then hashes with SHA-256 in a `ThreadPoolExecutor`. Progress surfaces via Qt signals (`scan_progress`, `scan_completed`). Preserve the “at least one survivor per group” guard when changing delete flows.
- **Backup engine:** `backup.py` computes diff plans, handles mirror deletions through `send2trash`, and streams progress (`BackupResult`, `BackupStats`). UI updates live in `FileManagerWidget` slots (`backup_progress_init`, `backup_progress`).
- **UI conventions:** Tabs named "Duplikate" and "Backup" with log consoles and action buttons. When extending functionality (dry runs, presets), keep controls grouped in `QGroupBox` forms.
- **Tests:** `tests/test_duplicate_scanner.py` and `tests/test_backup.py` provide fixtures for temporary directories, verifying hash grouping, trash logic, and summary strings.

### MediaLibrary (`src/mmst/plugins/media_library/`)
- **Library index:** `core.py` implements `LibraryIndex` using SQLite with WAL mode and RLocks. Methods like `upsert_file`, `list_files_with_sources`, and playlist CRUD power the UI and Smart Playlist evaluation.
- **Smart playlists:** Defaults ship in `smart_playlists.json`. The plugin loads them at startup, and tests such as `tests/test_smart_playlists.py`, `tests/test_smart_nested_groups.py`, and `tests/test_smart_within_days.py` cover rule evaluation, nested groups, and operators like `within_days`.
- **Filesystem watcher:** See `docs/filesystem-watcher.md`. `watcher.py` wraps `watchdog` observers, filters media extensions, and dispatches callbacks back into `LibraryIndex`. When editing, keep thread-safety (RLock + Qt signal handoff) intact.
- **Metadata engine:** `metadata` package reads/writes tags with `mutagen`/`pymediainfo`. Refer to `docs/metadata-engine.md` and tests in `tests/test_metadata.py` for serialization patterns.
- **UI & UX:** Includes both table and gallery views with synchronized selection, media player integration, context menus, tag management, and batch operations. Performance optimized for libraries with 10k+ files through chunked loading.
- **Performance targets:** The library aims for specific performance metrics (filter changes <250ms, playlist operations <300ms) even with very large libraries (100k+ files). Use `scripts/diag_media_library_plugin.py` for performance testing.

### SystemTools (`src/mmst/plugins/system_tools/`)
- **Tool detection:** `tools.py` exposes `ToolDetector` and `CONVERSION_FORMATS`. It shells out to `ffmpeg`/`magick`, parses versions, and degrades gracefully when binaries are absent. Tests in `tests/test_system_tools.py` mock `shutil.which` and `subprocess.run` to validate behavior.
- **Conversion pipeline:** `converter.py` defines `ConversionJob`, `ConversionResult`, and `FileConverter`. Jobs run via `subprocess.run`, stream stderr for progress, and emit localized success/failure summaries. Ensure tests can inject fake subprocesses.
- **Batch processing:** Implements a multi-file queue system for sequential processing with per-file status tracking and overall progress indication.
- **Image compression:** Includes visual comparison tools for before/after compression with quality slider adjustments.
- **Future panels:** `docs/system-tools-plan.md` tracks upcoming Disk Integrity Monitor and temp cleaner tasks. Document new features there as you finish or schedule them.

## Persistence & data flows
- **App state:** Dashboard window size/position, selected plugin, and auto-start list live under the `__dashboard__` config bucket. Call `_save_dashboard_state()` on close to persist updates.
- **Plugin state:** Use `get_plugin_config(identifier)` to read dictionaries, mutate copies, and persist with `save_plugin_config(identifier, values)`. Avoid raw file I/O—tests expect JSON schema stability.
- **Media cache:** MediaLibrary covers/resized artwork should reside under `CoreServices.ensure_subdirectories("covers")` to keep per-user storage tidy.
- **Scheduling & timers:** Auto-start logic uses `_restore_dashboard_state()` on launch. When implementing scheduled tasks (backup timers, library scans), follow the FileManager backup scheduler pattern.

## External integrations
- **PySide6 fallbacks:** `core/app.py` defines `_QtFallback` so the core imports without PySide6 at runtime (enables headless tests). Preserve these guards when relocating imports.
- **watchdog:** Only instantiate observers if available. Provide toggles to disable watchers when missing, and log friendly instructions.
- **Command-line tools:** SystemTools must guide users to install `ffmpeg`, `ImageMagick`, or SMART utilities. Store overrides in `tools` config keys and surface validation messages via notifications.
- **Audio stack:** AudioTools leans on `sounddevice` (PortAudio) and optional `numpy`/`scipy` DSP. Always catch backend exceptions and display Qt dialogs rather than crashing the worker.

## Testing & quality gates
- **Pytest layout:** Tests live in `tests/` and rely on `pythonpath = ["src"]` (see `pyproject.toml`). Use fixtures for temp paths (`tmp_path`) and monkeypatching external commands.
- **Selective runs:** GUI-heavy suites skip when PySide6 missing. CLI-centric modules (converter, scanner, metadata) have deterministic tests—run them before committing logic changes.
- **Integration flags:** Slow filesystem watcher tests are marked; run selectively with `python -m pytest tests/test_watcher.py -k "not slow"` for quick feedback.
- **CI expectations:** Keep new tests stable across Windows & Linux. Guard platform-specific assertions with `pytest.skipif(sys.platform == ...)` when needed.
- **Performance benchmarks:** MediaLibrary now includes performance benchmarks for various operations. Use `scripts/diag_media_library_plugin.py --benchmark` to validate changes against performance targets.

## Build & release workflows
- **Editable install:** Most scripts assume `mmst` is installed in editable mode so plugin discovery works. Ensure new entry points respect setuptools metadata (`project.scripts` exposes `mmst` → `core.app:main`).
- **Portable bundles:** `scripts/build.py --portable` creates a self-contained virtualenv with launcher scripts (`run-mmst-portable.bat` / `.sh`). Update the helper if new resources (covers, defaults) need packaging.
- **Artifacts:** Built distributions land in `dist/`; portable archives default to `dist/portable/mmst-portable-<platform>.zip`. Clean up using `build.robust_rmtree` helpers instead of manual shutil removal to avoid Windows locks.

## Adding or extending plugins
- **Layout:** New plugins live under `src/mmst/plugins/<feature>/` with a `plugin.py` exposing `class Plugin(BasePlugin)`. Include a `manifest` property returning `PluginManifest(identifier="mmst.<feature>", ...)`.
- **Threading:** Follow the FileManager pattern—start background work with `concurrent.futures.ThreadPoolExecutor`, emit Qt signals for progress, and guard shared data with locks.
- **UI friendliness:** Mirror existing UI tone—clear button labels, status text, and progress updates (see `FileManagerWidget` translations). Keep controls accessible (spacing, grouping) and remember the dashboard may auto-start plugins.
- **Documentation:** Update the relevant plan in `docs/` (for example, add checklist entries in `system-tools-plan.md`) whenever you complete or schedule significant tasks.
- **Telemetry:** For performance-sensitive components, integrate with the telemetry hooks for query latency and event loop monitoring, following the MediaLibrary pattern.

## Pitfalls & gotchas
- **Duplicate plugin IDs:** `PluginManager.discover()` warns and skips duplicates. Ensure manifests use unique identifiers; tests assert specific ones (`mmst.file_manager`, `mmst.audio_tools`, etc.).
- **Blocking UI:** Never run filesystem or subprocess work directly on the Qt thread. Respect existing `run_duplicate_scan` / `run_backup` patterns.
- **Config drift:** Changing config schemas requires migration helpers—tests expect backwards compatibility. Add versioned keys or migration routines when altering persisted structure.
- **Path handling:** Normalize paths with `Path` objects and avoid string concatenation. Windows UNC paths appear in user environments—use `Path.resolve()` cautiously.
- **Notifications:** If you surface errors, include actionable hints (missing tool, invalid path). The dashboard surfaces color-coded status rows; unclear messages confuse users.
- **Large libraries:** When working with MediaLibrary, test with large datasets (use `scripts/diag_media_library_plugin.py generate`) to ensure your changes maintain performance with 50k+ files.

## Useful fixtures & sample data
- `smart_playlists.json` seeds default smart playlist rules; update it alongside tests when adding new operators.
- `tests/fixtures/` (if added) should mirror production schema—prefer temporary directories and sample media files created on the fly.
- Sample README snapshots (for portable bundles or cached dependencies) under `.pytest_cache` / `.venv` are irrelevant for code changes—ignore them unless packaging scripts explicitly consume them.

## When in doubt
- Read the corresponding doc in `docs/` before changing a subsystem—they spell out design intent and future roadmap.
- Keep the UI approachable: preview states, confirmation dialogs, and inline guidance are valued. Consult existing widget layouts before introducing new patterns.
- Coordinate big changes with updates to this instruction file so future agents inherit the latest practices.
- Refer to the KPIs defined in `NEXT_BIG_UPDATE_PLAN.md` when making performance-related changes, especially for the MediaLibrary.
