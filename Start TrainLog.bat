@echo off
cd /d "%~dp0"
title TrainLog - laat dit venster open
echo TrainLog wordt gestart. De app opent vanzelf in je browser.
echo Laat dit venster open zolang je de app gebruikt.
echo Stoppen: druk op Ctrl+C of sluit dit venster.
echo.
python app.py --open
if errorlevel 1 (
    echo.
    echo Starten is mislukt. Controleer de foutmelding hierboven.
    echo Controleer of Python is geinstalleerd en beschikbaar via het commando python.
    pause
)
