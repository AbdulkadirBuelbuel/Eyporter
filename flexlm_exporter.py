#!/usr/bin/env python3
"""
FlexLM License Server Exporter for Prometheus
Mit AD City Location Lookup via optimiertem PowerShell (Batch-Abfragen)
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


def _kill_process_tree(process):
    """Force-kill einen Subprocess und seinen gesamten Process-Tree."""
    if process is None:
        return
    try:
        if process.poll() is not None:
            return
        try:
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=2)
        except Exception:
            pass
    except Exception:
        pass


class ADLocationLookup:
    """AD City Lookup via PowerShell mit Batch-Abfragen.
    
    Statt pro User einen eigenen PowerShell-Prozess zu starten (teuer: 1-3s Startup),
    werden bis zu BATCH_SIZE User in einem einzigen PowerShell-Aufruf abgefragt.
    Ein Semaphore begrenzt die max. gleichzeitigen PowerShell-Prozesse.
    """
    
    BATCH_SIZE = 10           # Max User pro PowerShell-Aufruf
    PS_TIMEOUT_BASE = 8       # Basis-Timeout in Sekunden (PowerShell Startup)
    PS_TIMEOUT_PER_USER = 1.5 # Zusätzlich pro User im Batch
    MAX_CONCURRENT_PS = 2     # Max gleichzeitige PowerShell-Prozesse
    TIMEOUT_RETRY_SECS = 300  # Timeout-User nach 5 Min erneut versuchen
    
    def __init__(self, domain: str = 'patec.group', cache_file: str = 'ad_cache.json', 
                 failed_retry_hours: float = 1.0):  # 1 Stunde statt vorher 12 Minuten
        self.domain = domain
        self.cache_file = cache_file
        self.failed_retry_seconds = failed_retry_hours * 3600 
        self._cache: Dict[str, str] = {}
        self._failed_users: Dict[str, float] = {}  # username -> timestamp
        self._processing: set = set()  # Verhindert doppelte Verarbeitung
        self._lock = threading.Lock()
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=4000)
        self._stop_event = threading.Event()
        self._work_available = threading.Event()  # Signalisiert Worker: Arbeit verfügbar
        self._last_save = time.time()
        self._ps_semaphore = threading.Semaphore(self.MAX_CONCURRENT_PS)
        
        self._load_cache()

        self._workers = []
        for i in range(3): 
            worker = threading.Thread(target=self._worker_loop, name=f"ADWorker-{i}", daemon=True)
            worker.start()
            self._workers.append(worker)
        
        logger.info(f"AD Location Lookup gestartet (Domain: {domain}, Batch={self.BATCH_SIZE}, "
                     f"Timeout={self.PS_TIMEOUT_BASE}+{self.PS_TIMEOUT_PER_USER}/User, "
                     f"MaxPS={self.MAX_CONCURRENT_PS}, {len(self._workers)} Workers)")

    def stop(self):
        """Beim Shutdown aufrufen."""
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
                worker.join(timeout=3)
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
                        first_val = next(iter(cache_data.values()))
                        if isinstance(first_val, list):
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
        """Cache in Datei speichern (direkt, ohne os.replace wegen WinError 32)"""
        try:
            with self._lock:
                data = {
                    'cache': dict(self._cache),
                    'failed_users': dict(self._failed_users),
                    'timestamp': time.time()
                }
            
            # Direkt schreiben statt os.replace (vermeidet WinError 32)
            for attempt in range(3):
                try:
                    with open(self.cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    return  # Erfolg
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        raise
                
        except Exception as e:
            logger.warning(f"Cache speichern fehlgeschlagen: {e}")

    def get_location(self, username: str) -> str:
        """
        Nicht-blockierender Lookup:
        - Cache wird permanent gehalten (kein TTL für erfolgreiche Lookups)
        - Failed Users haben TTL und werden nach Ablauf erneut versucht
        - Neue User werden im Hintergrund per Batch abgefragt
        """
        username_clean = username.split("\\")[-1].split("@")[0]
        username_lower = username_clean.lower().strip()
        if not username_lower:
            return "Unknown"

        now = time.time()

        with self._lock:
            if username_lower in self._cache:
                return self._cache[username_lower]
            
            # Bereits in Bearbeitung? Nicht nochmal einreihen
            if username_lower in self._processing:
                return "Unknown"
            
            if username_lower in self._failed_users:
                failed_time = self._failed_users[username_lower]
                if now - failed_time < self.failed_retry_seconds:
                    return "Unknown"
                else:
                    logger.debug(f"Failed User '{username_lower}' wird erneut versucht")
                    del self._failed_users[username_lower]
            
            # Markiere als "in Bearbeitung" BEVOR wir in die Queue legen
            self._processing.add(username_lower)

        try:
            self._queue.put_nowait(username_lower)
            self._work_available.set()  # Wecke Worker auf
        except queue.Full:
            with self._lock:
                self._processing.discard(username_lower)

        return "Unknown"

    def _worker_loop(self):
        """Worker-Thread mit Batch-Verarbeitung.
        
        Wartet auf Event statt zu pollen. Wird nur aktiv wenn Arbeit verfügbar ist.
        """
        worker_id = threading.current_thread().name
        logger.info(f"{worker_id} gestartet")
        
        while not self._stop_event.is_set():
            # Warte auf Arbeit (Event) statt zu pollen
            if not self._work_available.wait(timeout=30):  # Max 30s warten
                # Timeout: Queue noch leer oder alle Worker idle
                continue
            
            try:
                # === Batch aus Queue sammeln ===
                batch = []
                try:
                    first = self._queue.get(timeout=0.1)
                    if first == "__STOP__":
                        logger.info(f"{worker_id}: Stop Signal erhalten")
                        break
                    batch.append(first)
                except queue.Empty:
                    # Event war gesetzt aber Queue leer - Event zurücksetzen
                    if self._queue.empty():
                        self._work_available.clear()
                    continue
                
                # Weitere User ohne Blockieren sammeln (bis BATCH_SIZE)
                while len(batch) < self.BATCH_SIZE:
                    try:
                        item = self._queue.get_nowait()
                        if item == "__STOP__":
                            self._queue.put("__STOP__")  # Für andere Worker zurücklegen
                            break
                        batch.append(item)
                    except queue.Empty:
                        break
                
                if not batch:
                    continue
                
                # === Bereits gecachte/failed Users filtern ===
                to_query = []
                now = time.time()
                for uname in batch:
                    skip = False
                    with self._lock:
                        if uname in self._cache:
                            self._processing.discard(uname)
                            skip = True
                        elif uname in self._failed_users:
                            if now - self._failed_users[uname] < self.failed_retry_seconds:
                                self._processing.discard(uname)
                                skip = True
                            else:
                                del self._failed_users[uname]
                    
                    if skip:
                        self._queue.task_done()
                    else:
                        to_query.append(uname)
                
                if not to_query:
                    continue
                
                # === Batch AD-Abfrage ===
                logger.info(f"{worker_id}: Batch-Abfrage für {len(to_query)} User")
                
                try:
                    results = self._query_ad_powershell_batch(to_query)
                except Exception as e:
                    logger.error(f"{worker_id}: Batch-Fehler: {e}")
                    results = {}
                
                # === Ergebnisse verarbeiten ===
                with self._lock:
                    for uname in to_query:
                        result = results.get(uname)
                        
                        if uname in self._cache:
                            # Bereits von anderem Worker gecacht
                            pass
                        elif result and result not in ("ERROR", "NOTFOUND", "TIMEOUT"):
                            # Erfolg: City gefunden
                            self._cache[uname] = result
                            self._failed_users.pop(uname, None)
                            logger.info(f"{worker_id}: '{uname}' -> '{result}' (Cache: {len(self._cache)})")
                        elif result == "TIMEOUT":
                            # Timeout: Retry nach 5 Minuten (nicht volle Stunde)
                            self._failed_users[uname] = now - self.failed_retry_seconds + self.TIMEOUT_RETRY_SECS
                            logger.warning(f"{worker_id}: '{uname}' Timeout (Retry in {self.TIMEOUT_RETRY_SECS}s)")
                        else:
                            # Genuinely failed/not found: volle Retry-Zeit
                            self._failed_users[uname] = now
                            logger.info(f"{worker_id}: '{uname}' failed (Failed: {len(self._failed_users)})")
                        
                        self._processing.discard(uname)
                
                for _ in to_query:
                    self._queue.task_done()
                
                # Periodisch Cache speichern (alle 5 Min)
                if time.time() - self._last_save > 300:
                    self._save_cache()
                    self._last_save = time.time()
                
            except Exception as e:
                logger.error(f"{worker_id}: Kritischer Fehler in Worker-Loop: {e}")
                # Cleanup: batch-User aus _processing entfernen
                with self._lock:
                    for uname in batch:
                        self._processing.discard(uname)
                time.sleep(1)  # Tight-Loop-Prevention bei wiederholten Fehlern
                
        logger.info(f"{worker_id} beendet")

    def _query_ad_powershell_batch(self, usernames: List[str]) -> Dict[str, Optional[str]]:
        """Batch PowerShell AD-Abfrage für mehrere User in EINEM Prozess.
        
        Statt pro User einen eigenen PowerShell-Prozess zu starten (1-3s Overhead),
        werden alle User in einem einzigen Aufruf abgefragt.
        
        Returns dict: {username: city_string | "TIMEOUT" | "ERROR" | "NOTFOUND" | None}
        """
        if not usernames:
            return {}
        
        # PowerShell-Befehl für Batch-Abfrage bauen
        # Single-Quotes in Usernamen escapen ('' in PowerShell)
        safe_users = [u.replace("'", "''") for u in usernames]
        user_list = ",".join(f"'{u}'" for u in safe_users)
        
        ps_command = (
            f"$users = @({user_list})\n"
            f"foreach ($u in $users) {{\n"
            f"    try {{\n"
            f"        $adUser = Get-ADUser $u -Server '{self.domain}' -Properties City -ErrorAction Stop\n"
            f"        if ($adUser.City) {{\n"
            f"            Write-Output \"$u=$($adUser.City)\"\n"
            f"        }} else {{\n"
            f"            Write-Output \"$u=NOTFOUND\"\n"
            f"        }}\n"
            f"    }} catch {{\n"
            f"        Write-Output \"$u=ERROR\"\n"
            f"    }}\n"
            f"}}\n"
        )
        
        timeout = self.PS_TIMEOUT_BASE + self.PS_TIMEOUT_PER_USER * len(usernames)
        process = None
        username_set = set(usernames)
        
        # Semaphore: Warte max timeout Sekunden auf freien Slot
        if not self._ps_semaphore.acquire(timeout=timeout):
            logger.warning(f"PowerShell Semaphore timeout ({timeout}s) - alle {self.MAX_CONCURRENT_PS} Slots belegt")
            return {u: "TIMEOUT" for u in usernames}
        
        try:
            process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NoLogo", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning(f"PowerShell Batch timeout ({timeout:.0f}s) für {len(usernames)} User - Force-Kill")
                _kill_process_tree(process)
                process = None  # Bereits gekillt
                return {u: "TIMEOUT" for u in usernames}
            
            if process.returncode != 0:
                logger.warning(f"PowerShell Batch rc={process.returncode}, "
                               f"stderr={stderr[:200] if stderr else 'none'}")
            
            # Ausgabe parsen: "username=CityName" oder "username=ERROR/NOTFOUND"
            results = {}
            for line in (stdout or "").splitlines():
                line = line.strip()
                if '=' not in line:
                    continue
                parts = line.split('=', 1)
                if len(parts) != 2:
                    continue
                user_key = parts[0].strip().lower()
                value = parts[1].strip()
                
                if user_key in username_set:
                    results[user_key] = value if value and value not in ("", "Unknown") else "NOTFOUND"
            
            return results
            
        except Exception as e:
            logger.warning(f"PowerShell Batch Fehler: {e}")
            _kill_process_tree(process)
            process = None
            return {u: "ERROR" for u in usernames}
        finally:
            self._ps_semaphore.release()
            if process and process.poll() is None:
                _kill_process_tree(process)

    def log_cache_stats(self):
        """Loggt aktuelle Cache-Statistiken"""
        with self._lock:
            total_users = len(self._cache)
            failed_users = len(self._failed_users)
            processing = len(self._processing)
            queue_size = self._queue.qsize()
            
            logger.info(f"CACHE STATS: {total_users} gecacht, {failed_users} failed, "
                         f"{processing} in Bearbeitung, {queue_size} in Queue")

    def preload_users_async(self, usernames: List[str]) -> None:
        """Legt eine Liste von Usern in die Queue, ohne zu blockieren."""
        now = time.time()
        queued = 0
        for name in usernames:
            uname = name.lower().strip()
            if not uname:
                continue
            with self._lock:
                if uname in self._cache:
                    continue
                if uname in self._processing:
                    continue
                if uname in self._failed_users:
                    failed_time = self._failed_users[uname]
                    if now - failed_time < self.failed_retry_seconds:
                        continue
                    else:
                        del self._failed_users[uname]
                self._processing.add(uname)
            try:
                self._queue.put_nowait(uname)
                queued += 1
            except queue.Full:
                with self._lock:
                    self._processing.discard(uname)
                break
        if queued > 0:
            self._work_available.set()  # Wecke Worker auf
        logger.info(f"Preload: {queued} User in Queue eingereiht")


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
                _kill_process_tree(process)
                # Pipes nach Kill schließen (verhindert Deadlock)
                try:
                    process.stdout.close()
                    process.stderr.close()
                except Exception:
                    pass
                return '', 'timeout', -2
                
        except Exception as e:
            _kill_process_tree(process)
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
        
        self._collect_lock = threading.Lock()

    def _load_config(self) -> dict:
        """Lade Konfiguration aus YAML-Datei"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Konfiguration geladen: {self.config_file}")
        return config

    def collect_metrics(self):
        """Sammle Metrics von allen Servern - PARALLEL mit TOTAL-Timeout"""
        if not self._collect_lock.acquire(blocking=False):
            logger.warning("Collect bereits aktiv, überspringe")
            return []
        
        try:
            collect_start = time.time()
            logger.info("Starte Metrics Collection...")
            all_users = []
            results = {}
            results_lock = threading.Lock()
            
            def collect_one(server):
                try:
                    name = server.name
                    users = server.collect_metrics()
                    with results_lock:
                        results[name] = users
                except Exception as e:
                    logger.error(f"Fehler beim Sammeln von {server.name}: {e}")
                    with results_lock:
                        results[server.name] = []
            
            # Starte alle Server parallel
            threads = []
            for server in self.servers:
                t = threading.Thread(target=collect_one, args=(server,), name=f"Collect-{server.name}", daemon=True)
                t.start()
                threads.append((t, server.name))
            
            # TOTAL-Timeout: Max 60s für ALLE Server zusammen (nicht pro Thread!)
            total_deadline = time.time() + 60
            for t, name in threads:
                remaining = max(0, total_deadline - time.time())
                if remaining <= 0:
                    logger.warning(f"Total-Timeout! Server '{name}' übersprungen")
                    continue
                t.join(timeout=remaining)
                if t.is_alive():
                    logger.warning(f"Server '{name}' noch aktiv nach {time.time() - collect_start:.0f}s")
            
            # Sammle alle User
            for users in results.values():
                if users:
                    all_users.extend([u['username'] for u in users])
            
            duration = time.time() - collect_start
            logger.info(f"Collection fertig: {len(all_users)} User von {len(results)}/{len(self.servers)} Servern in {duration:.1f}s")
            return all_users
        finally:
            self._collect_lock.release()

    def collect(self):
        """Prometheus Collector Interface - NICHT collect_metrics aufrufen!
        Gauge-Werte werden im Hintergrund-Thread aktualisiert.
        Prometheus liest einfach die aktuellen Werte."""
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
            time.sleep(3)
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
            time.sleep(40)
            save_counter = 0
            while not self.ad_lookup._stop_event.is_set():
                try:
                    # Interruptible sleep (statt time.sleep(60))
                    if self.ad_lookup._stop_event.wait(timeout=60):
                        break
                    
                    logger.info("Heartbeat: collect_loop startet nächste Runde")
                    self.collect_metrics()
                    
                    save_counter += 1
                    if save_counter % 5 == 0:  # Alle 5 Min
                        self.ad_lookup.log_cache_stats()
                        self.ad_lookup._save_cache()
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Collect error: {e}")
            logger.info("Collect Loop beendet")
        
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
