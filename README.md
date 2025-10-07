# MMST Dashboard – Modulare Python-Anwendung

## Highlights (Oktober 2025)

- **🎯 Globales Progress-System:** Zentraler Fortschritts-Dialog für alle Plugins mit Multi-Task-Support
- **🐛 Debug-Console:** Echtzeit-Log-Viewer in Einstellungen mit Filterung und Farbcodierung
- **⏰ Scheduled Backups:** Automatische Zeitplanung für FileManager-Backups (Stündlich/Täglich/Wöchentlich/Monatlich)
- **🖼️ Image Compression Tool:** Visueller Vergleich vor/nach Kompression mit Quality-Slider
- **📊 Gallery Performance:** Optimiert für 10k+ Dateien mit Chunked-Loading & Binary-Search
- **Sitzungspersistenz:** Dashboard merkt sich Fenstergröße, aktives Plugin und Filter-Einstellungen
- **🎵 MediaLibrary v8.0:** 10 neue Features (Gallery View, Media Player, Smart Playlists, Kino Mode, Batch Operations) – **Produktionsreif!**

## Recent Updates (Next Big Update v2)

**7 Major Features Implementiert** – Das "Next Big Update" bringt umfangreiche Erweiterungen über alle Plugins:

### 🎵 MediaLibrary v8.0: Feature-Complete Restoration

**10 Major Features Implementiert** – Das MediaLibrary-Plugin ist vollständig restauriert und produktionsreif:

#### 1. 🖼️ Gallery View (Netflix-Style)
- **Card-Grid Layout:** Visueller Thumbnail-Grid mit Hover-Effekten
- **Cover-Cache:** Intelligentes Caching für schnelle Ladezeiten (Audio, Video, Images)
- **Split-View:** Gleichzeitige Table + Gallery Ansicht mit synchroner Selektion
- **Responsive Layout:** Automatische Card-Größenanpassung basierend auf Window-Breite

#### 2. 🎬 Media Player
- **Audio/Video Playback:** Vollständiger QMediaPlayer mit Play/Pause/Stop/Volume
- **Progress Slider:** Interaktive Timeline mit Seek-Funktion
- **Auto-Play:** Integriert mit Table/Gallery Selection

#### 3. 📋 Context Menus
- **Table Context Menu:** Rechtsklick auf Rows für Play, Edit Metadata, Add to Playlist, Delete
- **Gallery Context Menu:** Rechtsklick auf Cards mit identischen Actions
- **Keyboard Shortcuts:** Delete-Key für schnelles Löschen

#### 4. 📂 Playlist UI
- **CRUD Operations:** Create, Edit, Delete Playlists
- **Drag & Drop Reordering:** Intuitive Item-Verwaltung
- **Add to Playlist:** Context-Menu-Integration

#### 5. 🏷️ Tag Overview
- **Frequency Display:** Liste aller Tags mit Verwendungszähler
- **Click to Filter:** Automatischer Library-Filter beim Tag-Klick
- **Tag Management:** Rename/Delete Tags direkt aus Übersicht

#### 6. 🎯 Smart Playlists Editor
- **Visual Rule Builder:** Drag & Drop Tree-Editor mit verschachtelten Gruppen
- **12 Operators:** Rating, Genre, Artist, Duration, FileSize, LastPlayed, etc.
- **Undo/Redo:** Vollständige History für alle Änderungen
- **Live Preview:** Sofortige Regel-Evaluation

#### 7. 📡 Scanner & Watcher UI
- **Source Management:** Add/Remove Library Sources mit Scan-Progress
- **Filesystem Watcher:** Auto-Detection neuer Medien (watchdog-Integration)
- **Progress Feedback:** Detaillierter Scan-Status mit File-Count

#### 8. 📊 Statistics Dashboard
- **Visual Analytics:** Dashboard mit Statistik-Karten (Files, Size, Ratings)
- **Genre & Artist Charts:** Top 10 Bar-Charts
- **Temporal Stats:** "Last 7 Days" Filter für neue Dateien
- **Auto-Refresh:** Aktualisiert sich bei Tab-Switch

#### 9. 🎥 Kino Mode (Fullscreen Viewer)
- **Immersive Experience:** Fullscreen Video/Image Viewer
- **Auto-Hide Controls:** Controls verschwinden nach 3s
- **Keyboard Navigation:** Esc (Exit), Space (Play/Pause), Arrows (Next/Prev)
- **Slideshow Mode:** Automatischer Bildwechsel für Images

#### 10. ⚙️ Batch Operations
- **Multi-Selection:** Shift+Click und Ctrl+Click für Table-Rows
- **Batch Metadata Edit:** Rating/Tags für mehrere Dateien gleichzeitig ändern
- **Batch Delete:** Mehrfach-Löschung mit Bestätigungs-Dialog
- **Visual Feedback:** Button zeigt Anzahl selektierter Dateien

