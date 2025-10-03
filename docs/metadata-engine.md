# MediaLibrary: Metadaten-Engine

## Überblick

Die Metadaten-Engine ermöglicht das Lesen und Schreiben von Metadaten für Audio-, Video- und Bilddateien direkt aus der MediaLibrary heraus. Die Implementierung orientiert sich an Calibre's Metadata-Editor mit einer benutzerfreundlichen Tabbed-Interface.

## Architektur

### Komponenten

1. **MediaMetadata (Dataclass)**
   - Zentrale Datenstruktur für alle Metadaten
   - ~30 Felder für Common, Audio, Video und Technical Metadata
   - `to_dict()` Methode für Serialisierung

2. **MetadataReader**
   - Liest Metadaten aus Dateien
   - **Audio:** Verwendet `mutagen` für MP3, FLAC, M4A, WAV, OGG
   - **Video:** Verwendet `pymediainfo` für MP4, MKV, AVI, WebM
   - **Graceful Fallback:** Funktioniert auch ohne optionale Dependencies

3. **MetadataWriter**
   - Schreibt Metadaten zurück in Dateien
   - **Audio:** Schreibt ID3/Vorbis/MP4-Tags via `mutagen`
   - **Video:** Noch nicht implementiert (pymediainfo ist read-only)

4. **MetadataEditorDialog**
   - Calibre-ähnliche UI mit 4 Tabs:
     - **Common:** Titel, Künstler, Album, Jahr, Genre, Kommentar
     - **Audio:** Track/Disc-Nummern, Komponist
     - **Video:** Regisseur, Beschreibung, Schauspieler
     - **Technical:** Read-Only Bitrate, Codec, Sample Rate, Resolution
   - Speichern-Button schreibt via MetadataWriter zurück

### Integration in MediaLibrary

- **Doppelklick auf Datei:** Öffnet MetadataEditorDialog
- **Nach Speichern:** Tags werden direkt in Datei geschrieben
- **Status-Updates:** UI zeigt Erfolg/Fehler-Meldungen

## Unterstützte Formate

### Audio (Read & Write)
- MP3 (ID3v2)
- FLAC (Vorbis Comments)
- M4A (iTunes Tags)
- OGG Vorbis
- WAV (INFO/LIST Tags)

### Video (Read-Only)
- MP4
- MKV (Matroska)
- AVI
- WebM

### Metadaten-Felder

**Common Fields:**
- title, artist, album, year, genre, comment
- rating (1-5), tags (list)

**Audio-Specific:**
- track_number, track_total
- disc_number, disc_total
- composer

**Video-Specific:**
- director, actors (list)
- description

**Technical (Read-Only):**
- bitrate, sample_rate, channels
- codec, resolution
- duration, filesize

## Verwendung

```python
from mmst.plugins.media_library.metadata import MetadataReader, MetadataWriter
from pathlib import Path

# Lesen
reader = MetadataReader()
metadata = reader.read(Path("/music/song.mp3"))
print(metadata.title, metadata.artist)

# Schreiben
metadata.title = "Neuer Titel"
metadata.artist = "Neuer Künstler"

writer = MetadataWriter()
success = writer.write(Path("/music/song.mp3"), metadata)
```

## Dependencies

- **mutagen:** Audio-Metadaten (ID3, Vorbis, MP4)
- **pymediainfo:** Video/Container-Metadaten
- Beide sind optional mit graceful fallback

## Tests

12 Unit-Tests decken folgende Bereiche ab:
- MetadataReader: Initialisierung, Nonexistent Files, Audio-Dateien, Dict-Konvertierung
- MetadataWriter: Initialisierung, Fehlerbehandlung
- MediaMetadata: Creation, Dict-Konvertierung, Video-Felder, Technical Info

**Test-Ausführung:**
```bash
python -m pytest tests/test_metadata.py -v
```

## Zukünftige Erweiterungen

- [ ] **Bulk-Editing:** Mehrere Dateien gleichzeitig bearbeiten
- [ ] **SQLite-Integration:** Metadaten in Library-Index cachen
- [ ] **Online-Scraper:** Automatisches Abrufen von Metadaten (TheMovieDB, MusicBrainz)
- [ ] **Video-Writing:** Metadaten in Video-Container schreiben (mkvpropedit)
- [ ] **Cover-Art:** Einbetten und Anzeigen von Album-Art/Poster
