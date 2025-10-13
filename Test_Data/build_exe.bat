@echo off
echo === FlexLM Exporter EXE Builder ===

REM Prüfe ob PyInstaller installiert ist
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Erstelle EXE
echo Building EXE...
pyinstaller --clean build_exe.spec

if errorlevel 0 (
    echo.
    echo SUCCESS: EXE created in dist\FlexLM_Exporter.exe
    echo.
    echo Usage examples:
    echo Single server: .\dist\FlexLM_Exporter.exe --license-server HOST --license-port 25734 --exporter-port 9090
    echo Multi-server:  .\dist\FlexLM_Exporter.exe --servers-yaml servers.yml --exporter-port 9090
    echo With debug:    .\dist\FlexLM_Exporter.exe --servers-yaml servers.yml --verbose
) else (
    echo ERROR: Build failed
    pause
)
