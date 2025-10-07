#!/usr/bin/env python
# enable_full_version.py - Aktiviert die vollständige Version der Anwendung

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main():
    """Aktiviert die vollständige Version für alle Plugins, insbesondere für Media Library."""
    print("Aktiviere vollständige Version der Anwendung...")

    # Umgebungsvariablen setzen
    os.environ["MMST_MEDIA_LIBRARY_ENHANCED"] = "1"
    os.environ["MMST_MEDIA_LIBRARY_ULTRA"] = "1"
    
    # Daten-Verzeichnis finden
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    
    data_dir = base / "mmst"
    config_file = data_dir / "config.json"
    
    print(f"Konfigurationsdatei: {config_file}")
    
    # Konfiguration laden oder erstellen
    config_data = {}
    if config_file.exists():
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
            print("Bestehende Konfiguration geladen.")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")
            config_data = {}
    
    # Media Library Konfiguration aktualisieren
    media_lib_id = "mmst.media_library"
    if not isinstance(config_data.get(media_lib_id), dict):
        config_data[media_lib_id] = {}
    
    # Erweiterte Funktionen aktivieren
    config_data[media_lib_id]["enhanced_enabled"] = True
    config_data[media_lib_id]["ultra_enabled"] = True
    
    # Dashboard Konfiguration aktualisieren
    dashboard_id = "__dashboard__"
    if not isinstance(config_data.get(dashboard_id), dict):
        config_data[dashboard_id] = {}
    
    # Speichern der Konfiguration
    data_dir.mkdir(parents=True, exist_ok=True)
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, sort_keys=True)
    
    print("Vollständige Version aktiviert. Starten Sie die Anwendung neu mit 'python -m mmst.core.app'")


if __name__ == "__main__":
    main()