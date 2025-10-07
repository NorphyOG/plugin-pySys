@echo off
echo Aktiviere die vollstaendige Version des MMST-Programms...
echo.

echo 1. Aktiviere Vollversion-Konfiguration...
python enable_full_version.py
echo.


echo 2. Starte das Programm...
python -m mmst.core.app