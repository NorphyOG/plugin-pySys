# Projektplan: Modulares Medien- & System-Toolkit (MMST)

## 1. Vision & Ziele

Das MMST soll eine plattformübergreifende (Windows & Linux) Python-Anwendung werden, die eine Vielzahl von Medien- und Systemaufgaben über eine einheitliche, plugin-basierte Architektur zugänglich macht. Der Fokus liegt auf Erweiterbarkeit, Benutzerfreundlichkeit und mächtigen Werkzeugen für Power-User.

**Kernprinzipien:**

- **Modularität:** Jede Kernfunktion ist ein eigenständiges Plugin.
- **Performance:** Langwierige Operationen (Scannen, Konvertieren) blockieren niemals die Benutzeroberfläche.
- **Plattformunabhängigkeit:** Wo immer möglich, wird plattformunabhängiger Code verwendet. Wo nicht, werden spezifische Backends mit sauberen Fallbacks implementiert.
- **Transparenz:** Der Nutzer hat stets Kontrolle und Einblick in die Prozesse.

---

## 2. Globale Projekt-Roadmap (Meilensteine)

1. **Grundgerüst & Erste Plugins (Abgeschlossen):**
    - [x] Core-System mit Plugin-Manager und Dashboard-UI (PySide6).
    - [x] Plugin-Architektur mit `BasePlugin` Interface definiert.
    - [x] Erste UI-Entwürfe für `AudioTools` und `FileManager` erstellt.

2. **Funktionalität der Basis-Plugins:**
    - [x] **AudioTools:** MVP abgeschlossen (Aufnahme & EQ-Engine mit DSP).
    - [x] **FileManager:** Duplikat-Scanner und Backup-Tool implementiert.

3. **Medienbibliothek (Großes Feature):**
    - [x] Implementierung der `MediaLibrary` als Kern-Feature (MVP).
    - [ ] Metadaten-Handling und Steam-ähnliche Ordnerverwaltung (erweiterte Features).

4. **System-Werkzeuge & Konverter:**
    - [x] Implementierung des `SystemTools` Plugins mit Dateikonverter (MVP).
    - [ ] Disk Integrity Monitor und erweiterte Features.

5. **Polishing & Release-Vorbereitung:**
    - [ ] Umfassende Tests, Dokumentation und Fehlerbehebung.
    - [ ] Erstellen von Installationspaketen (z.B. mit PyInstaller).

---

## 3. Plugin: AudioTools

*Dieses Plugin ist bereits in der Entwicklung. Der Plan spiegelt den von Ihnen bereitgestellten Fortschritt wider.*

**Ziele:** Systemweiter Equalizer, Preset-Verwaltung, hochwertige Audioaufnahme mit Metadaten.

**Status:** **MVP Abgeschlossen (Recording + EQ-DSP fertig)**

### Arbeitsaufschlüsselung

- **Core Services & Utilities**
  - [x] `AudioDeviceService` zur Geräteerkennung hinzugefügt.
  - [ ] **(Als Nächstes)** Windows-Backend via `pycaw` (WASAPI) implementieren.
  - [ ] **(Als Nächstes)** Linux-Backend via `pulsectl` (PulseAudio) implementieren.
  - [ ] Fallback für generische Systemgeräte bereitstellen.

- **Config & UI**
  - [x] Config-Schema für Presets und Qualitätseinstellungen definiert.
  - [x] UI-Grundgerüst für Equalizer und Recorder erstellt.
  - [x] Warnung bei fehlendem Audio-Backend implementiert.

- **Equalizer Engine**
  - [x] Preset-Verwaltung (Speichern, Laden, Löschen) implementiert.
  - [x] Slider-Werte werden in Config gespeichert.
  - [x] **DSP-Pipeline für Echtzeit-Equalizing integriert** (scipy.signal IIR-Filter, 10-Band parametrische EQ, Echtzeit-Callbacks via sounddevice).

- **Recording Pipeline**
  - [x] Aufnahme-Worker mit `sounddevice` und Fallback implementiert.
  - [x] Konfigurierbare Qualität (Sample Rate, Bit-Tiefe) wird unterstützt.
  - [x] Metadaten-Dialog (`mutagen`) nach der Aufnahme integriert.
  - [x] Aufnahmeverlauf mit Metadaten in der UI sichtbar.

---

## 4. Plugin: FileManager

**Ziele:** Finden und Löschen von doppelten Dateien, Erstellen von 1:1-Backups der Dateistruktur.

**Status:** **In Arbeit (Duplikate & Backup mit Fortschritt)**

### Arbeitsaufschlüsselung

- **Feature: Duplikat-Scanner**
  - [x] **UI:** Tabellenansicht zur Anzeige der Duplikate mit Checkboxen zum Löschen.
  - [x] **Backend:** Scanner implementiert; läuft im ThreadPool des Plugins mit Fortschritts-Callback.
    - [x] **Phase 1 (Größe):** Rekursives Scannen und Gruppieren von Dateien nach identischer Größe.
    - [x] **Phase 2 (Hash):** Hash (SHA256) wird für Kandidaten identischer Größe berechnet.
    - [x] **Threading:** Fortschrittsanzeige (aktuelle Datei, Zähler) an die UI angebunden.
  - [x] **Anzeige:** Ergebnisse gruppiert; Checkboxen je Datei, Gruppen nicht löschbar.
  - [x] **Aktion:** Löschfunktion inkl. Schutz „mindestens eine Datei pro Gruppe“ implementiert.
  - [x] **Komfort:** „Im Ordner anzeigen“-Button für die ausgewählte Datei.

