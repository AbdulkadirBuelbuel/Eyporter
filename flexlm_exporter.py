#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus
Mit AD City Location Lookup via optimiertem PowerShell
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
import json
import signal
import yaml 
import sys

if sys.platform == 'win32':
    try:
        import io
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ADLocationLookup:
    """AD City Lookup via optimiertem PowerShell (mit CREATE_NEW_PROCESS_GROUP + Force-Kill)"""
    
    def __init__(self, domain: str = 'patec.group', cache_file: str = 'ad_cache.json', 
                 failed_retry_hours: int = 0.2):  
        self.domain = domain
        self.cache_file = cache_file
        self.failed_retry_seconds = failed_retry_hours * 3600 
        self._cache: Dict[str, str] = {}
        self._failed_users: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=2000)
        self._stop_event = threading.Event()
        
        self._load_cache()

        self._workers = []
        for i in range(3): 
            worker = threading.Thread(target=self._worker_loop, name=f"ADWorker-{i}", daemon=True)
            worker.start()
            self._workers.append(worker)
        
        logger.info(f"AD Location Lookup mit optimiertem PowerShell gestartet (Domain: {domain}, {len(self._workers)} Workers)")

    def stop(self):
        """Optional beim Shutdown aufrufen."""
        logger.info("AD Lookup wird beendet...")
        self._stop_event.set()
        
        for _ in range(len(self._workers)):
            try:
                self._queue.put_nowait("__STOP__")
            except queue.Full:
                pass
        
        for i, worker in enumerate(self._workers):
            if worker.is_alive():
                logger.info(f"Warte auf Worker-{i}...")
                worker.join(timeout=2)
                if worker.is_alive():
                    logger.warning(f"Worker-{i} antwortet nicht")
        
        try:
            self._save_cache()
            logger.info("Cache gespeichert")
        except Exception as e:
            logger.error(f"Cache speichern fehlgeschlagen: {e}")

    def _load_cache(self):
        """Cache aus Datei laden"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    cache_data = data.get('cache', {})
                    if cache_data:
                        if isinstance(list(cache_data.values())[0], list):
                            self._cache = {k: v[0] for k, v in cache_data.items()}
                            logger.info(f"Cache konvertiert: {len(self._cache)} User (Tupel -> String)")
                        else:
                            self._cache = cache_data
                            logger.info(f"Cache geladen: {len(self._cache)} User")
                    
                    failed_data = data.get('failed_users', [])
                    if isinstance(failed_data, list):
                        now = time.time()
                        self._failed_users = {user: now for user in failed_data}
                    elif isinstance(failed_data, dict):
                        self._failed_users = failed_data
                    
            except Exception as e:
                logger.warning(f"Cache laden fehlgeschlagen: {e}")

    def _save_cache(self):
        """Cache in Datei speichern"""
        try:
            with self._lock:
                data = {
                    'cache': dict(self._cache),
                    'failed_users': dict(self._failed_users),
                    'timestamp': time.time()
                }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Cache speichern fehlgeschlagen: {e}")

    def get_location(self, username: str) -> str:
        """
        Nicht-blockierender Lookup OHNE Cache-TTL:
        - Cache wird NIE geleert (permanent)
        - Nur Failed Users haben TTL und werden nach Zeit wieder versucht
        - Neue User werden im Hintergrund abgefragt
        """
        username_clean = username.split("\\")[-1].split("@")[0]
        username_lower = username_clean.lower().strip()
        if not username_lower:
            return "Unknown"

        now = time.time()

        with self._lock:
            if username_lower in self._cache:
                return self._cache[username_lower]
            
            if username_lower in self._failed_users:
                failed_time = self._failed_users[username_lower]
                time_since_failed = now - failed_time
                
                if time_since_failed < self.failed_retry_seconds:
                    return "Unknown"
                else:
                    logger.debug(f"Failed User '{username_lower}' wird nach {time_since_failed/3600:.1f}h wieder versucht")
                    del self._failed_users[username_lower]

        try:
            self._queue.put_nowait(username_lower)
        except queue.Full:
            pass

        return "Unknown"

    def _worker_loop(self):
        """Hintergrundthread, der User aus der Queue abarbeitet und Cache füllt."""
        worker_id = threading.current_thread().name
        logger.info(f"{worker_id} gestartet")
        
        while not self._stop_event.is_set():
            try:
                try:
                    username = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if username == "__STOP__":
                    logger.info(f"{worker_id}: Stop Signal erhalten")
                    break

                now = time.time()
                with self._lock:
                    if username in self._cache:
                        self._queue.task_done()
                        continue
                    
                    if username in self._failed_users:
                        failed_time = self._failed_users[username]
                        if now - failed_time < self.failed_retry_seconds:
                            self._queue.task_done()
                            continue
                        else:
                            del self._failed_users[username]

                logger.debug(f"{worker_id}: Verarbeite '{username}'")
                
                try:
                    location = self._query_ad_powershell(username)
                except Exception as e:
                    logger.error(f"{worker_id}: Unerwarteter Fehler bei '{username}': {e}")
                    location = None

                with self._lock:
                    if location and location != "Unknown":
                        self._cache[username] = location
                        self._failed_users.pop(username, None)
                        cache_size = len(self._cache)
                        logger.info(f"{worker_id}: '{username}' -> '{location}' erfolgreich (Cache: {cache_size} User)")
                    else:
                        self._failed_users[username] = now
                        failed_count = len(self._failed_users)
                        logger.info(f"{worker_id}: '{username}' als failed markiert (Failed: {failed_count} User)")

                self._queue.task_done()
                
            except Exception as e:
                logger.error(f"{worker_id}: Kritischer Fehler in Worker-Loop: {e}")
                
        logger.info(f"{worker_id} beendet")

    def _query_ad_powershell(self, username: str) -> Optional[str]:
        """Fallback: PowerShell AD-Abfrage"""
        process = None
        try:
            ps_command = f"""
            try {{
                $user = Get-ADUser '{username}' -Server '{self.domain}' -Properties City -ErrorAction Stop
                $city = $user.City
                if ($city) {{ $city }} else {{ "Unknown" }}
            }} catch {{ "Unknown" }}
            """

            process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NoLogo", "-NonInteractive", 
                 "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning(f"PowerShell timeout für '{username}' - Force-Kill")
                try:
                    # Force-Kill mit taskkill für gesamten Process-Tree
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                        capture_output=True,
                        timeout=1
                    )
                except:
                    pass
                process.kill()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                return None

            if process.returncode != 0:
                return None

            stdout = (stdout or "").strip()
            if not stdout or stdout == "Unknown":
                return None

            logger.debug(f"PowerShell: '{username}' -> '{stdout}'")
            return stdout.strip()

        except Exception as e:
            logger.warning(f"PowerShell Fehler für '{username}': {e}")
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=1)
                except:
                    pass
            return None
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=0.5)
                except:
                    try:
                        process.kill()
                    except:
                        pass

    def log_cache_stats(self):
        """Loggt aktuelle Cache-Statistiken"""
        with self._lock:
            total_users = len(self._cache)
            failed_users = len(self._failed_users)
            
            logger.info(f"CACHE STATS: {total_users} User permanent gecacht, {failed_users} failed [PowerShell]")

    def preload_users_async(self, usernames: List[str]) -> None:
        """Legt eine Liste von Usern in die Queue, ohne zu blockieren."""
        now = time.time()
        for name in usernames:
            uname = name.lower().strip()
            if not uname:
                continue
            with self._lock:
                if uname in self._cache:
                    continue
                
                if uname in self._failed_users:
                    failed_time = self._failed_users[uname]
                    if now - failed_time < self.failed_retry_seconds:
                        continue
                    else:
                        del self._failed_users[uname]
                        
            try:
                self._queue.put_nowait(uname)
            except queue.Full:
                break


class FlexLMExporter:
    """FlexLM Exporter mit AD City Location via PowerShell"""
    def __init__(self, name: str, host: str, port: int, lmutil_path: str, vendor: str, ad_lookup: ADLocationLookup, metrics: dict = None):
        self.name = name
        self.host = host  
        self.port = port
        self.lmutil_path = lmutil_path
        self.vendor = vendor
        self.ad_lookup = ad_lookup
        self.server_label = f"{host}:{port}"
        
        if metrics:
            self.server_up = metrics['server_up']
            self.feature_total = metrics['feature_total']
            self.feature_used = metrics['feature_used']
            self.feature_available = metrics['feature_available']
            self.user_licenses = metrics['user_licenses']
            self.location_licenses = metrics['location_licenses']
            self.location_users = metrics['location_users']
            self.daemon_up = metrics['daemon_up']
            self.scrape_duration = metrics['scrape_duration']
            self.scrape_errors = metrics['scrape_errors']
        else:
            self.server_up = Gauge('flexlm_server_up', 'Server Status', ['server', 'server_name'])
            self.feature_total = Gauge('flexlm_feature_total_licenses', 'Total Licenses', ['server','server_name','vendor','feature'])
            self.feature_used = Gauge('flexlm_feature_used_licenses', 'Used Licenses', ['server','server_name','vendor','feature'])
            self.feature_available = Gauge('flexlm_feature_available_licenses', 'Available Licenses', ['server','server_name','vendor','feature'])
            self.user_licenses = Gauge('flexlm_user_licenses', 'User License Start Time (Unix Timestamp)', ['server','server_name','vendor','feature','user','hostname','display','location'])
            self.location_licenses = Gauge('flexlm_location_licenses_total', 'Licenses per Location', ['server','server_name','location','feature'])
            self.location_users = Gauge('flexlm_location_users_total', 'Users per Location', ['server','server_name','location'])
            self.daemon_up = Gauge('flexlm_daemon_up', 'Daemon Status', ['server','server_name','daemon','version'])
            self.scrape_duration = Gauge('flexlm_scrape_duration_seconds', 'Scrape Duration', ['server','server_name'])
            self.scrape_errors = Counter('flexlm_scrape_errors_total', 'Scrape Errors', ['server','server_name'])

        logger.info(f"FlexLM Server initialisiert: {self.name} ({self.server_label}) [PowerShell]")
    
    def _run_lmstat(self) -> Tuple[str, str, int]:
        cmd = [self.lmutil_path, 'lmstat', '-c', f'{self.port}@{self.host}', '-a']
        if not os.path.exists(self.lmutil_path):
            return '', f'lmutil not found: {self.lmutil_path}', -99
        
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            try:
                stdout, stderr = process.communicate(timeout=30)
                return stdout or '', stderr or '', process.returncode
            except subprocess.TimeoutExpired:
                logger.warning(f"lmstat timeout für {self.name} - Force-Kill")
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                        capture_output=True,
                        timeout=2
                    )
                except:
                    pass
                process.kill()
                process.wait()
                return '', 'timeout', -2
                
        except Exception as e:
            if process and process.poll() is None:
                try:
                    process.kill()
                except:
                    pass
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
                        'feature': current_feature['name'],
                        'start_time': time.time()  # Simplified
                    }
                    current_feature['users'].append(user_dict)
                    data['users'].append(user_dict)
        
        return data

    def collect_metrics(self):
        start = time.time()
        stdout, stderr, rc = self._run_lmstat()
        
        if rc != 0 or not stdout.strip():
            self.server_up.labels(server=self.server_label, server_name=self.name).set(0)
            self.scrape_errors.labels(server=self.server_label, server_name=self.name).inc()
            logger.warning(f"lmstat failed for {self.name}: rc={rc}, stderr={stderr}")
            return []
        
        data = self.parse_lmstat_output(stdout)
        self.server_up.labels(server=self.server_label, server_name=self.name).set(1 if data['server_status'] else 0)
        
        for d in data['daemons']:
            self.daemon_up.labels(server=self.server_label, server_name=self.name, daemon=d['name'], version=d['version']).set(1 if d['status']=='UP' else 0)
        
        for feature in data['features']:
            self.feature_total.labels(server=self.server_label, server_name=self.name, vendor=self.vendor, feature=feature['name']).set(feature['total'])
            self.feature_used.labels(server=self.server_label, server_name=self.name, vendor=self.vendor, feature=feature['name']).set(feature['used'])
            self.feature_available.labels(server=self.server_label, server_name=self.name, vendor=self.vendor, feature=feature['name']).set(feature['available'])
            
            loc_counts = {}
            for u in feature['users']:
                location = self.ad_lookup.get_location(u['username'])
                start_time = u.get('start_time', 0)

                self.user_licenses.labels(
                    server=self.server_label,
                    server_name=self.name,
                    vendor=self.vendor,
                    feature=feature['name'],
                    user=u['username'],
                    hostname=u['hostname'],
                    display=u['display'],
                    location=location
                ).set(start_time)

                loc_counts[(location, feature['name'])] = loc_counts.get((location, feature['name']), 0) + 1

            for (loc, feat), cnt in loc_counts.items():
                self.location_licenses.labels(server=self.server_label, server_name=self.name, location=loc, feature=feat).set(cnt)

        loc_user_sets = {}
        
        for u in data['users']:
            location = self.ad_lookup.get_location(u['username'])
            loc_user_sets.setdefault(location, set()).add(u['username'])
        
        for loc, users in loc_user_sets.items():
            self.location_users.labels(server=self.server_label, server_name=self.name, location=loc).set(len(users))
        
        self.scrape_duration.labels(server=self.server_label, server_name=self.name).set(time.time() - start)
        logger.info(f"Collected {self.name}: {len(data['features'])} features, {len(data['users'])} users")
        
        return data['users']

    
class MultiFlexLMExporter:
    """Multi-Server FlexLM Exporter mit PowerShell"""
    def __init__(self, config_file: str = 'servers.yml'):
        self.config_file = config_file
        self.config = self._load_config()
        
        ad_domain = self.config.get('ad_domain', 'patec.group')
        cache_file = self.config.get('cache_file', 'ad_cache.json')
        self.ad_lookup = ADLocationLookup(domain=ad_domain, cache_file=cache_file)
        
        self.metrics = {
            'server_up': Gauge('flexlm_server_up', 'Server Status', ['server', 'server_name']),
            'feature_total': Gauge('flexlm_feature_total_licenses', 'Total Licenses', ['server','server_name','vendor','feature']),
            'feature_used': Gauge('flexlm_feature_used_licenses', 'Used Licenses', ['server','server_name','vendor','feature']),
            'feature_available': Gauge('flexlm_feature_available_licenses', 'Available Licenses', ['server','server_name','vendor','feature']),
            'user_licenses': Gauge('flexlm_user_licenses', 'User License Start Time (Unix Timestamp)', ['server','server_name','vendor','feature','user','hostname','display','location']),
            'location_licenses': Gauge('flexlm_location_licenses_total', 'Licenses per Location', ['server','server_name','location','feature']),
            'location_users': Gauge('flexlm_location_users_total', 'Users per Location', ['server','server_name','location']),
            'daemon_up': Gauge('flexlm_daemon_up', 'Daemon Status', ['server','server_name','daemon','version']),
            'scrape_duration': Gauge('flexlm_scrape_duration_seconds', 'Scrape Duration', ['server','server_name']),
            'scrape_errors': Counter('flexlm_scrape_errors_total', 'Scrape Errors', ['server','server_name'])
        }
        
        self.servers: List[FlexLMExporter] = []
        for server_config in self.config.get('servers', []):
            server = FlexLMExporter(
                name=server_config['name'],
                host=server_config['host'], 
                port=server_config['port'],
                lmutil_path=server_config['lmutil_path'],
                vendor=server_config['vendor'],
                ad_lookup=self.ad_lookup,
                metrics=self.metrics
            )
            self.servers.append(server)
        
        logger.info(f"Multi-FlexLM Exporter initialisiert mit {len(self.servers)} Servern [PowerShell]")
        
        self._collecting_enabled = False

    def _load_config(self) -> dict:
        """Lade Konfiguration aus YAML-Datei"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Konfiguration geladen: {self.config_file}")
        return config

    def collect_metrics(self):
        """Sammle Metrics von allen Servern - PARALLEL statt sequentiell"""
        all_users = []
        results = {}
        
        def collect_one(server):
            try:
                return server.name, server.collect_metrics()
            except Exception as e:
                logger.error(f"Fehler beim Sammeln von {server.name}: {e}")
                return server.name, []
        
        # Starte alle Server parallel
        threads = []
        for server in self.servers:
            t = threading.Thread(target=lambda s=server: results.update([collect_one(s)]), daemon=True)
            t.start()
            threads.append(t)
        
        # Warte max 45 Sekunden auf alle Threads
        for t in threads:
            t.join(timeout=45)
            if t.is_alive():
                logger.warning(f"Thread noch aktiv nach 45s timeout")
        
        # Sammle alle User
        for users in results.values():
            if users:
                all_users.extend([u['username'] for u in users])
        
        return all_users

    def collect(self):
        """Prometheus Collector Interface"""
        if self._collecting_enabled:
            self.collect_metrics()
        return []

    def start_server(self, port: int = 9090):
        """Startet HTTP Server"""
        REGISTRY.register(self)
        start_http_server(port)
        
        logger.info(f"Multi-FlexLM Exporter gestartet auf Port {port} [PowerShell]")
        for server in self.servers:
            logger.info(f"  - {server.name}: {server.host}:{server.port} ({server.vendor})")
        
        def signal_handler(signum, frame):
            logger.info(f"Signal {signum} erhalten, beende Exporter...")
            try:
                self.ad_lookup.stop()
            except Exception as e:
                logger.error(f"Fehler beim Beenden: {e}")
            import sys
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        def initial_collect():
            time.sleep(2)
            self._collecting_enabled = True
            logger.info("Starte Initial Collect für alle Server")
            try:
                all_users = self.collect_metrics()
                logger.info("Initial Collect abgeschlossen")
                
                if all_users:
                    unique_users = list(set(all_users))
                    logger.info(f"Starte AD Preload für {len(unique_users)} eindeutige Users")
                    self.ad_lookup.preload_users_async(unique_users)
            except Exception as e:
                logger.error(f"Initial Collect Fehler: {e}")
        
        threading.Thread(target=initial_collect, daemon=True).start()
        
        def collect_loop():
            time.sleep(35)
            while True:
                try:
                    time.sleep(60)  # 60s statt 30s
                    self.collect_metrics()
                    
                    if int(time.time()) % 600 < 60:
                        self.ad_lookup.log_cache_stats()
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Collect error: {e}")
        
        threading.Thread(target=collect_loop, daemon=True).start()
        
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Exporter beendet")
            try:
                self.ad_lookup.stop()
            except Exception:
                pass


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-FlexLM Exporter mit PowerShell AD Location Lookup')
    parser.add_argument('--config', default='servers.yml',
                       help='YAML Konfigurationsdatei')
    parser.add_argument('--exporter-port', type=int, default=9090,
                       help='Exporter HTTP Port')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose Logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("="*60)
    logger.info("FlexLM Exporter mit optimiertem PowerShell AD Lookup")
    logger.info("CREATE_NEW_PROCESS_GROUP + Force-Kill + Cache")
    logger.info("="*60)
    
    exporter = MultiFlexLMExporter(config_file=args.config)
    exporter.start_server(args.exporter_port)


if __name__ == '__main__':
    main()
