# MediaLibrary: Echtzeit-Ordnerüberwachung (Filesystem Watcher)

## Überblick

Die Echtzeit-Ordnerüberwachung ermöglicht es der MediaLibrary, Änderungen im Dateisystem automatisch zu erkennen und die Datenbank ohne manuelles Neu-Scannen zu aktualisieren. Die Implementierung basiert auf der `watchdog`-Bibliothek.

## Architektur

### Komponenten

1. **FileSystemWatcher**
   - Wrapper um watchdog's Observer
   - Verwaltet watched paths und event callbacks
   - Thread-safe Start/Stop-Mechanismen
   - Graceful Fallback wenn watchdog nicht verfügbar

2. **MediaFileHandler** (watchdog.events.FileSystemEventHandler)
   - Filtert Events auf Mediendateien (Audio/Video/Bild)
   - Unterstützt 20+ Dateiformate
   - Ruft Callbacks für created/modified/deleted/moved auf

3. **LibraryIndex-Erweiterungen**
   - `add_file_by_path()`: Fügt einzelne Datei zum Index hinzu
   - `update_file_by_path()`: Aktualisiert Metadaten einer Datei
   - `remove_file_by_path()`: Entfernt Datei aus Index
   - Automatische Source-Zuordnung basierend auf Pfad

### Integration in MediaLibrary Plugin

- **Auto-Start:** Watcher startet automatisch wenn Plugin aktiviert wird (falls enabled)
- **Event-Callbacks:** Filesystem-Events → SQLite-Updates → UI-Refresh
- **UI-Toggle:** Checkbox "Automatische Aktualisierung bei Dateiänderungen"
- **Status-Anzeige:** "Überwachung: Aktiv (N Quellen)" / "Inaktiv"

## Unterstützte Events

### File Created
- Neue Mediendatei erkannt → `LibraryIndex.add_file_by_path()`
- UI wird automatisch aktualisiert (neue Zeile in Tabelle)
- Log: "Indexed new file: filename.mp3"

### File Modified
- Metadaten-Änderung erkannt → `LibraryIndex.update_file_by_path()`
- Aktualisiert size/mtime in SQLite
- Log: "Updated file: filename.mp3"

### File Deleted
- Datei gelöscht → `LibraryIndex.remove_file_by_path()`
- UI wird automatisch aktualisiert (Zeile entfernt)
- Log: "Removed file from index: filename.mp3"

### File Moved/Renamed
- Datei verschoben → Remove old + Add new
- Funktioniert auch über Ordnergrenzen innerhalb derselben Source
- Log: "File moved: oldname.mp3 -> newname.mp3"

## Unterstützte Dateiformate

Der Watcher filtert automatisch auf folgende Media-Dateien:

**Audio:** `.mp3`, `.flac`, `.m4a`, `.wav`, `.ogg`, `.aac`, `.wma`

**Video:** `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`

**Images:** `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`

Alle anderen Dateien (`.txt`, `.doc`, `.exe`, etc.) werden ignoriert.

## Verwendung

### Programmatische Nutzung

```python
from mmst.plugins.media_library.watcher import FileSystemWatcher
from pathlib import Path

# Watcher erstellen
watcher = FileSystemWatcher()

# Callbacks definieren
def on_created(path: Path):
    print(f"New file: {path}")

def on_deleted(path: Path):
    print(f"Deleted: {path}")

# Watcher starten
watcher.start(
    on_created=on_created,
    on_deleted=on_deleted,
)

# Pfad hinzufügen
watcher.add_path(Path("/media/music"), recursive=True)

# ... Watcher läuft im Hintergrund ...

# Watcher stoppen
watcher.stop()
```

### UI-Verwendung

1. **MediaLibrary Plugin starten**
2. **Quellen hinzufügen** (z.B. "D:/Musik", "E:/Videos")
3. **Checkbox aktivieren:** "Automatische Aktualisierung bei Dateiänderungen"
4. **Status prüfen:** "Überwachung: Aktiv (2 Quellen)"

Jetzt werden alle Dateiänderungen in diesen Ordnern automatisch erkannt!

## Technische Details

### Threading
- Watchdog Observer läuft in eigenem Thread
- Events werden asynchron verarbeitet
- SQLite-Writes sind thread-safe (WAL mode)
- UI-Updates über Qt Signals (thread-safe)

### Performance
- Kein Polling, event-basiert (effizient)
- Nur Media-Dateien werden verarbeitet
- Recursive watching möglich
- Geringe CPU-Last im Idle

### Fehlerbehandlung
- Graceful Fallback wenn watchdog fehlt
- Ungültige Pfade werden ignoriert
- Exceptions in Callbacks werden geloggt
- Watcher kann jederzeit neu gestartet werden

## Tests

15 Unit-Tests decken folgende Bereiche ab:

**MediaFileHandler:**
- Handler Creation
- Media file detection (case-insensitive)
- Extension filtering

**FileSystemWatcher:**
- Initialization & availability check
- Start/Stop lifecycle
- Add/Remove paths
- Multiple paths watching
- Callback registration
- Error handling (invalid paths, double start, etc.)

**Integration Tests (marked slow):**
- Real file creation detection
- Non-media file filtering

**Test-Ausführung:**
```bash
# Schnelle Tests
python -m pytest tests/test_watcher.py -v -k "not slow"

# Alle Tests (inkl. Integration)
python -m pytest tests/test_watcher.py -v
```

## Dependencies

- **watchdog>=4.0:** Filesystem event monitoring
- Optional mit graceful fallback
- Cross-platform (Windows/Linux/macOS)

## Zukünftige Erweiterungen

- [ ] **Ignore Patterns:** `.gitignore`-Style patterns zum Filtern
- [ ] **Batch Updates:** Mehrere Events zusammenfassen für Performance
- [ ] **Network Shares:** Bessere Unterstützung für Netzlaufwerke
- [ ] **Manual Refresh:** Button zum Force-Rescan trotz Watcher
- [ ] **Watch Statistics:** Zeige Anzahl erkannter Events
