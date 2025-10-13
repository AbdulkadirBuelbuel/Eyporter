# FlexLM Exporter Setup Script
# Installiert alle Abhängigkeiten und bereitet die Umgebung vor

Write-Host "FlexLM Exporter Setup" -ForegroundColor Green
Write-Host "====================" -ForegroundColor Green
Write-Host ""

# Wechsle ins Skript-Verzeichnis  
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Prüfe Python Installation
Write-Host "Prüfe Python Installation..." -ForegroundColor Cyan
try {
    $PythonVersion = python --version 2>&1
    Write-Host "✓ $PythonVersion gefunden" -ForegroundColor Green
} catch {
    Write-Host "✗ Python nicht gefunden!" -ForegroundColor Red
    Write-Host "Bitte installieren Sie Python 3.7 oder höher." -ForegroundColor Yellow
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Erstelle Virtual Environment falls nicht vorhanden
if (-not (Test-Path ".venv")) {
    Write-Host "Erstelle Virtual Environment..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Fehler beim Erstellen des Virtual Environment!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Virtual Environment erstellt" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual Environment bereits vorhanden" -ForegroundColor Green
}

# Aktiviere Virtual Environment und installiere Packages
Write-Host "Installiere Python Packages..." -ForegroundColor Cyan
$PythonExe = "$ScriptDir\.venv\Scripts\python.exe"
$PipExe = "$ScriptDir\.venv\Scripts\pip.exe"

& $PipExe install --upgrade pip
& $PipExe install prometheus_client requests psutil

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Packages erfolgreich installiert" -ForegroundColor Green
} else {
    Write-Host "✗ Fehler bei der Package-Installation!" -ForegroundColor Red
    exit 1
}

# Prüfe lmutil (optional)
Write-Host ""
Write-Host "Prüfe FlexLM Tools..." -ForegroundColor Cyan
try {
    $LmutilVersion = lmutil --version 2>&1
    Write-Host "✓ lmutil gefunden" -ForegroundColor Green
} catch {
    Write-Host "⚠ lmutil nicht im PATH gefunden" -ForegroundColor Yellow
    Write-Host "  Das ist für den Demo-Modus okay." -ForegroundColor Yellow
    Write-Host "  Für echte License Server müssen FlexLM Tools installiert sein." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup abgeschlossen!" -ForegroundColor Green
Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Cyan
Write-Host "  Demo starten:        .\start_exporter.ps1 -Demo" -ForegroundColor White
Write-Host "  Echter Server:       .\start_exporter.ps1 -LicenseServer 192.168.1.100" -ForegroundColor White
Write-Host "  Hilfe anzeigen:      .\start_exporter.ps1 -?" -ForegroundColor White
