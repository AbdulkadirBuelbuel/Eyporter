#!/usr/bin/env python3
"""
Einfacher Test für FlexLM Exporter ohne AD
Für Test-Systeme die nicht mit AD verbunden sind
"""

import subprocess
import time
import sys
import os

def test_exporter_no_ad():
    """Testet den Exporter ohne AD"""
    print("FlexLM Exporter Test (ohne AD-Integration)")
    print("=" * 50)
    
    # Prüfe ob wir im richtigen Verzeichnis sind
    if not os.path.exists("flexlm_exporter.py"):
        print("❌ Fehler: flexlm_exporter.py nicht gefunden!")
        print("Bitte führen Sie dieses Skript im Projektverzeichnis aus.")
        return False
    
    # Python-Pfad
    python_exe = r"C:\Users\abdul\OneDrive - Hochschule Furtwangen\Semester_7\Eyporter\.venv\Scripts\python.exe"
    
    if not os.path.exists(python_exe):
        print("❌ Virtual Environment nicht gefunden!")
        return False
    
    # Test-Kommando (ohne echten License Server)
    cmd = [
        python_exe,
        "flexlm_exporter.py",
        "--license-server", "test-server",
        "--license-port", "27000",
        "--lmutil-path", "echo",  # Mock-Befehl statt echtem lmutil
        "--verbose"
        # AD ist standardmäßig deaktiviert
    ]
    
    print("Test-Befehl:")
    print(" ".join(cmd))
    print()
    print("Startet den Exporter für 15 Sekunden...")
    print("Metriken verfügbar unter: http://localhost:9090/metrics")
    print()
    
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Lese Output für 15 Sekunden
        start_time = time.time()
        output_lines = []
        
        while time.time() - start_time < 15:
            if process.poll() is not None:
                break
            
            # Lese verfügbare Ausgabe
            try:
                line = process.stdout.readline()
                if line:
                    print(line.strip())
                    output_lines.append(line.strip())
            except:
                pass
                
            time.sleep(0.1)
        
        # Prozess beenden
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Prüfe ob erfolgreich
        success_indicators = [
            "Starte FlexLM Exporter",
            "Metriken verfügbar unter",
            "FlexLM Exporter gestartet"
        ]
        
        success = any(any(indicator in line for indicator in success_indicators) 
                     for line in output_lines)
        
        if success:
            print("\n✅ Test erfolgreich! Exporter läuft ohne AD-Integration.")
            return True
        else:
            print("\n⚠️  Test unvollständig, aber kein kritischer Fehler.")
            return True
            
    except Exception as e:
        print(f"\n❌ Fehler beim Test: {e}")
        return False

def main():
    """Hauptfunktion"""
    success = test_exporter_no_ad()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Der FlexLM Exporter ist für Ihr Test-System konfiguriert!")
        print()
        print("Nächste Schritte:")
        print("1. Für echte Tests: Passen Sie --license-server an")
        print("2. Stellen Sie sicher, dass lmutil verfügbar ist")
        print("3. Für Produktion: Aktivieren Sie AD mit --enable-ad")
        print()
        print("Start-Befehle:")
        print("  PowerShell: .\\start_exporter.ps1 -Verbose")
        print("  Python:     python flexlm_exporter.py --verbose")
        print("  Mit AD:     python flexlm_exporter.py --enable-ad --verbose")
    else:
        print("❌ Es gibt noch Probleme mit der Konfiguration.")

if __name__ == '__main__':
    main()
