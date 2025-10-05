# Projektplan: Modulares Medien- & System-Toolkit (MMST)

**Version: 3.0**
**Letzte Ak- **Feature: Duplikat-Scanner**
  - [x] UI, Backend, Threading, Anzeige und Löschfunktion implementiert.
  - [x] „Im Ordner anzeigen"-Button.
  - [ ] **(Neu)** Alternative Scan-Methoden: Zusätzliche Optionen zum Finden von Duplikaten anbieten (z.B. nur Dateiname, Metadaten-Ähnlichkeit für Audiofiles).
  - [x] **(Abgeschlossen)** Intelligente Auswahl: 4 Smart-Selection-Buttons implementiert (Älteste behalten, Kleinste behalten, Nach Ordner filtern, Alle abwählen).sierung: 2025-10-03**

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
    - [x] Kino-Modus mit Vollbild-Player und Autoplay hinzugefügt.
    - [ ] **(Als Nächstes)** Automatisierungs-Features und intelligente Integrationen.

4. **System-Werkzeuge & Konverter (In Arbeit):**
    - [x] Implementierung des `SystemTools` Plugins mit Dateikonverter (MVP).
    - [x] **(Abgeschlossen)** Disk Integrity Monitor implementiert (Windows & Linux).
    - [ ] **(Als Nächstes)** Erweiterte Features.

5. **(Neu) Advanced Integrations & Automation (In Arbeit):**
    - [x] **(Abgeschlossen)** Plugin-übergreifende Aktionen: EventBus-System für Pub/Sub-Kommunikation zwischen Plugins implementiert.
    - [ ] Erweiterte Workflows und Automation-Chains.
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
  - [x] **(Abgeschlossen)** Echtzeit-Visualisierung: Spektrum-Analysator mit FFT-basierter 10-Band-Visualisierung implementiert (automatisches Start/Stop mit EQ-Engine, color-coded bars).
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
  - [x] **(Abgeschlossen)** Backup-Profile: Speichern und Laden von häufig genutzten Backup-Jobs (Quelle, Ziel, Mirror-Modus) via JSON-Persistierung.
  - [x] **(Abgeschlossen)** "Dry Run"-Modus: Vollständige Simulation mit [DRY RUN] Präfix in Logs, zeigt alle geplanten Operationen ohne Ausführung.
  - [x] **(Neu)** Zeitgesteuerte Backups: Scheduler mit Intervallen (stündlich, täglich, wöchentlich, monatlich), UI-Konfiguration pro Profil, Persistenz (`backup_schedules.json`).
  - [x] Concurrency Guard: Verhindert parallele manuelle & geplante Backups (Übersprungene Läufe werden geloggt & per Notification gemeldet).
  - [ ] Erweiterung: Ausführungszeit (z.B. täglich 02:00) statt gleitendem Intervall ab Erstellung.
  - [ ] Erweiterung: Mehrere Zeitpläne pro Profil + Übersichtsliste.
  - [ ] Erweiterung: Throttle / Retry bei Fehlern & E-Mail/Hook-Integration.

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
  - [x] Kino-Modus (Fullscreen) mit dynamischem Video-Wechsel & Autoplay.
  - [x] Tag-Übersichtstab mit Filter, Detailtabelle und Schnellnavigation.
  - [x] Verbesserte Tag-Interaktionen: Bibliotheksfilter per Klick, Umbenennen/Entfernen und dynamische Hinweise.
  - [x] Manuelles Playlist-Reordering (Auf/Ab) und Tag → Playlist-Workflows (Playlist aus Tag, Tag zu Playlist).
  - [x] Linux-optimierte "Im Ordner anzeigen"-Funktion via `xdg-open` Fallback.

- **Iteration 6 Fokus (Entwurf)**
  - [x] Smart Playlists – Phase 2 gestartet (Persistenz, CRUD-Basis, erweiterte Operatoren, Caching v1) – Erweiterter Editor & komplexe Regeln folgen.
  - [x] **(Abgeschlossen)** Statistik-Dashboard für Bibliothekskennzahlen: Visuelle Karten mit Datei-Counts/Größen/Bewertungen, Bar-Charts für Genre/Artist-Verteilung, temporale Stats (letzte 7 Tage).
  - [ ] Verbesserte Benutzeroberfläche für die Playlist-Verwaltung.
  - [ ] Automatisierungs-Features (z.B. Tags aus Dateipfaden generieren).
  - [ ] Online-Scraper (TheMovieDB/MusicBrainz) evaluieren und anbinden.

