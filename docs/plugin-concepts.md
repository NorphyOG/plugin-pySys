# Plugin Concepts Roadmap

This document records the detailed concepts for every planned MMST plugin. It aligns the feature wishlist with the existing core architecture (plugin base classes, services, config store, and notification center) and highlights dependencies, UI structure, and phased delivery plans.

## Cross-Cutting Architecture

- **Plugin Shell**: Each plugin exposes a `Plugin` class derived from `BasePlugin` with a manifest and a Qt-based view widget. Long-running jobs (scans, conversions, streaming) should execute in worker threads or subprocesses to keep the UI responsive.
- **Configuration**: Persist user preferences using `CoreServices.get_plugin_config()`. Store plugin state under the plugin identifier (for example `audio_tools.presets`). Use JSON-friendly dictionaries and keep schema documented.
- **Notifications**: Use `CoreServices.send_notification()` for status updates (scan completed, metadata fetched, backup finished) so messages appear in the dashboard and logs.
- **Background Work**: Provide cancellable jobs via a shared thread pool abstraction (future core enhancement) to prevent GUI freezes.
- **Capability Checks**: Wrap platform-specific operations behind detection routines and show friendly guidance when tooling is missing or a feature is unavailable on the current OS.
- **Testing Strategy**: Add unit tests for pure logic (preset math, hash pipelines, metadata parsing) and integration tests for orchestration. GUI behaviour can later leverage Qt Test or screenshot comparison.

---

## Plugin 1 – `AudioToolsPlugin`

### Mission & Scope (AudioTools)

Deliver a high-fidelity audio manipulation hub combining a multi-source equalizer and a lossless audio recorder with preset management.

### UI Composition (AudioTools)

- **Root Layout**: Two tabs (`Equalizer`, `Recorder`).

- **Equalizer Tab**:
  - Source selector (`QComboBox`) listing detected output/input devices and application-specific endpoints.
  - 10-band EQ sliders (`QSlider` vertical, labelled 31 Hz to 16 kHz) with numeric value display.
  - Preset toolbar (Save / Load / Delete / Reset) plus combo box for quick selection.
  - Real-time spectrum preview (optional stretch goal using PyQtGraph).

- **Recorder Tab**:
  - Source selector (shares detection logic with EQ).
  - Record/Stop button with elapsed time display.
  - Metadata form dialog (`QDialog`) triggered on stop (Title, Artist, Album, Genre, Comments).
  - Quality settings button opening a dialog for sample rate, bit depth, channel count.
  - Recent recordings list with open-in-folder action.

### Core Workflows (AudioTools)

1. **Source Discovery**: Abstract device enumeration per platform — Windows via `pycaw` (WASAPI), Linux via `pulsectl` (PulseAudio) or PipeWire bindings.
2. **Equalizer Processing**: Apply filters via backend DSP (e.g., `scipy.signal`, `pyAudioDSP`) on captured streams; MVP can focus on microphone capture before system-wide routing.
3. **Preset Management**: Serialize slider values and metadata to the config store under `eq.presets`, including last-selected preset.
4. **Recording Pipeline**: Capture PCM at 48 kHz / 24-bit using `sounddevice` or `pyaudio`, stream to `wave` writer, and embed metadata via `mutagen`.
5. **Quality Adjustment**: Optional resampling using `librosa` or `soundfile` when user selects lower quality profiles.

### Configuration Keys (AudioTools)

```json
{
  "device": "default_output",
  "eq": {
    "band_gains": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "preset": "Flat",
    "presets": {
      "Bass Boost": [6, 5, 4, 2, 0, -1, -2, -3, -5, -6]
    }
  },
  "recorder": {
    "device": "default_input",
    "quality": {
      "sample_rate": 48000,
      "bit_depth": 24,
      "channels": 2
    },
    "output_dir": "~/Music/Recordings"
  }
}
```

### Dependencies & Risks (AudioTools)

- Python packages: `pycaw`, `pulsectl`, `sounddevice`, `mutagen`, optional `pyqtgraph`.
- Elevated privileges may be required for capturing certain system outputs.
- Real-time EQ across arbitrary sources is complex; plan incremental rollout (microphone first, then loopback, then per-application streams).