- **Feature: Backup-Tool**
  - [x] **UI:** Felder für Quell- und Zielordner, Checkbox für "Spiegeln" vorhanden; Log-Panel integriert.
  - [x] **Backend:** Läuft im ThreadPool des Plugins; nutzt `shutil` für Kopieroperationen.
  - [x] **Fortschritt:** Fortschrittsbalken mit Gesamtanzahl (errechnet) und Zähler für Kopiert/Übersprungen; Log-Spiegelung in Echtzeit.
  - [x] **Plattform:** `pathlib` konsequent; optional `send2trash` für Papierkorb-Löschung.

---

## 5. Plugin: MediaLibrary

**Ziele:** Eine "Netflix-ähnliche" Ansicht für lokale Medien, Metadaten-Verwaltung, Integration externer Tools.

**Status:** **In Arbeit (MVP abgeschlossen)**

### Arbeitsaufschlüsselung

- **Core Library Service**
  - [x] Definieren einer Datenbank-Struktur (SQLite) zur Speicherung von Metadaten und Dateipfaden.
  - [x] "Steam-ähnliche" Verwaltung von Bibliotheksordnern (mehrere Quellen auf verschiedenen Laufwerken).
  - [ ] **(Nächste Phase)** Echtzeit-Ordnerüberwachung (`watchdog`-Bibliothek) zur automatischen Aktualisierung der Bibliothek.

- **UI / Frontend**
  - [x] **MVP:** Tabellen-Ansicht mit Quellenverwaltung, Scannen mit Fortschritt, Liste indizierter Dateien.
  - [ ] **(Erweitert)** Kachel-basierte Ansicht mit Covern und Titeln.
  - [ ] **(Erweitert)** Detailansicht, die alle Metadaten anzeigt.
  - [ ] **(Erweitert)** Mächtige Filter- und Sortierfunktionen (nach Genre, Bewertung, Datum etc.).

- **Metadaten-Engine**
  - [ ] **Editor:** Eine "Calibre-ähnliche" Bearbeitungsmaske für alle Metadatenfelder.
  - [ ] **Reader/Writer:** Integration von `mutagen` (Audio) und `pymediainfo` (Video/MKV), um Metadaten direkt aus den Dateien zu lesen und zu schreiben.
  - [ ] **Scraper (Optional):** Ein Online-Scraper, der versucht, Metadaten basierend auf dem Dateinamen zu finden (z.B. von TheMovieDB).

- **Integrationen**
  - [ ] **Externer Player:** Einstellungsdialog, in dem der Benutzer pro Dateityp eine externe Anwendung zum Öffnen festlegen kann (z.B. ".mkv -> VLC").
  - [ ] **Calibre (Recherche):** Analyse der `metadata.db` von Calibre, um eine schreibgeschützte Ansicht der E-Book-Bibliothek zu ermöglichen.

---

## 6. Plugin: SystemTools

**Ziele:** Eine Sammlung von Werkzeugen für Dateikonvertierung, Komprimierung und Systemdiagnose.

**Status:** **MVP Abgeschlossen (File Converter implementiert)**

### Arbeitsaufschlüsselung

- **Feature: Universal File Converter** ✅ **MVP Abgeschlossen**
  - [x] **UI:** Dateiauswahl, Zielformat-Dropdown, Konvertierungs-Log mit Fortschritt.
  - [x] **Backend:** Wrapper um Kommandozeilen-Tools implementiert.
    - [x] Prüft beim Start, ob `ffmpeg` und `ImageMagick` im System-PATH verfügbar sind.
    - [x] Zeigt Tool-Status mit Version in der UI an.
  - [x] **Formate:** Audio (MP3, WAV, FLAC, AAC, OGG), Video (MP4, MKV, AVI, WebM), Image (PNG, JPG, WebP, GIF, BMP).
  - [x] **Conversion Engine:** `FileConverter` mit Timeout-Handling und Progress-Callbacks.
  - [x] **Tests:** 21 Unit-Tests für Tool-Erkennung, Format-Inferenz und Konvertierungslogik.
  - [x] **Threading:** Asynchrone Konvertierung via ThreadPoolExecutor ohne UI-Blockierung.

- **Feature: JXL Image Tools**
  - [ ] **Integration:** Recherche und Einbindung einer `libjxl`-Python-Bibliothek.
  - [ ] **Funktionen:** Konvertierung von/zu JXL, Anzeige von JXL-Bildern (inkl. Animationen).

- **Feature: Disk Integrity Monitor**
  - [ ] **UI:** Zeigt eine Liste der Laufwerke mit ihrem S.M.A.R.T.-Status an.
  - [ ] **Windows Backend:** Verwendet `wmic diskdrive get status` oder PowerShell `Get-PhysicalDisk`.
  - [ ] **Linux Backend:** Verwendet `smartctl` aus `smartmontools`.

- **Feature: Fan Control (Experimentell & Hohes Risiko)**
  - [ ] **Warnung:** Dieses Feature wird als "experimentell" markiert und erfordert explizite Aktivierung und Administratorrechte.
  - [ ] **UI:** Graph-basierte Kurve (Temperatur vs. Lüfterdrehzahl).
  - [ ] **Recherche:** Evaluierung von Bibliotheken wie `py-smc` (macOS), `lm-sensors` (Linux) und potenziellen Windows-Lösungen. **Wird zunächst zurückgestellt.**