- **Zukünftige Erweiterungen (Iteration 6 und darüber hinaus)**
  - [x] **(Neu)** **Smart Playlists (Phase 1):** Regelbasiertes Filtering (Rating, Kind, Dauer, Basis-Metadaten), Default-Beispiele, UI-Tab, Live-Auswertung.
  - [x] **(Neu)** **Smart Playlists (Phase 2 – laufend):**
    - Persistenz (JSON Save/Load, Defaults beim ersten Start)
    - CRUD UI (Neu, Umbenennen, Löschen, Re-Evaluate)
    - Erweiterte Operatoren (>=, <=, between, contains/not_contains, startswith/endswith, regex, has_tag)
    - Einfaches Ergebnis-Caching (Signatur-basiert, Invalidierung bei Änderungen)
    - Unit Tests (Evaluation, Save/Load, Operatoren)
    - NEU: Regel-Editor Dialog (Name, Beschreibung, Match-Modus, Limit, Sortierung, Tabellenbasierte Rules)
    - NEU: Operator within_days (mtime innerhalb X Tage)
  - [ ] **(Geplant)** Smart Playlists (Phase 3):
  - [x] Grundstein: Erweiterter Editor (Tree-Struktur) – Prototyp erstellt (Nested Gruppen + Preview Count)
  - [x] Kontextmenü & Doppelklick: Regel bearbeiten / Gruppe toggeln
  - [x] NOT (Negate) Umschalten pro Gruppe + AND/OR Toggle ohne Komplett-Rebuild
  - [x] Inline-Regelbearbeitung (Dialog Sequenz Feld/Operator/Wert, inkl. between & within_days)
  - [x] Auto-Preview nach Struktur-/Regel-Änderungen
    - [ ] In-place Bearbeitung von Feld / Operator / Wert in Baum
    - [ ] Drag & Drop Reordering / Gruppierung
    - [ ] Relative Zeitregeln ("zuletzt X Tage", "Dieses Jahr")
    - [ ] Erweiterte Negation (NOT auf Einzelregel-Ebene toggelbar)
    - [ ] Performance: Delta-Reevaluation & inkrementeller Cache
    - [ ] UI: Live Inline-Vorschau (Top-N Treffer) während Bearbeitung
  - [ ] **(Neu)** **Statistik-Dashboard:** Eine visuelle Übersicht der Bibliothek (Anzahl Dateien, Gesamtgröße, Verteilung nach Genre/Jahr, etc.).
  - [ ] **Scraper:** Einen Online-Scraper implementieren, der Metadaten (inkl. Cover) von TheMovieDB, MusicBrainz etc. abruft.
  - [ ] **Calibre (Recherche):** Analyse der `metadata.db` von Calibre, um eine schreibgeschützte Ansicht der E-Book-Bibliothek zu ermöglichen.

### Performance & Skalierung (Neu)

Aktuell umgesetzt für sehr große Bibliotheken ( > 10.000 Einträge ):

| Bereich | Ansatz | Effekt |
|---------|-------|--------|
| Tabellen-Befüllung | Chunked Loading (erste 1000 synchron, danach 1500er Batches via QTimer) | UI friert nicht mehr beim Laden großer Datasets |
| Galerie-Befüllung | Gleiches Chunking + verzögerte Icon-Anreicherung | Schnelles initiales Scrolling ohne Blockade |
| Cover-Laden | Asynchron via QThreadPool + Platzhalter-Icons | Kein UI-Stutter durch disk/network IO |
| Selektions-Sync | Signal-Blockierung & Redundanzprüfung | Verhindert Deadlocks / blockierte Auswahl |

Geplante Optimierungen:

- Scroll-gesteuerte Nachladung (Demand-Driven statt Timer-Sequenz)
- Adaptives Batch-Sizing basierend auf Renderdauer
- Optionaler Preload-Index für häufig benutzte Sortierkriterien
- Konfigurierbarer Schwellwert & Dev-Schalter für Benchmarking

