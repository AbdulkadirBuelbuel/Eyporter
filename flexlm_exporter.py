#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus
Speziell für SolidWorks Lizenzserver

Dieser Exporter sammelt Informationen von FlexLM-basierten Lizenzservern
und stellt sie als Prometheus-Metriken zur Verfügung.
"""

import time
import subprocess
import re
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import threading
from prometheus_client import Counter, Gauge, Info, start_http_server, REGISTRY
from prometheus_client.core import CollectorRegistry

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlexLMExporter:
    """FlexLM License Server Exporter für Prometheus"""
    
    def __init__(self, license_server: str = "lic-solidworks-emea.patec.group", port: int = 25734, lmutil_path: str = "C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe"):
        self.license_server = license_server
        self.port = port
        self.lmutil_path = lmutil_path
        
        # Prometheus Metriken definieren
        self.setup_metrics()
        
        # Registrierung beim Prometheus Registry
        REGISTRY.register(self)
        
    def setup_metrics(self):
        """Initialisiert alle Prometheus-Metriken"""
        
        # Server Status
        self.server_up = Gauge(
            'flexlm_server_up',
            'FlexLM Server erreichbar (1 = up, 0 = down)',
            ['server']
        )
        
        # Feature Informationen
        self.feature_total = Gauge(
            'flexlm_feature_total_licenses',
            'Gesamtanzahl der verfügbaren Lizenzen pro Feature',
            ['server', 'vendor', 'feature']
        )
        
        self.feature_used = Gauge(
            'flexlm_feature_used_licenses',
            'Anzahl der verwendeten Lizenzen pro Feature',
            ['server', 'vendor', 'feature']
        )
        
        self.feature_available = Gauge(
            'flexlm_feature_available_licenses',
            'Anzahl der verfügbaren Lizenzen pro Feature',
            ['server', 'vendor', 'feature']
        )
        
        # Benutzer Informationen
        self.user_licenses = Gauge(
            'flexlm_user_licenses',
            'Anzahl der von einem Benutzer verwendeten Lizenzen',
            ['server', 'vendor', 'feature', 'user', 'hostname', 'display']
        )
        
        # Computer/Hostname Informationen
        self.host_licenses = Gauge(
            'flexlm_host_licenses_total',
            'Gesamtanzahl der Lizenzen pro Host',
            ['server', 'hostname']
        )
        
        # Daemon Status
        self.daemon_up = Gauge(
            'flexlm_daemon_up',
            'Status der License Daemons (1 = up, 0 = down)',
            ['server', 'daemon', 'version']
        )
        
        # Scrape Informationen
        self.scrape_duration = Gauge(
            'flexlm_scrape_duration_seconds',
            'Zeit für das Sammeln der Metriken'
        )
        
        self.scrape_errors = Counter(
            'flexlm_scrape_errors_total',
            'Anzahl der Fehler beim Sammeln der Metriken'
        )

    def run_lmutil_command(self, args: List[str]) -> Tuple[int, str, str]:
        """
        Führt lmutil mit einer Liste von Argumenten aus.
        Gibt (returncode, stdout, stderr) zurück.
        """
        cmd = [self.lmutil_path] + args
        logger.debug(f"Calling lmutil: {cmd!r}")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            logger.debug(f"lmutil returncode={res.returncode}")
            logger.debug(f"lmutil stdout:\n{res.stdout}")
            logger.debug(f"lmutil stderr:\n{res.stderr}")
            return res.returncode, res.stdout, res.stderr

        except subprocess.TimeoutExpired as e:
            logger.error(f"lmutil timeout: {e}")
            return -1, "", "TimeoutExpired"
        except Exception as e:
            logger.error(f"lmutil exception: {e}")
            return -1, "", str(e)
        

    def parse_lmstat_output(self, output: str) -> Dict:
        """Parsed die Ausgabe von lmstat -a"""
        data = {
            'server_status': False,
            'daemons': [],
            'features': [],
            'users': []
        }
        
        lines = output.split('\n')
        current_feature = None
        in_users_section = False
        
        for line in lines:
            original_line = line
            line = line.strip()
            
            # Server Status prüfen
            if 'license server UP' in line:
                data['server_status'] = True
            elif 'Cannot connect to license server' in line:
                data['server_status'] = False
            
            # Daemon Status
            daemon_match = re.search(r'(\w+): UP v([0-9.]+)', line)
            if daemon_match:
                daemon_name = daemon_match.group(1)
                version = daemon_match.group(2)
                data['daemons'].append({
                    'name': daemon_name,
                    'status': 'UP',
                    'version': version
                })
            
            # Feature Informationen
            feature_match = re.search(r'Users of (\w+):\s+\(Total of (\d+) license[s]? issued;\s+Total of (\d+) license[s]? in use\)', line)
            if feature_match:
                feature_name = feature_match.group(1)
                total_licenses = int(feature_match.group(2))
                used_licenses = int(feature_match.group(3))
                
                current_feature = {
                    'name': feature_name,
                    'total': total_licenses,
                    'used': used_licenses,
                    'available': total_licenses - used_licenses,
                    'users': []
                }
                data['features'].append(current_feature)
                in_users_section = True
                continue
            
            # Neues Feature beginnt - beende aktuellen Benutzer-Bereich
            if line.startswith('Users of ') and current_feature:
                in_users_section = False
                current_feature = None
            
            # Benutzer Informationen (erweitert für Computer-Namen)
            if in_users_section and current_feature:
                # Pattern für Benutzer-Zeilen: "    username hostname display (v2022.1105) (license_server/27000 1234), start ..."
                user_match = re.search(r'^\s+(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)', original_line)
                if user_match:
                    username = user_match.group(1)
                    hostname = user_match.group(2)
                    display = user_match.group(3)
                    
                    user_info = {
                        'username': username,
                        'hostname': hostname,
                        'display': display,
                        'feature': current_feature['name']
                    }
                    
                    current_feature['users'].append(user_info)
                    data['users'].append(user_info)
                    continue
        
        return data

    def collect_metrics(self):
        """Sammelt alle Metriken vom FlexLM Server"""
        start_time = time.time()
        
        try:
            # lmstat -a ausführen für detaillierte Informationen
            rc, output, error = self.run_lmutil_command([
                "lmstat", "-a", "-c", f"{self.port}@{self.license_server}"
            ])

            # 2) Fehler-Metrik setzen
            if rc != 0:
                self.server_up.labels(server=f"{self.license_server}:{self.port}").set(0)
                self.scrape_errors.inc()
                logger.error("lmutil fehlerhaft, rc=%d, err=%s", rc, error)
                return

            # 3) Ausgabe verarbeiten
            self.server_up.labels(server=f"{self.license_server}:{self.port}").set(1)
            data = self.parse_lmstat_output(output)

            server_label = f"{self.license_server}:{self.port}"
            self.server_up.labels(server=server_label).set(1 if data['server_status'] else 0)
            
            # Daemon Status
            for daemon in data['daemons']:
                self.daemon_up.labels(
                    server=server_label,
                    daemon=daemon['name'],
                    version=daemon['version']
                ).set(1 if daemon['status'] == 'UP' else 0)
            
            # Feature Metriken
            for feature in data['features']:
                vendor = 'solidworks'  # Annahme für SolidWorks
                
                self.feature_total.labels(
                    server=server_label,
                    vendor=vendor,
                    feature=feature['name']
                ).set(feature['total'])
                
                self.feature_used.labels(
                    server=server_label,
                    vendor=vendor,
                    feature=feature['name']
                ).set(feature['used'])
                
                self.feature_available.labels(
                    server=server_label,
                    vendor=vendor,
                    feature=feature['name']
                ).set(feature['available'])
                
                # Benutzer-spezifische Metriken
                for user in feature['users']:
                    self.user_licenses.labels(
                        server=server_label,
                        vendor=vendor,
                        feature=feature['name'],
                        user=user['username'],
                        hostname=user['hostname'],
                        display=user['display']
                    ).set(1)  # 1 Lizenz pro Benutzer/Feature Kombination
            
            # Host-basierte Metriken (Computer-Namen aggregieren)
            host_counts = {}
            for user in data['users']:
                hostname = user['hostname']
                if hostname in host_counts:
                    host_counts[hostname] += 1
                else:
                    host_counts[hostname] = 1
            
            for hostname, count in host_counts.items():
                self.host_licenses.labels(
                    server=server_label,
                    hostname=hostname
                ).set(count)
            
            logger.info(f"Metriken erfolgreich gesammelt. Features: {len(data['features'])}, Users: {len(data['users'])}")
            
        except Exception as e:
            logger.error(f"Fehler beim Sammeln der Metriken: {e}")
            self.scrape_errors.inc()
        
        finally:
            # Scrape-Dauer aufzeichnen
            duration = time.time() - start_time
            self.scrape_duration.set(duration)

    def collect(self):
        """Prometheus Collector Interface"""
        self.collect_metrics()
        return []

    def start_server(self, port: int = 9090):
        """Startet den HTTP Server für Prometheus Metriken"""
        logger.info(f"Starte FlexLM Exporter auf Port {port}")
        logger.info(f"Metriken verfügbar unter: http://localhost:{port}/metrics")
        logger.info(f"Überwachung von FlexLM Server: {self.license_server}:{self.port}")
        
        start_http_server(port)
        
        # Initiale Metriken sammeln
        self.collect_metrics()
        
        # Kontinuierliche Aktualisierung in separatem Thread
        def update_metrics():
            while True:
                time.sleep(30)  # Alle 30 Sekunden aktualisieren
                self.collect_metrics()
        
        update_thread = threading.Thread(target=update_metrics, daemon=True)
        update_thread.start()
        
        logger.info("FlexLM Exporter gestartet. Drücken Sie Ctrl+C zum Beenden.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("FlexLM Exporter beendet.")


def main():
    """Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FlexLM License Server Exporter für Prometheus')
    parser.add_argument('--license-server', default='localhost', 
                       help='FlexLM License Server Hostname/IP (default: localhost)')
    parser.add_argument('--license-port', type=int, default=27000,
                       help='FlexLM License Server Port (default: 27000)')
    parser.add_argument('--exporter-port', type=int, default=9090,
                       help='Port für den Prometheus Exporter (default: 9090)')
    parser.add_argument('--lmutil-path', default='lmutil',
                       help='Pfad zur lmutil Binary (default: lmutil im PATH)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose Logging aktivieren')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Exporter erstellen und starten
    exporter = FlexLMExporter(
        license_server=args.license_server,
        port=args.license_port,
        lmutil_path=args.lmutil_path
    )
    
    exporter.start_server(args.exporter_port)


if __name__ == '__main__':
    main()
