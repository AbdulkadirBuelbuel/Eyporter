#!/usr/bin/env python3
"""
Enhanced FlexLM Exporter Demo - Mit verbesserter AD-Integration
Demonstriert die Verwendung des FlexLM Exporters mit automatischer AD-Erkennung
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from flexlm_exporter import FlexLMExporter

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enhanced_exporter_demo.log')
    ]
)

logger = logging.getLogger(__name__)

def demo_basic_exporter():
    """Demo: Basis-Exporter ohne AD-Integration"""
    print("\n" + "="*60)
    print("📊 DEMO: Basis FlexLM Exporter (ohne AD)")
    print("="*60)
    
    try:
        # Exporter mit explizit deaktivierter AD-Integration
        exporter = FlexLMExporter(
            license_server="lic-solidworks-emea.patec.group",
            port=25734,
            enable_ad=False  # Explizit deaktiviert
        )
        
        print("✅ Basis-Exporter erfolgreich initialisiert")
        print(f"License Server: {exporter.license_server}")
        print(f"Port: {exporter.port}")
        print(f"AD Integration: {exporter.enable_ad}")
        
        # Ein Update durchführen
        print("\n🔄 Führe License-Update durch...")
        exporter.update_metrics()
        print("✅ Metriken erfolgreich aktualisiert")
        
    except Exception as e:
        print(f"❌ Fehler beim Basis-Exporter: {e}")

def demo_auto_detection():
    """Demo: Automatische AD-Erkennung"""
    print("\n" + "="*60)
    print("🤖 DEMO: Automatische AD-Erkennung")
    print("="*60)
    
    try:
        # Exporter mit automatischer AD-Erkennung (Standard)
        exporter = FlexLMExporter(
            license_server="lic-solidworks-emea.patec.group",
            port=25734
            # enable_ad wird automatisch erkannt
        )
        
        print("✅ Auto-Detection Exporter erfolgreich initialisiert")
        print(f"License Server: {exporter.license_server}")
        print(f"Port: {exporter.port}")
        print(f"AD Integration automatisch aktiviert: {exporter.enable_ad}")
        
        if exporter.ad_helper:
            print(f"AD Server: {exporter.ad_helper.ad_server}")
            print(f"Domain: {exporter.ad_helper.domain}")
            print(f"AD aktiv: {exporter.ad_helper.is_enabled()}")
        
    except Exception as e:
        print(f"❌ Fehler bei Auto-Detection: {e}")

def demo_explicit_ad_config():
    """Demo: Explizite AD-Konfiguration"""
    print("\n" + "="*60)
    print("⚙️  DEMO: Explizite AD-Konfiguration")
    print("="*60)
    
    try:
        # Exporter mit expliziter AD-Konfiguration
        exporter = FlexLMExporter(
            license_server="lic-solidworks-emea.patec.group",
            port=25734,
            enable_ad=True,  # Explizit aktiviert
            ad_server="dc01.company.com",  # Beispiel-Server
            ad_username="DOMAIN\\serviceuser",  # Beispiel-Benutzer
            ad_password="password123"  # Beispiel-Passwort
        )
        
        print("✅ Explizit konfigurierter Exporter initialisiert")
        print(f"AD Integration erzwungen: {exporter.enable_ad}")
        
        if exporter.ad_helper:
            print(f"Konfigurierter AD Server: {exporter.ad_helper.ad_server}")
            print(f"Konfigurierter Username: {exporter.ad_helper.username}")
        
    except Exception as e:
        print(f"❌ Fehler bei expliziter Konfiguration: {e}")

def demo_config_file():
    """Demo: Konfiguration über ad_config.ini"""
    print("\n" + "="*60)
    print("📄 DEMO: Konfiguration über ad_config.ini")
    print("="*60)
    
    # Beispiel-Konfigurationsdatei erstellen (falls noch nicht vorhanden)
    if not os.path.exists("ad_config.ini"):
        print("ℹ️  Erstelle Beispiel ad_config.ini...")
        example_config = """[ActiveDirectory]
# Active Directory Server (optional - wird automatisch erkannt wenn leer)
server = 

# Benutzerdaten für AD-Zugriff (optional - versucht Windows Integrated Authentication wenn leer)
# Format: DOMAIN\\username oder username@domain.com
username = 
password = 