Risiken & Mitigation:

- Race Conditions bei Cover-Updates → Pfadbasierter Matching-Check
- Hohe Thread-Auslastung bei massiven Cover-Anfragen → Nutzung von globalInstance() des ThreadPools (Qt limitiert Worker)
- Test-Stabilität → Feature deaktiviert für kleine Datenmengen (unterhalb Threshold unverändert synchron)

---

## 6. Plugin: SystemTools

**Status:** **MVP Abgeschlossen, Erweiterungen geplant**

### Arbeitsaufschlüsselung (SystemTools)

- **Feature: Universal File Converter**
  - [x] UI, Backend, Formatunterstützung und Threading implementiert.
  - [x] Tool-Erkennung für ImageMagick/FFmpeg verbessert (inkl. Pfadauflösung & Nutzerhinweisen).
  - [x] **(Abgeschlossen)** Stapelverarbeitung: Batch-Warteschlange Tab mit Multi-File-Queue, sequentieller Verarbeitung, Fortschrittsanzeige pro Datei und Gesamtübersicht.
  - [x] **(Abgeschlossen)** Preset-System: Speichern/Laden von Format-Presets mit JSON-Persistierung, automatisches Ziel-Extension-Update beim Laden.

- **Feature: Image Tools & Compression**
  - [ ] **(Als Nächstes)** **JXL Image Tools:** Recherche und Einbindung einer `libjxl`-Python-Bibliothek für Konvertierung und Anzeige.
  - [ ] **(Neu)** **Bild-Komprimierer:** Eine dedizierte UI erstellen, um Bilder zu komprimieren, mit visuellem Vorher/Nachher-Vergleich und Qualitäts-Schieberegler.

- **(Neu) Feature: Disk Integrity Monitor**
- [x] Backend für Windows via WMI (`MSStorageDriver_FailurePredictData`) implementiert.
- [x] Backend für Linux via `smartctl` implementiert.
- [x] Plattform-agnostische Abstraktion (`DiskMonitorBase`) und Factory erstellt.
- [x] UI-Widget zur Anzeige des Disk-Status integriert.
- [x] Hintergrund-Überwachung mit Benachrichtigung bei kritischen Status-Änderungen.

- **(Neu) Feature: Temporäre Dateien-Reiniger** (In Arbeit)
  - [x] Backend `temp_cleaner.py` mit Kategorien & Scan / Delete API.
  - [x] Kategorien: System Temp, Browser Caches (Windows) / User Cache (Linux), erweiterbar.
  - [x] UI Tab (🧹 Temp Cleaner) mit Kategorie-Checkboxen, Scan & Delete (Dry Run / Echt) Buttons, Log & Summary.
  - [x] Persistenz: Ausgewählte Kategorien + letzte Scan-Zusammenfassung werden gespeichert.
  - [ ] Erweiterung: Altersfilter UI (aktuell nur Parameter `min_age_seconds` im Code nutzbar).
  - [ ] Erweiterung: Größenfilter & Ausschlussmuster.
  - [ ] Erweiterung: Fortschritts-Anzeige während tiefen Scans.
  - [ ] Erweiterung: Konfigurierbare zusätzliche Custom-Kategorien via Config-Dialog.

- **(Neu) Feature: Temporäre Dateien-Reiniger**
  - [ ] **UI:** Zeigt eine Liste von zu löschenden temporären Dateien gruppiert nach Kategorie (System-Cache, Browser-Cache, etc.) an.
  - [ ] **Backend:** Implementiert Logik zum Finden von temporären Ordnern auf Windows (`%TEMP%`) und Linux (`/tmp`, `~/.cache`).
  - [ ] **Aktion:** Erlaubt dem Benutzer, ausgewählte Kategorien sicher zu löschen.

