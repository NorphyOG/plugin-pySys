# Projektplan: Modulares Medien- & System-Toolkit (MMST)

**Version: 3.0**
**Letzte Aktualisierung: 2025-10-03**

## 1. Vision & Ziele

Das MMST soll eine plattformübergreifende (Windows & Linux) Python-Anwendung werden, die eine Vielzahl von Medien- und Systemaufgaben über eine einheitliche, plugin-basierte Architektur zugänglich macht. Der Fokus liegt auf Erweiterbarkeit, Benutzerfreundlichkeit und mächtigen Werkzeugen für Power-User.

**Kernprinzipien:**

- **Modularität:** Jede Kernfunktion ist ein eigenständiges Plugin.
- **Performance:** Langwierige Operationen blockieren niemals die Benutzeroberfläche.
- **Plattformunabhängigkeit:** Saubere Backends mit generischen Fallbacks.
- **Transparenz:** Der Nutzer hat stets Kontrolle und Einblick in die Prozesse.

---

## 2. Globale Projekt-Roadmap (Meilensteine)

1. **Grundgerüst & Erste Plugins (Abgeschlossen):**
    - [x] Core-System mit Plugin-Manager und Dashboard-UI (PySide6).
    - [x] Plugin-Architektur mit `BasePlugin` Interface definiert.
    - [x] Erste UI-Entwürfe für `AudioTools` und `FileManager` erstellt.

2. **Funktionalität der Basis-Plugins (Abgeschlossen):**
    - [x] **AudioTools:** MVP abgeschlossen (Aufnahme & EQ-Engine mit DSP).
    - [x] **FileManager:** Duplikat-Scanner und Backup-Tool implementiert.

3. **Medienbibliothek (In Arbeit):**
    - [x] Implementierung der `MediaLibrary` als Kern-Feature (MVP).
    - [x] Metadaten-Handling und erweiterte UI-Features implementiert.
    - [x] Integrierte Vorschau (Audio/Video) und Playlist-Verwaltung ergänzt.
    - [ ] **(Als Nächstes)** Automatisierungs-Features und intelligente Integrationen.

4. **System-Werkzeuge & Konverter (In Arbeit):**
    - [x] Implementierung des `SystemTools` Plugins mit Dateikonverter (MVP).
    - [ ] **(Als Nächstes)** Disk Integrity Monitor und erweiterte Features.

5. **(Neu) Advanced Integrations & Automation (Geplant):**
    - [ ] Plugin-übergreifende Aktionen und Workflows.
    - [ ] Scripting-Schnittstelle für Power-User.

6. **Polishing & Release-Vorbereitung (Geplant):**
    - [ ] Umfassende Tests, Dokumentation und Fehlerbehebung.
    - [ ] Erstellen von Installationspaketen (z.B. mit PyInstaller).

---

## 3. Plugin: AudioTools

**Status:** **MVP Abgeschlossen, Erweiterungen geplant**

### Arbeitsaufschlüsselung (AudioTools)

- **Core Services & Utilities**
  - [x] `AudioDeviceService` zur Geräteerkennung hinzugefügt.
  - [x] Loopback/Desktop-Audio-Erfassung über Windows-WASAPI integriert (inkl. Fallback-Handling).
  - [ ] **(Als Nächstes)** Windows-Backend via `pycaw` (WASAPI) implementieren.
  - [ ] **(Als Nächstes)** Linux-Backend via `pulsectl` (PulseAudio) implementieren.
  - [ ] Fallback für generische Systemgeräte bereitstellen.
  - [ ] **(Neu)** Hot-Plug-Unterstützung: Auf Änderungen der Audiogeräte lauschen und die UI automatisch aktualisieren.
  - [ ] **(Neu)** Voreinstellungen pro Gerät: Erlaube das Speichern von EQ-Presets pro Ausgabegerät.

- **Equalizer Engine**
  - [x] Preset-Verwaltung (Speichern, Laden, Löschen) implementiert.
  - [x] Slider-Werte werden in Config gespeichert.
  - [x] DSP-Pipeline für Echtzeit-Equalizing integriert.
  - [ ] **(Neu)** Echtzeit-Visualisierung: Einen Spektrum-Analysator neben den EQ-Bändern anzeigen, der das Audiosignal visualisiert.
  - [ ] **(Neu)** Zusätzliche DSP-Effekte: Einen "Noise Gate" und "Kompressor" für Aufnahmequellen hinzufügen.