### Implementation Phases (AudioTools)

1. Build UI skeleton with mock device list and preset persistence.
2. Add recording pipeline for microphone input with metadata dialog.
3. Introduce EQ DSP for a single platform (likely Windows) and validate latency.
4. Expand source support and visualization, then polish presets and quality profiles.

---

## Plugin 2 – `FileManagerPlugin`

### Mission & Scope (FileManager)

Provide fast duplicate detection and simple, reliable folder backups across platforms.

### UI Composition (FileManager)

- **Root Layout**: Two tabs (`Duplicate Scanner`, `Backup`).

- **Duplicate Scanner Tab**:
  - Directory picker (`QFileDialog`) and include-subfolders toggle.
  - Scan button with progress bar.
  - Results tree (`QTreeWidget`): top-level nodes represent duplicate groups, child rows list file paths, size, modified date, with checkboxes for deletion.
  - Action bar: `Delete Selected`, `Open Location`, `Export Report` (CSV/JSON).
    - Action bar now exposes `Open Location` to launch the containing folder for a highlighted duplicate along with `Delete Selected` and future report actions.

- **Backup Tab**:
  - Source folder picker and target folder picker.
  - Options: `Mirror`, `Incremental`, `Dry Run`, `Preserve timestamps` checkbox.
  - Run button with log console summarizing copied/skipped/error counts.

### Core Workflows (FileManager)

1. **Duplicate Scan Pipeline**: Group files by size, hash first chunk (1 MB), then full SHA-256 for candidates. Use thread pool with cancellation support.
2. **Deletion Flow**: Move files to OS recycle bin via `send2trash` by default, optionally allow permanent deletion. Refresh view after actions.
3. **Backup Execution**: Compare source vs. target metadata (size, mtime) to determine copy list. Use `shutil.copy2` for metadata preservation, delete orphans in mirror mode with confirmation.
4. **Reporting**: Persist last scan report to config (`duplicate_scanner.last_report`) for quick reload and export to CSV/JSON.

### Configuration Keys (FileManager)

```json
{
  "duplicate_scanner": {
    "last_path": "C:/Users/example",
    "hash_algorithm": "sha256",
    "trash_deletion": true
  },
  "backup": {
    "source": "D:/Media",
    "target": "E:/Backups/Media",
    "mode": "incremental",
    "preserve_timestamps": true
  }
}
```

### Dependencies & Risks (FileManager)

- Python packages: `send2trash`, `tqdm` (optional), built-in `hashlib`/`pathlib`.
- Large directory scans require memory-conscious batching and responsive progress reporting.
- Deletion operations must always confirm and support undo via recycle bin by default.

### Implementation Phases (FileManager)

1. Implement hashing engine with CLI-style progress (no GUI).
2. Layer Qt UI, integrate with config, and support deletion workflow.
3. Add backup orchestration with dry-run preview and logging.
4. Polish UX: scheduling hooks, report exports, notifications.

---

## Plugin 3 – `MediaLibraryPlugin`

### Mission & Scope (MediaLibrary)

Act as a media control center with Netflix-style browsing, metadata enrichment, and external player integration.

### UI Composition (MediaLibrary)

- **Main View**: Grid of cover tiles (`FlowLayout` or custom view) with hover quick actions (play, edit metadata, open folder).
- **Detail Drawer**: Slides in with synopsis, metadata, tags, file details, and configurable action buttons when an item is selected.
- **Toolbar**: Library selector (drop-down), search box, genre filter, rating slider, tag chips, refresh button.

### Core Workflows (MediaLibrary)

1. **Library Management**: Persist library roots in config, watch folders with `watchdog`, and maintain plugin-specific SQLite database for indexed media.
2. **Metadata Enrichment**: Parse filenames with `guessit`, query APIs (OMDb, TMDb, MusicBrainz) with cached responses, and download cover art to cache directory.
3. **Metadata Editing**: Provide editor dialog using `mutagen` for audio tags and `pymediainfo` for video sidecars. Store normalized data in SQLite and optionally commit to file metadata.
4. **Playback Launching**: Determine external player association from config and spawn via `subprocess.Popen`.
5. **Calibre Integration (Optional)**: When library type equals `calibre`, read `metadata.db` and map books into shared grid with e-book specific metadata.