- **Feature: Fan Control (Experimentell & Hohes Risiko)**
  - [ ] **Warnung:** Dieses Feature wird als "experimentell" markiert.
  - [ ] **Recherche:** Evaluierung von Bibliotheken. **Wird weiterhin zurückgestellt.**
  - [ ] **UI:** Graph-basierte Kurve (Temperatur vs. Lüfterdrehzahl).

  ---

  ## 7. Dokumentationsjournal

  - ✅ 2025-10-04: `.github/copilot-instructions.md` aktualisiert; bündelt Architektur- und Workflow-Hinweise für KI-Agenten.
  - ✅ 2025-10-04: **Next Big Update abgeschlossen** – 7 Major Features implementiert:
    - MediaLibrary: Statistik-Dashboard mit visuellen Analytics
    - FileManager: Intelligente Duplikat-Auswahl + Backup-Profile & Dry-Run
    - SystemTools: Batch-Warteschlange + Conversion-Presets
    - AudioTools: Echtzeit-Spektrum-Analyzer (FFT-basiert)
    - Core: EventBus für Plugin-übergreifende Kommunikation
  - 🔜 Nächster Meilenstein: Unit Tests für neue Features und Performance-Optimierungen.

---

## 8. Offene / Fehlende Funktionen (Aktualisierung)

Diese Übersicht fasst fehlende oder teils entfernte/geplante Funktionen zusammen, damit ihr Status im Plan wieder klar als "nicht erledigt" markiert ist. (Nur Ergänzung – vorhandene Abschnitte oben bleiben unverändert.)

### MediaLibrary
- [ ] Erweiterte Playlist-Verwaltung (verbesserte UI – Drag & Drop, Multi-Select Operationen)
- [ ] Automatisierungs-Features (Tag-Generierung aus Pfaden / Batch-Regeln)
- [ ] Online-Metadaten-Enrichment (Provider-Integration + UI-Button / Kandidatenauswahl)
- [ ] Smart Playlists Phase 3 (Drag & Drop Reordering, relative Zeitregeln, Inline-Bearbeitung von Feld/Operator/Wert, erweiterte NOT-Regeln auf Regel-Ebene)
- [ ] Performance: Delta-Reevaluation & inkrementeller Smart-Playlist-Cache
- [ ] UI: Live Inline-Vorschau (Top-N Treffer) während Smart-Playlist-Regelbearbeitung

### AudioTools
- [ ] Windows Backend via `pycaw` (vollständige Implementierung)
- [ ] Linux Backend via `pulsectl`
- [ ] Hot-Plug-Erkennung der Audiogeräte
- [ ] Gerätespezifische EQ-Presets (Persistenz je Gerät)
- [ ] Aufnahme-Timer (geplante Start/Stop Zeiten)
- [ ] Zusätzliche DSP-Effekte: Noise Gate & Kompressor

### FileManager
- [ ] Duplikat-Scanner: Alternative Scan-Methoden (Nur Dateiname / Metadaten-Ähnlichkeit)
- [ ] Duplikat-Scanner: Erweiterte intelligente Auswahl (Mehr Auto-Select Strategien)
- [ ] Backup: Ausführungszeit (z.B. täglich 02:00) statt Intervall ab Erstellung
- [ ] Backup: Mehrere Zeitpläne pro Profil + Übersichtsliste
- [ ] Backup: Throttle/Retry & E-Mail/Webhook Integration

### SystemTools
- [ ] Temp Cleaner: Altersfilter UI (statt nur Parameter)
- [ ] Temp Cleaner: Größenfilter & Ausschlussmuster
- [ ] Temp Cleaner: Fortschrittsanzeige für tiefe Scans
- [ ] Temp Cleaner: Konfigurierbare Custom-Kategorien (UI + Persistenz)
- [ ] Image Tools: JXL-Unterstützung (Recherche + Konverter)
- [ ] Bild-Komprimierer UI (Vorher/Nachher, Qualitäts-Slider)
- [ ] Fan Control (Recherche & sichere Abstraktion) – weiterhin zurückgestellt

### Cross-Cutting / Core
- [ ] Erweiterte Workflows & Automation Chains (Plugin-übergreifend)
- [ ] Scripting-Schnittstelle für Power-User
- [ ] Online-Scraper (TheMovieDB / MusicBrainz) – Evaluierung + Proof-of-Concept
- [ ] Calibre-Integration (schreibgeschützte E‑Book Ansicht) – Analyse `metadata.db`

---

Hinweis: Diese Sektion dient als Delta-Liste. Wenn einzelne Punkte umgesetzt werden, sollten sie in die jeweiligen Plugin-Abschnitte nach oben verschoben und hier entfernt werden.
