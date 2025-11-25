#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus
Mit AD City Location Lookup (non-blocking, single file)
"""
import time
import subprocess
import re
import os
import logging
import threading
from typing import Dict, List, Tuple, Optional
from prometheus_client import Counter, Gauge, start_http_server, REGISTRY
import queue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ADLocationLookup:
    """AD City Lookup mit Hintergrund-Thread und Cache, blockiert Scrapes nicht."""
    def __init__(self, domain: str = 'patec.group'):
        self.domain = domain
        self._cache: Dict[str, str] = {}
        self._failed_users: set[str] = set()
        self._lock = threading.Lock()
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="ADLocationWorker", daemon=True)
        self._worker.start()

    def stop(self):
        """Optional beim Shutdown aufrufen."""
        self._stop_event.set()
        try:
            self._queue.put_nowait("__STOP__")
        except queue.Full:
            pass
        self._worker.join(timeout=2)

    def get_location(self, username: str) -> str:
        """
        Nicht-blockierender Lookup:
        - Gibt sofort aus Cache zurück, wenn vorhanden
        - Sonst 'Unknown' und stößt AD-Abfrage im Hintergrund an
        """
        # Sicherstellen, dass wir immer den SamAccountName verwenden
        username_clean = username.split("\\")[-1].split("@")[0]
        username_lower = username_clean.lower().strip()
        if not username_lower:
            return "Unknown"

        with self._lock:
            if username_lower in self._cache:
                return self._cache[username_lower]
            if username_lower in self._failed_users:
                return "Unknown"

        # Noch nicht bekannt: Job in Queue legen (non-blocking)
        try:
            self._queue.put_nowait(username_lower)
        except queue.Full:
            pass

        return "Unknown"
        # Noch nicht bekannt: Job in Queue legen (non-blocking)
        try:
            self._queue.put_nowait(username_lower)
        except queue.Full:
            # Queue voll -> wir blockieren nicht, sondern liefern Unknown
            pass

        return "Unknown"

    def _worker_loop(self):
        """Hintergrundthread, der User aus der Queue abarbeitet und Cache füllt."""
        while not self._stop_event.is_set():
            try:
                username = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if username == "__STOP__":
                break

            # Nochmal checken, ob inzwischen gecached
            with self._lock:
                if username in self._cache or username in self._failed_users:
                    continue

            location = self._query_ad(username)

            with self._lock:
                if location and location != "Unknown":
                    self._cache[username] = location
                else:
                    self._failed_users.add(username)
                    self._cache[username] = "Unknown"

    
    def _query_ad(self, username: str) -> Optional[str]:
        """AD Query nur für City (Attribut: City). Läuft im Hintergrund-Thread."""
        try:
            ps_command = f"""
            try {{
                $user = Get-ADUser '{username}' -Server '{self.domain}' -Properties City -ErrorAction Stop
                $city = $user.City
                if ($city) {{ $city }} else {{ "Unknown" }}
            }} catch {{ "Unknown" }}
            """

            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=3
            )

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            logger.debug(f"AD raw stdout for {username!r}: {stdout!r}")
            if stderr:
                logger.debug(f"AD raw stderr for {username!r}: {stderr!r}")

            if result.returncode != 0:
                logger.warning(f"AD query rc={result.returncode} for {username}: {stderr}")
                return None

            if not stdout or stdout == "Unknown":
                return None

            city = stdout.strip()
            return city

        except subprocess.TimeoutExpired:
            logger.warning(f"AD query timeout for {username}")
            return None
        except Exception as e:
            logger.warning(f"AD query failed for {username}: {e}")
            return None

    # def _query_ad(self, username: str) -> Optional[str]:
    #     """AD Query nur für City (Attribut: l). Läuft im Hintergrund-Thread."""
    #     try:
    #         ps_command = f"""
    #         try {{
    #             $user = Get-ADUser '{username}' -Server '{self.domain}' -Properties l -ErrorAction Stop
    #             $city = $user.l
    #             if ($city) {{ $city }} else {{ "Unknown" }}
    #         }} catch {{ "Unknown" }}
    #         """

    #         result = subprocess.run(
    #             ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
    #             capture_output=True,
    #             text=True,
    #             encoding="utf-8",
    #             timeout=3  # kurz halten
    #         )

    #         if result.returncode == 0 and result.stdout:
    #             city = result.stdout.strip()
    #             if city and city not in ("Unknown", ""):
    #                 logger.debug(f"AD: {username} -> {city}")
    #                 return city

    #         logger.debug(f"AD: {username} Unknown or empty")
    #         return None

    #     except subprocess.TimeoutExpired:
    #         logger.warning(f"AD query timeout for {username}")
    #         return None
    #     except Exception as e:
    #         logger.warning(f"AD query failed for {username}: {e}")
    #         return None
        
    def preload_users_async(self, usernames: List[str]) -> None:
        """Legt eine Liste von Usern in die Queue, ohne zu blockieren."""
        for name in usernames:
            uname = name.lower().strip()
            if not uname:
                continue
            with self._lock:
                if uname in self._cache or uname in self._failed_users:
                    continue
            try:
                self._queue.put_nowait(uname)
            except queue.Full:
                # Wenn die Queue voll ist, brechen wir ab, um nicht zu blockieren
                break