# Cache-Timeout in Sekunden (Standard: 300 = 5 Minuten)
cache_timeout = 300

# Beispiel-Konfiguration (auskommentiert):
# server = dc01.company.com
# username = COMPANY\\serviceuser
# password = SecretPassword123
# cache_timeout = 600"""
        
        with open("ad_config.ini", "w", encoding="utf-8") as f:
            f.write(example_config)
        print("✅ Beispiel ad_config.ini erstellt")
    
    try:
        # Exporter lädt automatisch aus ad_config.ini
        exporter = FlexLMExporter(
            license_server="lic-solidworks-emea.patec.group",
            port=25734,
            enable_ad=True  # AD aktiviert, Konfiguration aus Datei
        )
        
        print("✅ Exporter mit Konfigurationsdatei initialisiert")
        print(f"Config-Datei vorhanden: {os.path.exists('ad_config.ini')}")
        
        if exporter.ad_helper:
            print(f"Cache Timeout: {exporter.ad_helper.cache_timeout}")
            print(f"Location Attributes: {len(exporter.ad_helper.location_attributes)}")
        
    except Exception as e:
        print(f"❌ Fehler bei Config-File Demo: {e}")

def demo_production_simulation():
    """Demo: Produktions-Simulation"""
    print("\n" + "="*60)
    print("🏭 DEMO: Produktions-Simulation")
    print("="*60)
    
    try:
        print("🔄 Simuliere Produktionsumgebung...")
        
        # Exporter wie in Produktion (automatische Erkennung)
        exporter = FlexLMExporter()  # Alle Standardwerte
        
        print("✅ Produktions-Exporter gestartet")
        print(f"Automatische AD-Erkennung: {exporter.enable_ad}")
        
        # Simuliere mehrere Updates
        for i in range(3):
            print(f"\n📊 Update {i+1}/3...")
            try:
                exporter.update_metrics()
                print(f"✅ Update {i+1} erfolgreich")
                
                # Zeige einige Metriken
                if hasattr(exporter, 'server_up'):
                    server_status = list(exporter.server_up.collect())[0]
                    for sample in server_status.samples:
                        print(f"   Server Status: {sample.value}")
                
            except Exception as e:
                print(f"⚠️  Update {i+1} Fehler: {e}")
            
            if i < 2:  # Nicht beim letzten Durchlauf warten
                time.sleep(2)
        
    except Exception as e:
        print(f"❌ Fehler bei Produktions-Simulation: {e}")

def show_system_info():
    """Zeigt Systeminfos an"""
    print("\n" + "="*60)
    print("💻 SYSTEM-INFORMATIONEN")
    print("="*60)
    
    import platform
    print(f"Betriebssystem: {platform.system()} {platform.release()}")
    print(f"Python Version: {sys.version}")
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    
    # Überprüfe Dependencies
    try:
        import win32api
        print("✅ pywin32 verfügbar")
    except ImportError:
        print("❌ pywin32 nicht verfügbar")
    
    try:
        import ldap3
        print("✅ ldap3 verfügbar")
    except ImportError:
        print("❌ ldap3 nicht verfügbar")
    
    try:
        import prometheus_client
        print("✅ prometheus_client verfügbar")
    except ImportError:
        print("❌ prometheus_client nicht verfügbar")
    
    # Datei-Status
    files = [
        "flexlm_exporter.py",
        "active_directory_helper.py", 
        "ad_config.ini",
        "requirements.txt"
    ]
    
    print(f"\n📁 Dateistatus:")
    for file in files:
        exists = "✅" if os.path.exists(file) else "❌"
        print(f"   {exists} {file}")

def main():
    """Hauptdemo-Funktion"""
    print("🚀 Enhanced FlexLM Exporter - Umfassende Demo")
    print("="*80)
    
    show_system_info()
    
    # Demos ausführen
    demo_basic_exporter()
    demo_auto_detection()
    demo_explicit_ad_config()
    demo_config_file()
    demo_production_simulation()
    
    print("\n" + "="*80)
    print("🎉 Alle Demos abgeschlossen!")
    print("📋 Prüfen Sie die Logs für Details: enhanced_exporter_demo.log")
    print("🌐 Öffnen Sie http://localhost:8000/metrics für Live-Metriken")
    print("="*80)

if __name__ == "__main__":
    main()