### Configuration Keys (MediaLibrary)

```json
{
  "libraries": [
    {"id": "movies", "path": "D:/Videos", "type": "video"},
    {"id": "ebooks", "path": "D:/Books", "type": "calibre", "db": "metadata.db"}
  ],
  "metadata": {
    "providers": ["tmdb", "musicbrainz"],
    "api_keys": {"tmdb": "API_KEY"},
    "cache_ttl_days": 14
  },
  "associations": {
    ".mkv": "C:/Program Files/VLC/vlc.exe",
    ".mp3": "/usr/bin/audacious"
  },
  "filters": {
    "last_view": "all",
    "sort": "title"
  }
}
```

### Dependencies & Risks (MediaLibrary)

- Python packages: `watchdog`, `guessit`, `requests` or `aiohttp`, `mutagen`, `pymediainfo`, optional `sqlalchemy`.
- API rate limits require caching and exponential backoff strategies.
- Thumbnail generation for large libraries needs batching and worker pools to avoid UI stalls.

### Implementation Phases (MediaLibrary)

1. Baseline library scanning and static grid UI with local metadata only.
2. (Enhanced Mode Incremental) Introduce optional enhanced widget gated by `MMST_MEDIA_LIBRARY_ENHANCED` / config flag.
3. Add table + gallery hybrid, detail panel, shelves (recent/top rated/tags).
4. Integrate filesystem watcher (debounced refresh) and smart playlist filtering.

#### Enhanced Mode Additions (Current Status)

The enhanced Media Library path is additive and opt-in:

- Filesystem Watcher: Starts automatically when watchdog is installed, watching all indexed sources. Events batch-refresh table, gallery, and shelves after 250 ms of inactivity.
- Smart Playlists: Header combo lists available playlists loaded from user data `smart_playlists.json` or bundled default. Selection filters before other UI filters and persists in `enhanced_state.smart_playlist`.
- Batch Actions: Multi-row selection exposes a bar to set rating or append tags to all selected entries.
- Attribute Filters: Header provides a minimum rating selector (≥ ★..★★ etc.) plus a tag filter field (comma-separated; matches any tag). These filters layer on top of smart playlist results and persist in `enhanced_state.rating_filter_min` / `enhanced_state.tag_filter`.
- Lazy Gallery Loading: Gallery first paints an initial batch (default 40) of cover thumbnails, then queues the remainder on a short timer to keep UI responsive for large libraries.

Headless safety: All PySide6 interactions are guarded by try/except with stub fallbacks so existing tests continue to execute without the GUI stack.
2. (Enhanced mode placeholder) Persist lightweight UI state under `enhanced_state` when feature flag `MMST_MEDIA_LIBRARY_ENHANCED` or config key `enhanced_enabled` is set.

#### Enhanced Mode State Persistence

The experimental enhanced UI (opt‑in) stores a small dictionary under the plugin config key `enhanced_state`:

```json
{
  "view_mode": "table" | "gallery" | "split",
  "dashboard_visible": true,
  "selected_path": "C:/path/to/file.ext"
}
```

All keys are optional; absence implies defaults (table view, dashboard visible, no current selection). This bucket is safe to evolve with additional fields like playback position or filter presets; consumers must treat missing keys as defaults. The minimal restored widget ignores these values so legacy tests remain stable.
2. Add metadata fetching (one provider) and cover cache.
3. Implement detail editor, external player hooks, and SQLite persistence.
4. Introduce real-time monitoring and Calibre adapter.

---

## Plugin 4 – `SystemToolsPlugin`

### Mission & Scope (SystemTools)

Bundle essential conversion utilities and system health dashboards while keeping risky hardware controls optional.

### UI Composition (SystemTools)

