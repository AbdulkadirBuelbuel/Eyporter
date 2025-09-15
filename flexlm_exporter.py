#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus (SolidWorks Fokus)
Mit Username -> Location Mapping und Multi-Server YAML Support.
"""
import time, subprocess, re, logging, threading, os, sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from prometheus_client import Counter, Gauge, start_http_server, REGISTRY

# Username Location Mapper
try:
    from username_location_mapper import UsernameLocationMapper
    USERNAME_MAPPING_AVAILABLE = True
except ImportError as e:
    USERNAME_MAPPING_AVAILABLE = False
    print(f"WARNUNG: Username Location Mapping nicht verfügbar: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False

def _app_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

@dataclass
class FlexLMServerTarget:
    host: str
    port: int
    lmutil_path: str

class FlexLMExporter:
    def __init__(self,
                 license_server: str = "lic-solidworks-emea.patec.group",
                 port: int = 25734,
                 lmutil_path: str = r"C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe",
                 mapping_file: str = "mapping.json",
                 servers: Optional[List[FlexLMServerTarget]] = None,
                 verbose: bool = False):
        self.base_dir = _app_base_dir()
        self.verbose = verbose or os.environ.get("SWX_VERBOSE", "0") == "1"

        # lmutil path abs
        if not os.path.isabs(lmutil_path):
            lmutil_path = os.path.join(self.base_dir, lmutil_path)
        self.lmutil_path = lmutil_path

        # mapping.json finden
        if not os.path.isabs(mapping_file):
            candidates = []
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                candidates.append(os.path.join(sys._MEIPASS, mapping_file))
            candidates += [
                os.path.join(self.base_dir, mapping_file),
                mapping_file,
            ]
            for c in candidates:
                if os.path.exists(c):
                    mapping_file = c
                    break
        self.mapping_file = mapping_file

        self.license_server = license_server
        self.port = port
        self.location_mapper = None
        if USERNAME_MAPPING_AVAILABLE:
            try:
                self.location_mapper = UsernameLocationMapper(self.mapping_file)
            except Exception as e:
                if self.verbose:
                    logger.warning(f"Mapping init fehlgeschlagen: {e}")

        # Targets Liste
        if servers and len(servers) > 0:
            fixed = []
            for t in servers:
                lp = t.lmutil_path or self.lmutil_path
                if not os.path.isabs(lp):
                    lp = os.path.join(self.base_dir, lp)
                fixed.append(FlexLMServerTarget(t.host, t.port, lp))
            self.targets = fixed
        else:
            self.targets = [FlexLMServerTarget(self.license_server, self.port, self.lmutil_path)]

        self.setup_metrics()
        REGISTRY.register(self)
        self._last_feature_count = 0
        self._last_user_count = 0

    def setup_metrics(self):
        self.server_up = Gauge('flexlm_server_up', 'Server erreichbar (1/0)', ['server'])
        self.feature_total = Gauge('flexlm_feature_total_licenses', 'Total Lizenzen', ['server','vendor','feature'])
        self.feature_used = Gauge('flexlm_feature_used_licenses', 'Verwendete Lizenzen', ['server','vendor','feature'])
        self.feature_available = Gauge('flexlm_feature_available_licenses', 'Verfügbare Lizenzen', ['server','vendor','feature'])
        self.user_licenses = Gauge('flexlm_user_licenses', 'Benutzer Lizenz', ['server','vendor','feature','user','hostname','display','location'])
        self.location_licenses = Gauge('flexlm_location_licenses_total', 'Lizenzen je Standort', ['server','location','feature'])
        self.location_users = Gauge('flexlm_location_users_total', 'User je Standort', ['server','location'])
        self.host_licenses = Gauge('flexlm_host_licenses_total', 'Lizenzen je Host', ['server','hostname','location'])
        self.daemon_up = Gauge('flexlm_daemon_up', 'Daemon Status', ['server','daemon','version'])
        self.scrape_duration = Gauge('flexlm_scrape_duration_seconds', 'Scrape Dauer')
        self.scrape_errors = Counter('flexlm_scrape_errors_total', 'Scrape Fehler')

    def _run_lmstat(self, host: str, port: int, lmutil_path: str) -> Tuple[str,str,int]:
        cmd = [lmutil_path, 'lmstat', '-c', f'{port}@{host}', '-a']
        if not os.path.exists(lmutil_path):
            return '', f'lmutil missing: {lmutil_path}', -99
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
        feature_hdr_re = re.compile(r'^Users of\s+([\w\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?.*Total of\s+(\d+)\s+licenses? in use\)', re.IGNORECASE)
        feature_hdr_alt = re.compile(r'^Users of\s+([\w\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?,\s+(\d+)\s+in use\)', re.IGNORECASE)
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
                um = user_line_re.search(raw) or user_line_generic.search(raw)
                if um:
                    username = um.group(1)
                    hostname = um.group(2)
                    display = um.group(3) if um.lastindex and um.lastindex >= 3 else username
                    current_feature['users'].append({'username': username,'hostname': hostname,'display': display,'feature': current_feature['name']})
                    data['users'].append({'username': username,'hostname': hostname,'display': display,'feature': current_feature['name']})
        return data

    def collect_metrics_for_target(self, target: FlexLMServerTarget):
        stdout, stderr, rc = self._run_lmstat(target.host, target.port, target.lmutil_path)
        server_label = f"{target.host}:{target.port}"
        if rc != 0 or not stdout.strip():
            self.server_up.labels(server=server_label).set(0)
            self.scrape_errors.inc()
            if self.verbose:
                print(f"DEBUG {server_label} rc={rc} stderr={stderr.strip()} lmutil={target.lmutil_path} exists={os.path.exists(target.lmutil_path)}")
            return 0, 0
        data = self.parse_lmstat_output(stdout)
        self.server_up.labels(server=server_label).set(1 if data['server_status'] else 0)
        vendor = 'solidworks'
        for d in data['daemons']:
            self.daemon_up.labels(server=server_label, daemon=d['name'], version=d['version']).set(1 if d['status']=='UP' else 0)
        for feature in data['features']:
            self.feature_total.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['total'])
            self.feature_used.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['used'])
            self.feature_available.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['available'])
            loc_counts: Dict[Tuple[str,str], int] = {}
            for u in feature['users']:
                location = 'Unknown'
                if self.location_mapper:
                    try:
                        location = self.location_mapper.get_user_location_info(u['username']).location
                    except Exception:
                        pass
                self.user_licenses.labels(server=server_label, vendor=vendor, feature=feature['name'], user=u['username'], hostname=u['hostname'], display=u['display'], location=location).set(1)
                loc_counts[(location, feature['name'])] = loc_counts.get((location, feature['name']), 0) + 1
            for (loc, feat), cnt in loc_counts.items():
                self.location_licenses.labels(server=server_label, location=loc, feature=feat).set(cnt)
        host_counts: Dict[Tuple[str,str], int] = {}
        loc_user_sets: Dict[str, set] = {}
        for u in data['users']:
            location = 'Unknown'
            if self.location_mapper:
                try:
                    location = self.location_mapper.get_user_location_info(u['username']).location
                except Exception:
                    pass
            hk = (u['hostname'], location)
            host_counts[hk] = host_counts.get(hk, 0) + 1
            loc_user_sets.setdefault(location, set()).add(u['username'])
        for (hn, loc), cnt in host_counts.items():
            self.host_licenses.labels(server=server_label, hostname=hn, location=loc).set(cnt)
        for loc, users in loc_user_sets.items():
            self.location_users.labels(server=server_label, location=loc).set(len(users))
        return len(data['features']), len(data['users'])

    def collect_metrics(self):
        start = time.time()
        feats = 0; users = 0
        for t in self.targets:
            f,u = self.collect_metrics_for_target(t)
            feats += f; users += u
        self.scrape_duration.set(time.time() - start)
        self._last_feature_count = feats
        self._last_user_count = users

    def collect(self):
        self.collect_metrics()
        return []

    def start_server(self, port: int = 9090):
        start_http_server(port)
        self.collect_metrics()
        if len(self.targets) == 1:
            t = self.targets[0]
            print(f"Exporter läuft | Server {t.host}:{t.port} | Port {port} | Features {self._last_feature_count} | Users {self._last_user_count}")
        else:
            servers = ','.join([f"{t.host}:{t.port}" for t in self.targets])
            print(f"Exporter läuft | {len(self.targets)} Server ({servers}) | Port {port} | Features {self._last_feature_count} | Users {self._last_user_count}")
        logging.getLogger().setLevel(logging.ERROR)
        def loop():
            while True:
                time.sleep(30)
                self.collect_metrics()
        threading.Thread(target=loop, daemon=True).start()
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            pass

def load_servers_yaml(path: str) -> List[FlexLMServerTarget]:
    if not YAML_AVAILABLE:
        return []
    try:
        base_dir = _app_base_dir()
        # YAML lokalisieren
        if not os.path.isabs(path):
            candidates = []
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                candidates.append(os.path.join(sys._MEIPASS, path))
            candidates += [os.path.join(base_dir, path), path]
            for c in candidates:
                if os.path.exists(c):
                    path = c; break
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        servers_section = data.get('servers', []) if isinstance(data, dict) else []
        targets: List[FlexLMServerTarget] = []
        for entry in servers_section:
            if not isinstance(entry, dict):
                continue
            host = entry.get('host')
            port = entry.get('port') or entry.get('license_port')
            lmutil_path = entry.get('lmutil_path') or 'lmutil.exe'
            if not host or not port:
                continue
            try:
                port = int(port)
            except Exception:
                continue
            if not os.path.isabs(lmutil_path):
                lmutil_candidates = []
                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    lmutil_candidates.append(os.path.join(sys._MEIPASS, 'lmutil.exe'))
                lmutil_candidates += [
                    os.path.join(base_dir, lmutil_path),
                    os.path.join(base_dir, 'lmutil.exe'),
                    lmutil_path
                ]
                for c in lmutil_candidates:
                    if os.path.exists(c):
                        lmutil_path = c; break
            targets.append(FlexLMServerTarget(host=host, port=port, lmutil_path=lmutil_path))
        return targets
    except Exception:
        return []

def main():
    import argparse
    p = argparse.ArgumentParser(description='FlexLM Exporter (SolidWorks)')
    p.add_argument('--license-server', default='lic-solidworks-emea.patec.group')
    p.add_argument('--license-port', type=int, default=25734)
    p.add_argument('--exporter-port', type=int, default=9090)
    p.add_argument('--lmutil-path', default=r'C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe')
    p.add_argument('--mapping-file', default='mapping.json')
    p.add_argument('--servers-yaml')
    p.add_argument('--verbose','-v', action='store_true')
    args = p.parse_args()
    servers: List[FlexLMServerTarget] = []
    if args.servers_yaml:
        servers = load_servers_yaml(args.servers_yaml)
    exporter = FlexLMExporter(
        license_server=args.license_server,
        port=args.license_port,
        lmutil_path=args.lmutil_path,
        mapping_file=args.mapping_file,
        servers=servers,
        verbose=args.verbose
    )
    exporter.start_server(args.exporter_port)

if __name__ == '__main__':
    main()
