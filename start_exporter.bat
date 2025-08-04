@echo off
REM FlexLM Exporter Startskript für Windows

echo Starting FlexLM Exporter...
echo.

REM Aktiviere Virtual Environment falls vorhanden
if exist "venv\Scripts\activate.bat" (
    echo Aktiviere Virtual Environment...
    call venv\Scripts\activate.bat
)

REM Prüfe ob Python verfügbar ist
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python ist nicht verfügbar oder nicht im PATH!
    echo Bitte installieren Sie Python 3.7 oder höher.
    pause
    exit /b 1
)

REM Prüfe ob lmutil verfügbar ist
lmutil --version >nul 2>&1
if errorlevel 1 (
    echo WARNUNG: lmutil ist nicht im PATH verfügbar!
    echo Bitte stellen Sie sicher, dass FlexLM Tools installiert sind.
    echo Sie können den Pfad mit --lmutil-path angeben.
    echo.
)

REM Installiere Dependencies falls requirements.txt existiert
if exist "requirements.txt" (
    echo Installiere Python Dependencies...
    pip install -r requirements.txt
    echo.
)

REM Starte den Exporter
echo Starte FlexLM Exporter auf http://localhost:9090/metrics
echo Drücken Sie Ctrl+C zum Beenden...
echo.

python flexlm_exporter.py --verbose

pause