- **Recording Pipeline**
  - [x] Aufnahme-Worker mit `sounddevice` und Fallback implementiert.
  - [x] Konfigurierbare Qualität (Sample Rate, Bit-Tiefe) wird unterstützt.
  - [x] Metadaten-Dialog (`mutagen`) nach der Aufnahme integriert.
  - [x] Aufnahmeverlauf mit Metadaten in der UI sichtbar.
  - [x] Dateinamensschema & Verlaufspflege sorgen für eindeutige, aktuelle Einträge (inkl. Capture-Modus-Metadaten).
  - [x] Desktop-Audio-Quelle in UI & Persistenz aufgenommen (Geräteeinstellungen pro Modus).
  - [ ] **(Neu)** Aufnahme-Timer: Geplante Aufnahmen zu einer bestimmten Zeit starten/stoppen.

---

## 4. Plugin: FileManager

**Status:** **MVP Abgeschlossen, Erweiterungen geplant**

### Arbeitsaufschlüsselung (FileManager)

- **Feature: Duplikat-Scanner**
  - [x] UI, Backend, Threading, Anzeige und Löschfunktion implementiert.
  - [x] „Im Ordner anzeigen“-Button.
  - [ ] **(Neu)** Alternative Scan-Methoden: Zusätzliche Optionen zum Finden von Duplikaten anbieten (z.B. nur Dateiname, Metadaten-Ähnlichkeit für Audiofiles).
  - [ ] **(Neu)** Intelligente Auswahl: Buttons zum automatischen Auswählen von Duplikaten (z.B. "alle bis auf die Neueste auswählen", "alle in einem bestimmten Ordner auswählen").

- **Feature: Backup-Tool**
  - [x] UI, Backend, Fortschrittsanzeige und `send2trash` implementiert.
  - [ ] **(Neu)** Backup-Profile: Speichern und Laden von häufig genutzten Backup-Jobs (Quelle, Ziel, Einstellungen).
  - [ ] **(Neu)** "Dry Run"-Modus: Simulation eines Backups, die anzeigt, welche Dateien kopiert, überschrieben oder gelöscht *würden*.
  - [ ] **(Neu)** Zeitgesteuerte Backups: Integration eines Schedulers, um Backups täglich/wöchentlich auszuführen.

---

## 5. Plugin: MediaLibrary

**Status:** **Iteration 5 abgeschlossen – Iteration 6 in Arbeit**

### Arbeitsaufschlüsselung (MediaLibrary)

- **Core & UI**
  - [x] SQLite-Backend, Ordner-Verwaltung, Echtzeit-`watchdog` implementiert.
  - [x] Tabellen- und Kachel-Ansicht mit Cover-Cache und Hover-Effekten.
  - [x] Master/Detail-Split-View mit dynamischen Tabs und Metadaten-Anzeige.
  - [x] Filterleiste, Sortierung und Quick-Actions im Kontextmenü.
  - [x] Metadaten-Engine mit Editor und Reader/Writer (`mutagen`/`pymediainfo`).
  - [x] Persistente Sitzungen: Dashboard merkt sich Fenster & aktives Plugin, MediaLibrary speichert Filter, Tabs und Auswahl.
  - [x] Galerie rendert große Bibliotheken per Lazy-Loading & Icon-Virtualisierung ohne Speicher-Spikes.

- **Iteration 5 Ergebnisse**
  - [x] Inline-Bearbeitung für Bewertung & Tags direkt aus der Detailansicht.
  - [x] Speichern/Laden benutzerdefinierter Filter-Presets.
  - [x] Stapelaktionen für Mehrfachauswahl (Metadaten-Dialog im Batch, etc.).
  - [x] Externer Player-Button in Detail & Kontextmenü (pro Dateityp konfigurierbar).
  - [x] Zusätzliche Tests & Persistenz-Coverage (UI-State, Attribute-Handling).
  - [x] Thread-sicheres SQLite-Handling für Scanner und Watchdog eingeführt.

