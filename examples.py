#!/usr/bin/env python3
"""
Beispiel-Skript für den FlexLM Exporter mit Active Directory Integration
Zeigt verschiedene Verwendungsmöglichkeiten
"""

import subprocess
import time
import sys
import os

def run_exporter_example(description: str, args: list, duration: int = 10):
    """Führt den Exporter mit gegebenen Argumenten aus"""
    print(f"\n{description}")
    print("=" * len(description))
    
    cmd = [
        r"C:\Users\abdul\OneDrive - Hochschule Furtwangen\Semester_7\Eyporter\.venv\Scripts\python.exe",
        "flexlm_exporter.py"
    ] + args
    
    print(f"Befehl: {' '.join(cmd)}")
    print(f"Läuft für {duration} Sekunden...")
    print("Metriken verfügbar unter: http://localhost:9090/metrics")
    print("Drücken Sie Ctrl+C zum vorzeitigen Beenden")
    print()
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            if process.poll() is not None:
                break
            time.sleep(1)
        
        if process.poll() is None:
            process.terminate()
            process.wait()
        
        print(f"✓ Beispiel abgeschlossen nach {duration} Sekunden")
        
    except KeyboardInterrupt:
        print("\n⚠️ Abgebrochen durch Benutzer")
        if process.poll() is None:
            process.terminate()
    except Exception as e:
        print(f"❌ Fehler: {e}")

def main():
    """Hauptfunktion mit verschiedenen Beispielen"""
    print("FlexLM Exporter - Verwendungsbeispiele")
    print("======================================")
    
    # Prüfe ob wir im richtigen Verzeichnis sind
    if not os.path.exists("flexlm_exporter.py"):
        print("❌ Fehler: flexlm_exporter.py nicht gefunden!")
        print("Bitte führen Sie dieses Skript im Projektverzeichnis aus.")
        return
    
    examples = [
        {
            "description": "1. Standard-Konfiguration mit AD-Integration",
            "args": ["--verbose"],
            "duration": 15
        },
        {
            "description": "2. Ohne Active Directory Integration",
            "args": ["--disable-ad", "--verbose"],
            "duration": 10
        },
        {
            "description": "3. Mit benutzerdefinierten License Server",
            "args": [
                "--license-server", "lic-solidworks-emea.patec.group",
                "--license-port", "25734",
                "--verbose"
            ],
            "duration": 15
        },
        {
            "description": "4. Demo-Modus (mit simulierten Daten)",
            "args": [],
            "duration": 10,
            "script": "demo_exporter.py"
        }
    ]
    
    for i, example in enumerate(examples):
        print(f"\nBeispiel {i+1} von {len(examples)}")
        
        if example.get("script"):
            # Spezielles Skript verwenden
            cmd = [
                r"C:\Users\abdul\OneDrive - Hochschule Furtwangen\Semester_7\Eyporter\.venv\Scripts\python.exe",
                example["script"]
            ]
            description = example["description"]
            duration = example["duration"]
            
            print(f"\n{description}")
            print("=" * len(description))
            print(f"Befehl: {' '.join(cmd)}")
            print(f"Läuft für {duration} Sekunden...")
            print("Metriken verfügbar unter: http://localhost:9090/metrics")
            print()
            
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                
                start_time = time.time()
                while time.time() - start_time < duration:
                    if process.poll() is not None:
                        break
                    time.sleep(1)
                
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                
                print(f"✓ Beispiel abgeschlossen nach {duration} Sekunden")
                
            except KeyboardInterrupt:
                print("\n⚠️ Abgebrochen durch Benutzer")
                if process.poll() is None:
                    process.terminate()
                break
            except Exception as e:
                print(f"❌ Fehler: {e}")
        else:
            # Standard Exporter verwenden
            run_exporter_example(
                example["description"],
                example["args"],
                example["duration"]
            )
        
        if i < len(examples) - 1:
            print("\nWeiter zum nächsten Beispiel? (Enter drücken oder Ctrl+C zum Beenden)")
            try:
                input()
            except KeyboardInterrupt:
                print("\n⚠️ Abgebrochen durch Benutzer")
                break
    
    print("\n" + "=" * 50)
    print("✅ Alle Beispiele abgeschlossen!")
    print("\nFür den produktiven Einsatz:")
    print("1. Passen Sie die Server-Parameter an")
    print("2. Stellen Sie sicher, dass lmutil verfügbar ist")
    print("3. Konfigurieren Sie Prometheus für das Scraping")
    print("4. Erstellen Sie Grafana-Dashboards für die Visualisierung")

if __name__ == '__main__':
    main()
