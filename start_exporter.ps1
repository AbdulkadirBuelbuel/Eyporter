# FlexLM Exporter PowerShell Startskript

param(
    [string]$LicenseServer = "lic-solidworks-emea.patec.group",
    [int]$LicensePort = 25734,
    [int]$ExporterPort = 9090,
    [string]$LmutilPath = "lmutil",
    [switch]$Verbose,
    [switch]$Demo
)

Write-Host "FlexLM License Server Exporter" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green
Write-Host ""

# Wechsle ins Skript-Verzeichnis
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Prüfe Python-Umgebung
$PythonExe = "$ScriptDir\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "FEHLER: Virtual Environment nicht gefunden!" -ForegroundColor Red
    Write-Host "Bitte führen Sie zuerst setup.ps1 aus." -ForegroundColor Yellow
    exit 1
}

# Prüfe ob lmutil verfügbar ist (außer im Demo-Modus)
if (-not $Demo) {
    try {
        & $LmutilPath --version | Out-Null
    } catch {
        Write-Host "WARNUNG: lmutil nicht im PATH gefunden!" -ForegroundColor Yellow
        Write-Host "Sie können den Pfad mit -LmutilPath angeben." -ForegroundColor Yellow
        Write-Host "Oder verwenden Sie -Demo für Testzwecke." -ForegroundColor Yellow
        Write-Host ""
    }
}

# Baue Kommandozeile auf
$Args = @()

if ($Demo) {
    Write-Host "Starte im Demo-Modus mit simulierten Daten..." -ForegroundColor Cyan
    $Args += "flexlm_exporter.py"
} else {
    $Args += "flexlm_exporter.py"
    $Args += "--license-server", $LicenseServer
    $Args += "--license-port", $LicensePort.ToString()
    $Args += "--exporter-port", $ExporterPort.ToString()
    $Args += "--lmutil-path", $LmutilPath
    
    if ($Verbose) {
        $Args += "--verbose"
    }
    
    Write-Host "Konfiguration:" -ForegroundColor Cyan
    Write-Host "  License Server: $LicenseServer`:$LicensePort" -ForegroundColor White
    Write-Host "  Exporter Port:  $ExporterPort" -ForegroundColor White
    Write-Host "  lmutil Pfad:    $LmutilPath" -ForegroundColor White
}

Write-Host ""
Write-Host "Metriken verfügbar unter: http://localhost:$ExporterPort/metrics" -ForegroundColor Green
Write-Host "Drücken Sie Ctrl+C zum Beenden..." -ForegroundColor Yellow
Write-Host ""

# Starte den Exporter
try {
    & $PythonExe @Args
} catch {
    Write-Host "Fehler beim Starten des Exporters: $_" -ForegroundColor Red
    exit 1
}