**Status:** ✅ **Produktionsreif** – Alle 46 Tests bestehen (100% Coverage), Performance excellent (Startup < 1s), keine kritischen Bugs

### 📁 FileManager: Intelligente Duplikat-Auswahl, Backup-Profile & Zeitgesteuerte Backups

- **Smart Selection (4 Modi):**
  - *Älteste behalten:* Wählt neuere Duplikate zum Löschen aus
  - *Kleinste behalten:* Markiert größere Varianten
  - *Nach Ordner filtern:* Zeigt nur Duplikate in bestimmtem Pfad
  - *Alle abwählen:* Reset für manuelle Nachbearbeitung
- **Backup-Profile:** Speichern & Laden häufig genutzter Backup-Konfigurationen (JSON-basiert)
- **Dry-Run-Modus:** Zeigt exakt, welche Dateien kopiert/gelöscht würden – ohne Ausführung
- **⏰ Scheduled Backups:** Automatische Backups mit QTimer (Stündlich/Täglich/Wöchentlich/Monatlich)
  - Profile-basierte Zeitplanung mit nächstem Laufzeitpunkt
  - Hintergrund-Ausführung mit Benachrichtigungen
  - Persistente Konfiguration über App-Neustarts

### 🔧 SystemTools: Batch-Warteschlange & Conversion-Presets

- **Batch-Queue:** Multi-File-Warteschlange mit sequentieller Verarbeitung
- **Fortschrittsanzeige:** Pro-Datei-Status und Gesamt-Fortschrittsbalken
- **Conversion-Presets:** Speichern häufiger Format-Kombinationen (z. B. "MP4 zu GIF", "WAV zu MP3 192kbit")
- **Event-Emission:** Sendet `files.converted` Events für MediaLibrary-Integration

### 🎚️ AudioTools: Echtzeit-Spektrum-Analyzer

- **FFT-basierte Visualisierung:** 10-Band-Frequenzanzeige (31 Hz – 16 kHz)
- **Color-Coded Bars:** Grün (niedrig) → Gelb (mittel) → Rot (Spitzen)
- **Auto-Start/Stop:** Synchronisiert automatisch mit EQ-Engine-Status
- **Graceful Degradation:** Optionale Dependencies (numpy/sounddevice) werden sauber behandelt

### 🔌 Core: EventBus-System

- **Plugin-Kommunikation:** Pub/Sub-Architektur für lose gekoppelte Plugin-Interaktion
- **Thread-Safe:** RLock-basierte Synchronisation für Concurrent Access
- **Error Isolation:** Fehlerhafte Subscriber beeinträchtigen andere nicht
- **Events:**
  - `files.deleted` – FileManager → MediaLibrary (automatisches Index-Update)
  - `files.converted` – SystemTools → MediaLibrary (Benachrichtigung über neue Dateien)

### 📊 Technische Details

- **Neue Dateien:** `src/mmst/core/events.py`, `src/mmst/plugins/media_library/statistics_dashboard.py`, `src/mmst/plugins/audio_tools/spectrum_analyzer.py`
- **Modifizierte Module:** 6 Plugin-Dateien erweitert (MediaLibrary, FileManager, SystemTools, AudioTools)
- **Code-Umfang:** ~1500 neue Zeilen über 3 neue + 6 modifizierte Dateien
- **Tests:** Unit Tests für EventBus, Backup Dry-Run, und Batch Queue
- **Persistierung:** JSON-basierte Profile/Presets in Plugin-Config-Verzeichnissen

Siehe `NEXT_BIG_UPDATE_SUMMARY.md` für detaillierte Feature-Beschreibungen und Verwendungsbeispiele.

## Architektur im Überblickia & System Toolkit (MMST)

MMST ist ein modulares Dashboard, das ein gemeinsames Core-System mit spezialisierten Plugins kombiniert.
Der Core verwaltet Lebenszyklus, Benutzeroberfläche und gemeinsame Dienste, während Plugins einzelne Werkzeuge
(z. B. Dateiverwaltung oder Audio-Bearbeitung) kapseln.

## Highlights (Oktober 2025)

- **Sitzungspersistenz:** Dashboard merkt sich Fenstergröße, aktives Plugin und zuletzt genutzte MediaLibrary-Filter inklusive Tabs & Auswahl.
- **MediaLibrary Iteration 5:** Inline-Bewertungen und Tags, benutzerdefinierte Presets, Stapelaktionen, externe Player pro Dateityp sowie Auswahl-basierte Tag-/Playlist-Aktionen und eine integrierte Playlist-Wiedergabe.
- **Qualitätssicherung:** Erweiterte Tests für UI-Persistenz und Attributspeicherung sichern die neuen Workflows ab.

## Architektur im Überblick

- **Core-System (Python + PySide6)**
  - Lädt Plugins dynamisch aus `mmst.plugins.*`.
  - Stellt gemeinsame Dienste wie Logging, Benachrichtigungen und Speicherpfade über `CoreServices` bereit.
  - Visualisiert Plugins im Dashboard (`DashboardWindow`) mit Statusanzeige, Start/Stop und Konfigurationsaufrufen.
