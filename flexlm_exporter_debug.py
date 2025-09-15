#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus - Debug Version
Speziell für SolidWorks Lizenzserver

Dieser Exporter sammelt Informationen von FlexLM-basierten Lizenzservern
und stellt sie als Prometheus-Metriken zur Verfügung.
Erweitert um Standortableitung aus Benutzernamen via mapping.json.
"""

import time
import subprocess
import re
import logging
from typing import Dict, List, Tuple, Optional
import threading
from prometheus_client import Counter, Gauge, start_http_server, REGISTRY
from dataclasses import dataclass
import os
import sys

# Username Location Mapper importieren
try:
    from username_location_mapper import UsernameLocationMapper
    USERNAME_MAPPING_AVAILABLE = True
except ImportError as e:
    USERNAME_MAPPING_AVAILABLE = False
    print(f"WARNUNG: Username Location Mapping nicht verfügbar: {e}")

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import yaml  # Für Mehr-Server YAML-Konfiguration
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False


def _app_base_dir() -> str:
    """Bestimmt das Basisverzeichnis (PyInstaller kompatibel)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller executable - use the directory containing the exe
        return os.path.dirname(sys.executable)
    else:
        # Development
        return os.path.dirname(os.path.abspath(__file__))


@dataclass
class FlexLMServerTarget:
    host: str
    port: int
    lmutil_path: str