- **Iteration 6 Fortschritt**
  - [x] Integrierter Audio/Video-Player in der Detailansicht (QtMultimedia, optionaler Fallback).
  - [x] Playlist-Datenbank (Schema, CRUD) und Playlist-Tab mit Hinzufügen/Entfernen.

- **Iteration 6 Fokus (Entwurf)**
  - [ ] Smart Playlists & regelbasierte Vorschläge vorbereiten.
  - [ ] Statistik-Dashboard für Bibliothekskennzahlen prototypen.
  - [ ] Online-Scraper (TheMovieDB/MusicBrainz) evaluieren und anbinden.

- **Zukünftige Erweiterungen (Iteration 6 und darüber hinaus)**
  - [ ] **(Neu)** **Smart Playlists:** Erstellen von dynamischen Wiedergabelisten basierend auf Filterkriterien (z.B. "Alle Rock-Songs > 4 Sterne aus den 90ern", "Zuletzt hinzugefügte Filme").
  - [ ] **(Neu)** **Statistik-Dashboard:** Eine visuelle Übersicht der Bibliothek (Anzahl Dateien, Gesamtgröße, Verteilung nach Genre/Jahr, etc.).
  - [ ] **Scraper:** Einen Online-Scraper implementieren, der Metadaten (inkl. Cover) von TheMovieDB, MusicBrainz etc. abruft.
  - [ ] **Calibre (Recherche):** Analyse der `metadata.db` von Calibre, um eine schreibgeschützte Ansicht der E-Book-Bibliothek zu ermöglichen.

---

## 6. Plugin: SystemTools

**Status:** **MVP Abgeschlossen, Erweiterungen geplant**

### Arbeitsaufschlüsselung (SystemTools)

- **Feature: Universal File Converter**
  - [x] UI, Backend, Formatunterstützung und Threading implementiert.
  - [x] Tool-Erkennung für ImageMagick/FFmpeg verbessert (inkl. Pfadauflösung & Nutzerhinweisen).
  - [ ] **(Neu)** Stapelverarbeitung: Erlaube das Hinzufügen mehrerer Dateien und konvertiere sie nacheinander in einer Warteschlange.
  - [ ] **(Neu)** Preset-System: Speichern von häufig genutzten Konvertierungseinstellungen (z.B. "MP4 zu GIF", "WAV zu MP3 192kbit").

- **Feature: Image Tools & Compression**
  - [ ] **(Als Nächstes)** **JXL Image Tools:** Recherche und Einbindung einer `libjxl`-Python-Bibliothek für Konvertierung und Anzeige.
  - [ ] **(Neu)** **Bild-Komprimierer:** Eine dedizierte UI erstellen, um Bilder zu komprimieren, mit visuellem Vorher/Nachher-Vergleich und Qualitäts-Schieberegler.

- **Feature: Disk Integrity Monitor**
  - [ ] **(Als Nächstes)** **UI:** Zeigt eine Liste der Laufwerke mit S.M.A.R.T.-Status, Temperatur und Modell an.
  - [ ] **(Als Nächstes)** **Windows Backend:** Verwendet `wmic` oder PowerShell.
  - [ ] **(Als Nächstes)** **Linux Backend:** Verwendet `smartctl`.
  - [ ] **(Neu)** Benachrichtigungen: Sende eine Systembenachrichtigung, wenn sich der Status eines Laufwerks auf "Warning" oder "Error" ändert.

- **(Neu) Feature: Temporäre Dateien-Reiniger**
  - [ ] **UI:** Zeigt eine Liste von zu löschenden temporären Dateien gruppiert nach Kategorie (System-Cache, Browser-Cache, etc.) an.
  - [ ] **Backend:** Implementiert Logik zum Finden von temporären Ordnern auf Windows (`%TEMP%`) und Linux (`/tmp`, `~/.cache`).
  - [ ] **Aktion:** Erlaubt dem Benutzer, ausgewählte Kategorien sicher zu löschen.

- **Feature: Fan Control (Experimentell & Hohes Risiko)**
  - [ ] **Warnung:** Dieses Feature wird als "experimentell" markiert.
  - [ ] **Recherche:** Evaluierung von Bibliotheken. **Wird weiterhin zurückgestellt.**
  - [ ] **UI:** Graph-basierte Kurve (Temperatur vs. Lüfterdrehzahl).