- **Navigation**: Sidebar listing `Converter`, `Image Compression`, `Drive Health`, (future) `Fan Control`.

- **Converter Panel**:
  - Drag-and-drop file area (`QListWidget` accepting drops).
  - Target format dropdown populated per file type.
  - Conversion queue table with progress bars and status icons.
  - Settings dialog for tool paths and concurrency.

- **Image Compression Panel**:
  - Thumbnail list of selected images.
  - Quality slider (0–100), output format selector, estimated size preview.
  - Batch convert button with optional metadata stripping.

- **Drive Health Panel**:
  - Table of drives (name, model, temperature, SMART status, power-on hours).
  - Refresh button and auto-refresh toggle.
  - Detailed popup with SMART attribute breakdown and notification thresholds.

- **Fan Control (Experimental)**:
  - Hidden/disabled by default; only enabled when vendor SDK is detected. Shows a curve editor for temperature vs PWM.

### Core Workflows (SystemTools)

1. **Tool Discovery**: Probe for `ffmpeg`, `ffprobe`, `magick`/`convert`, `pdftotext`, `smartctl` on startup; persist overrides in config.
2. **Conversion Engine**: Map conversion recipes (input extension → command template) and run subprocesses with progress parsing (ffmpeg stderr). Support concurrent jobs with bounded queue.
3. **Image Compression**: Use `Pillow` or ImageMagick to compute previews, apply compression, and handle EXIF metadata stripping if requested.
4. **Drive Health Monitoring**: On Windows use PowerShell `Get-PhysicalDisk` or WMI; on Linux call `smartctl -H -A /dev/sdX`. Cache results and surface alerts through notification center.
5. **Fan Control Exploration**: Detect vendor-specific SDKs (ASUS, MSI, etc.) or Linux `fancontrol`. Gate feature behind explicit capability flag and multilayer warnings.

### Configuration Keys (SystemTools)

```json
{
  "tools": {
    "ffmpeg": "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
    "imagemagick": "magick",
    "smartctl": "/usr/sbin/smartctl"
  },
  "converter": {
    "concurrency": 2,
    "profiles": {
      "mp4_to_mp3": {"bitrate": "192k"}
    }
  },
  "image": {
    "quality": 80,
    "strip_metadata": true
  },
  "drive_health": {
    "auto_refresh_minutes": 30,
    "alerts": {
      "temperature_c": 60,
      "smart_status": "warning"
    }
  }
}
```

### Dependencies & Risks (SystemTools)

- Python packages: `Pillow`, optional `psutil` for drive enumeration.
- External executables must be installed separately; provide helper dialogs to guide users.
- Elevated privileges may be required for SMART queries, especially on Windows.
- Fan control is hardware-vendor specific; keep behind experimental flag until validated.

### Implementation Phases (SystemTools)

1. Implement conversion queue with FFmpeg integration and progress feedback.
2. Add image compression module with previews and batch operations.
3. Implement cross-platform drive health polling (read-only) and alerting.
4. Investigate fan control feasibility per platform, gated behind capability flag.

---

## Next Steps & Integration Checklist

1. **Prototype Order**: Start with `FileManagerPlugin` (lowest external dependencies), then tackle `SystemToolsPlugin` conversions, followed by `MediaLibraryPlugin`, and finally incrementally build `AudioToolsPlugin` hardware integrations.
2. **Core Enhancements Needed**:

    - Background job runner service (thread pool abstraction) shared across plugins.
    - Unified settings dialog leveraging the config store for persisted plugin options.
    - Extension points for plugin-specific notifications (icons, severity levels).

3. **Documentation**: Update `README.md` with plugin summaries and link to this concept document.
4. **Testing Infrastructure**: Set up fixtures for temporary directories, mocked external tools, and sample media files to support unit and integration tests.
5. **Licensing & API Keys**: Track external API terms (TMDb, MusicBrainz). Provide secure storage guidance for keys (for example, environment variables injected into the config store on demand).

This concept blueprint should serve as a reference when implementing each plugin, enabling cohesive UX and predictable integration with the MMST core platform.