class FlexLMExporter:
    """FlexLM License Server Exporter für Prometheus"""
    def __init__(self, license_server: str = "lic-solidworks-emea.patec.group", port: int = 25734,
                 lmutil_path: str = r"C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe",
                 mapping_file: str = "mapping.json", servers: Optional[List[FlexLMServerTarget]] = None,
                 verbose: bool = False):
        self.base_dir = _app_base_dir()
        self.verbose = verbose or os.environ.get("SWX_VERBOSE", "0") == "1"
        
        # Pfade absolutieren
        if not os.path.isabs(lmutil_path):
            lmutil_path = os.path.join(self.base_dir, lmutil_path)
        if not os.path.isabs(mapping_file):
            # Try multiple locations for mapping file
            candidates = [
                os.path.join(self.base_dir, mapping_file),
                mapping_file,  # current directory
            ]
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                candidates.insert(0, os.path.join(sys._MEIPASS, mapping_file))
            
            mapping_file_found = None
            for candidate in candidates:
                if os.path.exists(candidate):
                    mapping_file_found = candidate
                    break
            
            if mapping_file_found:
                mapping_file = mapping_file_found
        
        self.mapping_file = mapping_file
        # Attribute für Einzelserver (auch bei Multi-Server für Rückwärtskompatibilität)
        self.license_server = license_server
        self.port = port
        self.lmutil_path = lmutil_path
        self.location_mapper = None
        if USERNAME_MAPPING_AVAILABLE:
            try:
                self.location_mapper = UsernameLocationMapper(mapping_file)
            except Exception as e:
                if self.verbose:
                    logger.warning(f"⚠️  Username Mapping-Initialisierung fehlgeschlagen: {e}")
        # Server Targets
        if servers and len(servers) > 0:
            # ensure absolute lmutil paths
            fixed = []
            for t in servers:
                lp = t.lmutil_path or lmutil_path
                if not os.path.isabs(lp):
                    lp = os.path.join(self.base_dir, lp)
                fixed.append(FlexLMServerTarget(t.host, t.port, lp))
            self.targets = fixed
        else:
            self.targets = [FlexLMServerTarget(license_server, port, lmutil_path)]
        # Prometheus Metriken definieren
        self.setup_metrics()
        # Registrierung beim Prometheus Registry
        REGISTRY.register(self)
        self._last_feature_count = 0
        self._last_user_count = 0

    def setup_metrics(self):
        """Initialisiert alle Prometheus-Metriken"""
        self.server_up = Gauge('flexlm_server_up', 'FlexLM Server erreichbar (1 = up, 0 = down)', ['server'])
        self.feature_total = Gauge('flexlm_feature_total_licenses', 'Gesamtanzahl der verfügbaren Lizenzen pro Feature', ['server', 'vendor', 'feature'])
        self.feature_used = Gauge('flexlm_feature_used_licenses', 'Anzahl der verwendeten Lizenzen pro Feature', ['server', 'vendor', 'feature'])
        self.feature_available = Gauge('flexlm_feature_available_licenses', 'Anzahl der verfügbaren Lizenzen pro Feature', ['server', 'vendor', 'feature'])
        self.user_licenses = Gauge('flexlm_user_licenses', 'Anzahl der von einem Benutzer verwendeten Lizenzen', ['server', 'vendor', 'feature', 'user', 'hostname', 'display', 'location'])
        self.location_licenses = Gauge('flexlm_location_licenses_total', 'Gesamtanzahl der Lizenzen pro Standort', ['server', 'location', 'feature'])
        self.location_users = Gauge('flexlm_location_users_total', 'Anzahl der Benutzer pro Standort', ['server', 'location'])
        self.host_licenses = Gauge('flexlm_host_licenses_total', 'Gesamtanzahl der Lizenzen pro Host', ['server', 'hostname', 'location'])
        self.daemon_up = Gauge('flexlm_daemon_up', 'Status der License Daemons (1 = up, 0 = down)', ['server', 'daemon', 'version'])
        self.scrape_duration = Gauge('flexlm_scrape_duration_seconds', 'Zeit für das Sammeln der Metriken')
        self.scrape_errors = Counter('flexlm_scrape_errors_total', 'Anzahl der Fehler beim Sammeln der Metriken')

    def _run_lmstat(self, host: str, port: int, lmutil_path: str) -> Tuple[str, str, int]:
        cmd = [lmutil_path, 'lmstat', '-c', f'{port}@{host}', '-a']
        if not os.path.exists(lmutil_path):
            return '', f'lmutil not found: {lmutil_path}', -99
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            return proc.stdout or '', proc.stderr or '', proc.returncode
        except subprocess.TimeoutExpired:
            return '', 'timeout', -2
        except Exception as e:
            return '', str(e), -1

    def parse_lmstat_output(self, output: str) -> Dict:
        data = {'server_status': False, 'daemons': [], 'features': [], 'users': []}
        lines = output.splitlines()
        current_feature = None
        in_users_section = False
        
        # Robuste Regex-Patterns
        feature_hdr_re = re.compile(r'^Users of\s+([A-Za-z0-9_\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?\s+issued;.*Total of\s+(\d+)\s+licenses?\s+in use\)', re.IGNORECASE)
        feature_hdr_alt = re.compile(r'^Users of\s+([A-Za-z0-9_\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?,\s+(\d+)\s+in use\)', re.IGNORECASE)
        daemon_re = re.compile(r'(\w+): UP v([0-9.]+)')
        user_line_re = re.compile(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)', re.IGNORECASE)
        user_line_generic = re.compile(r'^\s*(\S+?)(?:@|\s+)([A-Za-z0-9_\-.]+)\s+\(v[0-9\.]+\)\s+\([^)]+\s+\d+\)', re.IGNORECASE)
        
        for raw in lines:
            line = raw.strip()
            if 'license server UP' in line:
                data['server_status'] = True
            dm = daemon_re.search(line)
            if dm:
                data['daemons'].append({'name': dm.group(1), 'status': 'UP', 'version': dm.group(2)})
            fm = feature_hdr_re.search(raw) or feature_hdr_alt.search(raw)
            if fm:
                current_feature = {
                    'name': fm.group(1),
                    'total': int(fm.group(2)),
                    'used': int(fm.group(3)),
                    'available': int(fm.group(2)) - int(fm.group(3)),
                    'users': []
                }
                data['features'].append(current_feature)
                in_users_section = True
                continue
            if line.startswith('Users of ') and not (feature_hdr_re.search(raw) or feature_hdr_alt.search(raw)):
                in_users_section = False
                current_feature = None
            if in_users_section and current_feature:
                um = user_line_re.search(raw)
                if not um:
                    um = user_line_generic.search(raw)
                    if um:
                        u = um.group(1)
                        h = um.group(2)
                        current_feature['users'].append({'username': u, 'hostname': h, 'display': u, 'feature': current_feature['name']})
                        data['users'].append({'username': u, 'hostname': h, 'display': u, 'feature': current_feature['name']})
                        continue
                if um:
                    username = um.group(1)
                    hostname = um.group(2)
                    display = um.group(3)
                    current_feature['users'].append({'username': username, 'hostname': hostname, 'display': display, 'feature': current_feature['name']})
                    data['users'].append({'username': username, 'hostname': hostname, 'display': display, 'feature': current_feature['name']})
        return data

    def collect_metrics_for_target(self, target: FlexLMServerTarget):
        stdout, stderr, rc = self._run_lmstat(target.host, target.port, target.lmutil_path)
        server_label = f"{target.host}:{target.port}"
        
        # Debug-Info bei Fehlern oder Verbose-Modus
        if self.verbose or rc != 0 or not stdout.strip():
            print(f"DEBUG {server_label}: lmutil_path={target.lmutil_path}, exists={os.path.exists(target.lmutil_path)}, rc={rc}")
            if stderr:
                print(f"DEBUG {server_label} STDERR: {stderr}")
        
        # Nur bei Verbose oder ENV-Variable loggen
        if self.verbose or os.environ.get('SWX_DUMP_RAW', '0') == '1':
            try:
                dump_dir = os.path.join(self.base_dir, 'raw_dumps')
                os.makedirs(dump_dir, exist_ok=True)
                dump_file = os.path.join(dump_dir, f"lmstat_{target.host}_{target.port}.log")
                with open(dump_file, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(stdout)
                    f.write('\n--- STDERR ---\n')
                    f.write(stderr)
                    f.write(f"\nRC={rc}\n")
            except Exception:
                pass
        
        if rc != 0 or not stdout.strip():
            self.server_up.labels(server=server_label).set(0)
            self.scrape_errors.inc()
            return 0, 0
        
        data = self.parse_lmstat_output(stdout)
        self.server_up.labels(server=server_label).set(1 if data['server_status'] else 0)
        
        for daemon in data['daemons']:
            self.daemon_up.labels(server=server_label, daemon=daemon['name'], version=daemon['version']).set(1 if daemon['status'] == 'UP' else 0)
        
        vendor = 'solidworks'
        total_users = len(data['users'])
        total_features = len(data['features'])
        
        for feature in data['features']:
            self.feature_total.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['total'])
            self.feature_used.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['used'])
            self.feature_available.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['available'])
            location_counts: Dict[str, int] = {}
            for user in feature['users']:
                location = 'Unknown'
                if self.location_mapper:
                    try:
                        location = self.location_mapper.get_user_location_info(user['username']).location
                    except Exception:
                        pass
                self.user_licenses.labels(server=server_label, vendor=vendor, feature=feature['name'], user=user['username'], hostname=user['hostname'], display=user['display'], location=location).set(1)
                location_counts[(location, feature['name'])] = location_counts.get((location, feature['name']), 0) + 1
            for (loc, feat_name), count in location_counts.items():
                self.location_licenses.labels(server=server_label, location=loc, feature=feat_name).set(count)
        
        host_counts: Dict[Tuple[str, str], int] = {}
        location_user_sets: Dict[str, set] = {}
        for user in data['users']:
            location = 'Unknown'
            if self.location_mapper:
                try:
                    location = self.location_mapper.get_user_location_info(user['username']).location
                except Exception:
                    pass
            host_key = (user['hostname'], location)
            host_counts[host_key] = host_counts.get(host_key, 0) + 1
            location_user_sets.setdefault(location, set()).add(user['username'])
        
        for (hn, loc), count in host_counts.items():
            self.host_licenses.labels(server=server_label, hostname=hn, location=loc).set(count)
        for loc, users in location_user_sets.items():
            self.location_users.labels(server=server_label, location=loc).set(len(users))
        
        return total_features, total_users

    def collect_metrics(self):
        start_time = time.time()
        total_feat = 0
        total_users = 0
        try:
            for t in self.targets:
                f, u = self.collect_metrics_for_target(t)
                total_feat += f
                total_users += u
        finally:
            self.scrape_duration.set(time.time() - start_time)
            self._last_feature_count = total_feat
            self._last_user_count = total_users

    def collect(self):
        self.collect_metrics()
        return []

    def start_server(self, port: int = 9090):
        start_http_server(port)
        
        # Debug-Info über die konfigurierten Targets
        if self.verbose:
            print(f"DEBUG: Base directory: {self.base_dir}")
            print(f"DEBUG: Configured targets: {len(self.targets)}")
            for i, target in enumerate(self.targets):
                print(f"DEBUG: Target {i+1}: {target.host}:{target.port}, lmutil={target.lmutil_path}, exists={os.path.exists(target.lmutil_path)}")
        
        self.collect_metrics()
        
        # Einmalige Statusmeldung beim Start
        if len(self.targets) == 1:
            t = self.targets[0]
            print(f"Exporter läuft | Server {t.host}:{t.port} | Port {port} | Features {self._last_feature_count} | Users {self._last_user_count}")
        else:
            server_list = ','.join([f"{t.host}:{t.port}" for t in self.targets])
            print(f"Exporter läuft | {len(self.targets)} Server ({server_list}) | Port {port} | Features {self._last_feature_count} | Users {self._last_user_count}")
        
        # Logging auf ERROR reduzieren (keine weiteren Ausgaben)
        logging.getLogger().setLevel(logging.ERROR)
        
        def update_metrics():
            while True:
                time.sleep(30)
                self.collect_metrics()
        
        threading.Thread(target=update_metrics, daemon=True).start()
        
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