class FlexLMExporter:
    """FlexLM Exporter mit AD City Location"""
    def __init__(self, license_server: str, port: int, lmutil_path: str, ad_domain: str = 'patec.group'):
        self.license_server = license_server
        self.port = port
        self.lmutil_path = lmutil_path
        
        # AD Location Lookup
        self.ad_lookup = ADLocationLookup(domain=ad_domain)
        
        # Metrics
        self.setup_metrics()
        
        # Internal
        self._last_users = []
        self._collecting_enabled = False
    
    def setup_metrics(self):
        self.server_up = Gauge('flexlm_server_up', 'Server Status', ['server'])
        self.feature_total = Gauge('flexlm_feature_total_licenses', 'Total Licenses', ['server','vendor','feature'])
        self.feature_used = Gauge('flexlm_feature_used_licenses', 'Used Licenses', ['server','vendor','feature'])
        self.feature_available = Gauge('flexlm_feature_available_licenses', 'Available Licenses', ['server','vendor','feature'])
        self.user_licenses = Gauge('flexlm_user_licenses', 'User License', ['server','vendor','feature','user','hostname','display','location'])
        self.location_licenses = Gauge('flexlm_location_licenses_total', 'Licenses per Location', ['server','location','feature'])
        self.location_users = Gauge('flexlm_location_users_total', 'Users per Location', ['server','location'])
        self.host_licenses = Gauge('flexlm_host_licenses_total', 'Licenses per Host', ['server','hostname','location'])
        self.daemon_up = Gauge('flexlm_daemon_up', 'Daemon Status', ['server','daemon','version'])
        self.scrape_duration = Gauge('flexlm_scrape_duration_seconds', 'Scrape Duration')
        self.scrape_errors = Counter('flexlm_scrape_errors_total', 'Scrape Errors')
    
    def _run_lmstat(self) -> Tuple[str, str, int]:
        cmd = [self.lmutil_path, 'lmstat', '-c', f'{self.port}@{self.license_server}', '-a']
        if not os.path.exists(self.lmutil_path):
            return '', f'lmutil not found: {self.lmutil_path}', -99
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
        daemon_re = re.compile(r'(\w+): UP v([0-9.]+)')
        user_line_re = re.compile(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)', re.IGNORECASE)
        
        for raw in lines:
            line = raw.strip()
            
            if 'license server UP' in line:
                data['server_status'] = True
            
            dm = daemon_re.search(line)
            if dm:
                data['daemons'].append({'name': dm.group(1), 'status': 'UP', 'version': dm.group(2)})
            
            fm = feature_hdr_re.search(raw)
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
            
            if line.startswith('Users of ') and not feature_hdr_re.search(raw):
                in_users_section = False
                current_feature = None
            
            if in_users_section and current_feature:
                um = user_line_re.search(raw)
                if um:
                    username = um.group(1)
                    hostname = um.group(2)
                    display = um.group(3)
                    user_dict = {
                        'username': username,
                        'hostname': hostname,
                        'display': display,
                        'feature': current_feature['name']
                    }
                    current_feature['users'].append(user_dict)
                    data['users'].append(user_dict)
        
        return data
    
    def get_location_for_user(self, username: str) -> str:
        """Holt Location aus AD"""
        return self.ad_lookup.get_location(username)
    
    def collect_metrics(self):
        start = time.time()
        stdout, stderr, rc = self._run_lmstat()
        server_label = f"{self.license_server}:{self.port}"
        
        if rc != 0 or not stdout.strip():
            self.server_up.labels(server=server_label).set(0)
            self.scrape_errors.inc()
            logger.warning(f"lmstat failed: rc={rc}, stderr={stderr}")
            return
        
        data = self.parse_lmstat_output(stdout)
        self.server_up.labels(server=server_label).set(1 if data['server_status'] else 0)
        
        vendor = 'solidworks'
        
        for d in data['daemons']:
            self.daemon_up.labels(server=server_label, daemon=d['name'], version=d['version']).set(1 if d['status']=='UP' else 0)
        
        for feature in data['features']:
            self.feature_total.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['total'])
            self.feature_used.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['used'])
            self.feature_available.labels(server=server_label, vendor=vendor, feature=feature['name']).set(feature['available'])
            
            # Users mit Location (nicht-blockierend, AD im Hintergrund)
            loc_counts = {}
            for u in feature['users']:
                location = self.get_location_for_user(u['username'])

                self.user_licenses.labels(
                    server=server_label,
                    vendor=vendor,
                    feature=feature['name'],
                    user=u['username'],
                    hostname=u['hostname'],
                    display=u['display'],
                    location=location
                ).set(1)

                loc_counts[(location, feature['name'])] = loc_counts.get((location, feature['name']), 0) + 1

            for (loc, feat), cnt in loc_counts.items():
                self.location_licenses.labels(server=server_label, location=loc, feature=feat).set(cnt)
        
        # Host und Location aggregiert
        host_counts = {}
        loc_user_sets = {}
        
        for u in data['users']:
            location = self.get_location_for_user(u['username'])
            hk = (u['hostname'], location)
            host_counts[hk] = host_counts.get(hk, 0) + 1
            loc_user_sets.setdefault(location, set()).add(u['username'])
        
        for (hn, loc), cnt in host_counts.items():
            self.host_licenses.labels(server=server_label, hostname=hn, location=loc).set(cnt)
        
        for loc, users in loc_user_sets.items():
            self.location_users.labels(server=server_label, location=loc).set(len(users))
        
        if data['users']:
            self._last_users = [u['username'] for u in data['users']]
        
        self.scrape_duration.set(time.time() - start)
        logger.info(f"Collected: {len(data['features'])} features, {len(data['users'])} users")
    
    def collect(self):
        """Prometheus Collector Interface"""
        if self._collecting_enabled:
            self.collect_metrics()
        return []
    
    def start_server(self, port: int = 9090):
        """Startet HTTP Server"""
        REGISTRY.register(self)
        start_http_server(port)
        
        logger.info(f"Exporter gestartet auf Port {port}")
        logger.info(f"Server: {self.license_server}:{self.port}")
        logger.info(f"lmutil: {self.lmutil_path}")
        
        def initial_collect():
            time.sleep(2)
            self._collecting_enabled = True
            logger.info("Starte Initial Collect")
            self.collect_metrics()
            logger.info("Initial Collect abgeschlossen")
            
            if self._last_users:
                logger.info(f"Starte AD Preload fuer {len(self._last_users)} Users")
                self.ad_lookup.preload_users_async(self._last_users)
        
        threading.Thread(target=initial_collect, daemon=True).start()
        
        def collect_loop():
            time.sleep(35)
            while True:
                time.sleep(30)
                try:
                    self.collect_metrics()
                except Exception as e:
                    logger.error(f"Collect error: {e}")
        
        threading.Thread(target=collect_loop, daemon=True).start()
        
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Exporter beendet")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='FlexLM Exporter mit AD City Location')
    parser.add_argument('--license-server', default='lic-solidworks-emea.patec.group',
                       help='FlexLM Server Hostname')
    parser.add_argument('--license-port', type=int, default=25734,
                       help='FlexLM Server Port')
    parser.add_argument('--exporter-port', type=int, default=9090,
                       help='Exporter HTTP Port')
    parser.add_argument('--lmutil-path', default=r'C:\Temp\SolidWorks_Exporter\Eyporter\lmutil.exe',
                       help='Pfad zu lmutil.exe')
    parser.add_argument('--ad-domain', default='patec.group',
                       help='Active Directory Domain')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose Logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    exporter = FlexLMExporter(
        license_server=args.license_server,
        port=args.license_port,
        lmutil_path=args.lmutil_path,
        ad_domain=args.ad_domain
    )
    
    exporter.start_server(args.exporter_port)


if __name__ == '__main__':
    main()
