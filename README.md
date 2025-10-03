# Modular Media & System Toolkit (MMST)

MMST ist ein modulares Dashboard, das ein gemeinsames Core-System mit spezialisierten Plugins kombiniert.
Der Core verwaltet Lebenszyklus, Benutzeroberfläche und gemeinsame Dienste, während Plugins einzelne Werkzeuge
(z. B. Dateiverwaltung oder Audio-Bearbeitung) kapseln.

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
| `FileManagerPlugin` (`mmst.file_manager`) | Duplikat-Scanner mit Hash-Gruppierung, sicherer Löschfunktion und dateibasierten Backups | Prototyp |
| `AudioToolsPlugin` (`mmst.audio_tools`) | Equalizer- und Recorder-Oberfläche mit per-Gerät-Presets, Qualitätsprofilen und konfigurierbarem Aufnahmeziel | Scaffold |

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
│           └── file_manager/
│               ├── plugin.py
│               ├── backup.py
│               └── scanner.py
└── tests/
    ├── test_audio_device_service.py
    ├── test_audio_tools_plugin.py
    ├── test_backup.py
    ├── test_config_store.py
    ├── test_duplicate_scanner.py
    └── test_plugin_manager.py
```

## Schnellstart

1. **Abhängigkeiten installieren**

   ```powershell
   cd c:\Users\jerom\Desktop\plugin-pySys
   python -m pip install -e .[dev]
   ```

  > PySide6 ist erforderlich, um das Dashboard auszuführen. Die optionale `dev`-Gruppe installiert `pytest`. Für die
  > Löschfunktion des Duplikat-Scanners empfiehlt sich zusätzlich `send2trash` (wird automatisch mit der `dev`-Gruppe
  > installiert).

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
- MediaLibrary- und SystemTools-Plugins vorbereiten.
- Plugin-Konfigurationsdialoge implementieren (z. B. Hash-Algorithmus im Duplikat-Scanner).
- Ereignisbus erweitern (z. B. Toast-Benachrichtigungen im UI darstellen).