def load_servers_yaml(path: str) -> List[FlexLMServerTarget]:
    if not YAML_AVAILABLE:
        return []
    try:
        if not os.path.isabs(path):
            # Try multiple locations for YAML file
            base_dir = _app_base_dir()
            candidates = [
                os.path.join(base_dir, path),
                path,  # current directory
            ]
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                candidates.insert(0, os.path.join(sys._MEIPASS, path))
            
            yaml_found = None
            for candidate in candidates:
                if os.path.exists(candidate):
                    yaml_found = candidate
                    break
            
            if yaml_found:
                path = yaml_found
            else:
                path = os.path.join(base_dir, path)
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f.read())
        servers_section = []
        if isinstance(data, dict):
            servers_section = data.get('servers', []) or []
        targets: List[FlexLMServerTarget] = []
        for entry in servers_section:
            if not isinstance(entry, dict):
                continue
            host = entry.get('host')
            port = entry.get('port') or entry.get('license_port') or entry.get('port')
            lmutil_path = entry.get('lmutil_path') or r"C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe"
            if host and port:
                try:
                    port = int(port)
                except Exception:
                    continue
                if not os.path.isabs(lmutil_path):
                    # Try multiple locations for lmutil.exe
                    base_dir = _app_base_dir()
                    lmutil_candidates = [
                        os.path.join(base_dir, lmutil_path),
                        os.path.join(base_dir, 'lmutil.exe'),
                        lmutil_path,
                    ]
                    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                        lmutil_candidates.insert(0, os.path.join(sys._MEIPASS, 'lmutil.exe'))
                    
                    lmutil_found = None
                    for candidate in lmutil_candidates:
                        if os.path.exists(candidate):
                            lmutil_found = candidate
                            break
                    
                    if lmutil_found:
                        lmutil_path = lmutil_found
                    else:
                        lmutil_path = os.path.join(base_dir, 'lmutil.exe')
                
                targets.append(FlexLMServerTarget(host=host, port=port, lmutil_path=lmutil_path))
        return targets
    except FileNotFoundError:
        return []
    except Exception:
        return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description='FlexLM License Server Exporter für Prometheus mit Username-basiertem Location Mapping - Debug Version')
    parser.add_argument('--license-server', default='lic-solidworks-emea.patec.group')
    parser.add_argument('--license-port', type=int, default=25734)
    parser.add_argument('--exporter-port', type=int, default=9090)
    parser.add_argument('--lmutil-path', default=r'C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe')
    parser.add_argument('--mapping-file', default='mapping.json')
    parser.add_argument('--servers-yaml')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()
    
    servers_list: List[FlexLMServerTarget] = []
    if args.servers_yaml:
        servers_list = load_servers_yaml(args.servers_yaml)
    
    exporter = FlexLMExporter(
        license_server=args.license_server,
        port=args.license_port,
        lmutil_path=args.lmutil_path,
        mapping_file=args.mapping_file,
        servers=servers_list,
        verbose=args.verbose
    )
    
    exporter.start_server(args.exporter_port)


if __name__ == '__main__':
    main()
