#!/usr/bin/env python3
"""
Production-Ready FlexLM Exporter - Enhanced AD Integration
Final Version mit automatischer Umgebungserkennung
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from flexlm_exporter import FlexLMExporter
from prometheus_client import start_http_server

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global exporter instance
exporter = None

def signal_handler(signum, frame):
    """Graceful shutdown handler"""
    logger.info("🛑 Shutdown-Signal empfangen, beende Exporter...")
    if exporter:
        logger.info("👋 FlexLM Exporter beendet")
    sys.exit(0)

def main():
    """Production-ready main function"""
    global exporter
    
    # Signal Handler für graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 FlexLM Exporter - Enhanced AD Integration")
    print("="*60)
    print(f"🐍 Python {sys.version}")
    print(f"📁 Arbeitsverzeichnis: {os.getcwd()}")
    print(f"⚙️  Config-Datei: {'✅ Vorhanden' if os.path.exists('ad_config.ini') else '❌ Nicht gefunden'}")
    print("="*60)
    
    try:
        # Exporter mit automatischer Konfiguration erstellen
        logger.info("🔧 Initialisiere FlexLM Exporter...")
        exporter = FlexLMExporter(
            license_server="lic-solidworks-emea.patec.group",
            port=25734
            # Alle anderen Parameter werden automatisch erkannt
        )
        
        print("✅ FlexLM Exporter erfolgreich initialisiert")
        print(f"📊 License Server: {exporter.license_server}:{exporter.port}")
        print(f"🏢 AD Integration: {'✅ Aktiviert' if exporter.enable_ad else '❌ Deaktiviert'}")
        
        if exporter.enable_ad and exporter.ad_helper:
            print(f"🌐 AD Server: {exporter.ad_helper.ad_server}")
            print(f"🏘️  Domain: {exporter.ad_helper.domain}")
            print(f"👤 Username: {exporter.ad_helper.username or 'Windows Integrated'}")
        
        # HTTP Server für Prometheus Metriken starten
        prometheus_port = 8000
        start_http_server(prometheus_port)
        logger.info(f"🌐 Prometheus HTTP Server gestartet auf Port {prometheus_port}")
        print(f"🌐 Metriken verfügbar unter: http://localhost:{prometheus_port}/metrics")
        
        print("\n" + "="*60)
        print("✅ FlexLM Exporter läuft!")
        print("🔄 Drücken Sie Ctrl+C zum Beenden")
        print("="*60)
        
        # Hauptschleife - Update Metriken alle 60 Sekunden
        update_interval = 60
        while True:
            try:
                # Update-Zyklusinfo
                logger.info("🔄 Aktualisiere License-Metriken...")
                
                # Metrics werden automatisch über collect() aktualisiert
                # wenn Prometheus sie abruft
                
                logger.info(f"✅ Metriken aktualisiert - nächstes Update in {update_interval}s")
                time.sleep(update_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Fehler beim Metriken-Update: {e}")
                time.sleep(10)  # Kurze Pause bei Fehlern
        
    except Exception as e:
        logger.error(f"❌ Kritischer Fehler: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
