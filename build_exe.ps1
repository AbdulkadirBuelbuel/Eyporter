# PowerShell Script zum Erstellen der EXE
# Führe dieses Script aus um die EXE zu bauen

Write-Host "=== FlexLM Exporter EXE Builder ===" -ForegroundColor Green

# Prüfe ob PyInstaller installiert ist
try {
    pyinstaller --version | Out-Null
    Write-Host "✓ PyInstaller gefunden" -ForegroundColor Green
} catch {
    Write-Host "✗ PyInstaller nicht gefunden. Installiere..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Prüfe benötigte Dateien
$requiredFiles = @(
    "flexlm_exporter.py",
    "username_location_mapper.py", 
    "mapping.json",
    "servers.yml",
    "requirements.txt"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✓ $file gefunden" -ForegroundColor Green
    } else {
        Write-Host "✗ $file fehlt!" -ForegroundColor Red
        exit 1
    }
}

# Prüfe lmutil.exe
$lmutilPath = "C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe"
if (Test-Path $lmutilPath) {
    Write-Host "✓ lmutil.exe gefunden" -ForegroundColor Green
} else {
    Write-Host "✗ lmutil.exe nicht gefunden bei: $lmutilPath" -ForegroundColor Red
    Write-Host "Bitte Pfad in build_exe.spec anpassen!" -ForegroundColor Yellow
}

# Backup alte dist falls vorhanden
if (Test-Path "dist") {
    Write-Host "Backup alte dist zu dist_backup..." -ForegroundColor Yellow
    if (Test-Path "dist_backup") {
        Remove-Item -Recurse -Force "dist_backup"
    }
    Rename-Item "dist" "dist_backup"
}

# EXE erstellen
Write-Host "Erstelle EXE..." -ForegroundColor Yellow
pyinstaller --clean build_exe.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ EXE erfolgreich erstellt!" -ForegroundColor Green
    Write-Host "EXE befindet sich in: dist\FlexLM_Exporter.exe" -ForegroundColor Cyan
    
    # Teste die EXE
    Write-Host "Teste EXE..." -ForegroundColor Yellow
    .\dist\FlexLM_Exporter.exe --help
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ EXE Test erfolgreich!" -ForegroundColor Green
        Write-Host ""
        Write-Host "=== Verwendung ===" -ForegroundColor Cyan
        Write-Host "Einzelserver:"
        Write-Host ".\dist\FlexLM_Exporter.exe --license-server HOST --license-port 25734 --exporter-port 9090"
        Write-Host ""
        Write-Host "Multi-Server (mit servers.yml):"
        Write-Host ".\dist\FlexLM_Exporter.exe --servers-yaml servers.yml --exporter-port 9090"
        Write-Host ""
        Write-Host "Mit Debugging:"
        Write-Host ".\dist\FlexLM_Exporter.exe --servers-yaml servers.yml --verbose"
    } else {
        Write-Host "✗ EXE Test fehlgeschlagen" -ForegroundColor Red
    }
} else {
    Write-Host "✗ EXE Erstellung fehlgeschlagen" -ForegroundColor Red
    exit 1
}