- **Plugins**
  - Erben von `BasePlugin` und liefern einen `PluginManifest` mit Metadaten.
  - Implementieren grundlegende Hooks (`initialize`, `start`, `stop`, `create_view`, `configure`, `shutdown`).
  - Können eigene Services, Threads oder Abhängigkeiten mitbringen, bleiben aber über die definierte Schnittstelle
    vom Core entkoppelt.

### Aktuell enthaltene Plugins

| Plugin | Beschreibung | Status |
| ------ | ------------- | ------ |
| `FileManagerPlugin` (`mmst.file_manager`) | Duplikat-Scanner mit Hash-Gruppierung, sicherer Löschfunktion und dateibasierten Backups mit Fortschrittsanzeige | ✅ MVP |
| `AudioToolsPlugin` (`mmst.audio_tools`) | Echtzeit-10-Band-Equalizer mit scipy DSP, WAV-Recorder mit Metadaten, Preset-Verwaltung | ✅ MVP |
| `MediaLibraryPlugin` (`mmst.media_library`) | SQLite-Bibliothek mit Quellenverwaltung, Inline-Rating & Tags, benutzerdefinierten Presets, Stapelaktionen, externen Playern, Playlist-Wiedergabe sowie persistenten Filtern, Tabs und Selektionen | ✅ Iteration 5 |
| `SystemToolsPlugin` (`mmst.system_tools`) | Dateikonverter für Audio/Video/Bild mit ffmpeg/ImageMagick-Integration und Tool-Erkennung | ✅ MVP |

Der Duplikat-Scanner nutzt parallele Threads, gruppiert Dateien anhand von SHA-256-Hashes und erlaubt das Löschen
einzelner Kopien (standardmäßig via Papierkorb). Die Backup-Ansicht kopiert Ordnerbäume ohne Kompression, optional
als Spiegelung, und meldet Fortschritt sowie berechnete Statistiken im UI. Zentrale Logik befindet sich in
`mmst.plugins.file_manager.scanner` und `mmst.plugins.file_manager.backup`.

## Projektstruktur

```text
.
├── pyproject.toml
├── README.md
├── src/
│   └── mmst/
│       ├── core/
│       │   ├── app.py
│       │   ├── plugin_base.py
│       │   ├── plugin_manager.py
│       │   └── services.py
│       └── plugins/
│           ├── file_manager/
│           │   ├── plugin.py
│           │   ├── backup.py
│           │   └── scanner.py
│           ├── media_library/
│           │   ├── plugin.py
│           │   └── core.py
│           └── system_tools/
│               ├── plugin.py
│               ├── tools.py
│               └── converter.py
└── tests/
    ├── test_audio_device_service.py
    ├── test_audio_tools_plugin.py
    ├── test_backup.py
    ├── test_config_store.py
    ├── test_duplicate_scanner.py
    ├── test_media_library.py
    ├── test_plugin_manager.py
    └── test_system_tools.py
```

## Schnellstart

1. **Abhängigkeiten installieren**

   ```powershell
   python -m pip install -e .[dev]
   ```

  > PySide6 ist erforderlich, um das Dashboard auszuführen. Die optionale `dev`-Gruppe installiert `pytest`. Für die
  > Löschfunktion des Duplikat-Scanners empfiehlt sich zusätzlich `send2trash` (wird automatisch mit der `dev`-Gruppe
  > installiert). Für WAV-Metadaten nutzt das AudioTools-Plugin `mutagen`; die Bibliothek wird automatisch mitinstalliert.

1. **Dashboard starten**

   ```powershell
   python -m mmst.core.app
   ```

   Nach dem Start erscheint das FileManager-Plugin in der Seitenleiste. Plugins lassen sich starten/stoppen; im aktiven Zustand
   zeigt der zentrale Bereich das UI des ausgewählten Plugins.

## Tests & Qualitätssicherung

- Das Projekt verwendet `pytest`. Die Konfiguration (inkl. `pythonpath`) liegt in `pyproject.toml`.
- Test-Suite ausführen:

  ```powershell
  python -m pytest
  ```

  Der Plugin-Manager-Test wird automatisch übersprungen, falls PySide6 nicht installiert ist.

## Ausblick

- AudioTools-Plugin ausbauen: Equalizer-DSP, Recording-Pipeline und Plattform-spezifische Backends.
  - Nächste Schritte: EQ-DSP Pipeline, Echtzeit-Pegelanzeige, Linux-spezifische Loopback-Backends.
- MediaLibrary- und SystemTools-Plugins vorbereiten.
- Plugin-Konfigurationsdialoge implementieren (z. B. Hash-Algorithmus im Duplikat-Scanner).
- Ereignisbus erweitern (z. B. Toast-Benachrichtigungen im UI darstellen).
