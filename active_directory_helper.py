#!/usr/bin/env python3
"""
Active Directory Helper für FlexLM Exporter
Ermittelt Standortinformationen von Benutzern über Active Directory
"""

import os
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

# Active Directory Imports
try:
    import win32api
    import win32con
    import win32security
    from ldap3 import Server, Connection, ALL, SUBTREE, MODIFY_REPLACE
    AD_AVAILABLE = True
except ImportError as e:
    AD_AVAILABLE = False
    print(f"WARNUNG: Active Directory Module nicht verfügbar: {e}")
    print("Standort-Features werden deaktiviert.")

logger = logging.getLogger(__name__)

@dataclass
class UserInfo:
    """Benutzerinformationen aus Active Directory"""
    username: str
    full_name: str = ""
    location: str = ""
    department: str = ""
    office: str = ""
    city: str = ""
    country: str = ""
    
class ActiveDirectoryHelper:
    """Helper-Klasse für Active Directory Abfragen"""
    
    def __init__(self, ad_server: Optional[str] = None, domain: Optional[str] = None, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 location_attributes: Optional[List[str]] = None):
        self.ad_server = ad_server
        self.domain = domain or self._get_current_domain()
        self.username = username
        self.password = password
        self.connection = None
        self.user_cache = {}
        self.cache_timeout = 300  # 5 Minuten Cache
        self.last_cache_update = 0
        self.enabled = AD_AVAILABLE
        
        # Standard Attribute für Standort-Informationen
        self.location_attributes = location_attributes or [
            'l',           # Location/Stadt
            'st',          # State/Bundesland
            'c',           # Country/Land
            'co',          # Country Name
            'physicalDeliveryOfficeName',  # Office
            'streetAddress',  # Straße
            'department',     # Abteilung
            'title',         # Titel
            'company',       # Firma
            'description'    # Beschreibung
        ]
        
        if self.enabled:
            self._initialize_connection()
        else:
            logger.warning("Active Directory nicht verfügbar - Standort-Features deaktiviert")
    
    @staticmethod
    def detect_domain_environment() -> bool:
        """Erkennt automatisch ob das System in einer Windows-Domain ist"""
        try:
            if not AD_AVAILABLE:
                return False
            
            # Methode 1: Prüfe USERDOMAIN vs COMPUTERNAME
            userdomain = os.environ.get('USERDOMAIN', '').upper()
            computername = os.environ.get('COMPUTERNAME', '').upper()
            
            # Wenn USERDOMAIN != COMPUTERNAME und nicht WORKGROUP, dann Domain
            if userdomain and computername and userdomain != computername and userdomain != 'WORKGROUP':
                logger.debug(f"Domain erkannt über USERDOMAIN: {userdomain}")
                return True
            
            # Methode 2: Prüfe USERDNSDOMAIN
            userdnsdomain = os.environ.get('USERDNSDOMAIN', '')
            if userdnsdomain and userdnsdomain.strip():
                logger.debug(f"Domain erkannt über USERDNSDOMAIN: {userdnsdomain}")
                return True
            
            # Methode 3: Prüfe mit win32api
            try:
                import win32api
                import win32con
                domain_info = win32api.GetComputerNameEx(win32con.ComputerNameDnsDomain)
                if domain_info and domain_info.strip() and domain_info.lower() != 'localhost':
                    logger.debug(f"Domain erkannt über win32api: {domain_info}")
                    return True
            except Exception as e:
                logger.debug(f"win32api Domain-Check fehlgeschlagen: {e}")
            
            # Methode 4: Prüfe Registry
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                  r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters") as key:
                    domain, _ = winreg.QueryValueEx(key, "Domain")
                    if domain and domain.strip():
                        logger.debug(f"Domain erkannt über Registry: {domain}")
                        return True
            except Exception as e:
                logger.debug(f"Registry Domain-Check fehlgeschlagen: {e}")
            
            logger.debug("Keine Domain-Umgebung erkannt")
            return False
            
        except Exception as e:
            logger.debug(f"Domain-Erkennung fehlgeschlagen: {e}")
            return False
    
    def _get_current_domain(self) -> str:
        """Ermittelt die aktuelle Domain"""
        try:
            if AD_AVAILABLE:
                # Verschiedene Methoden zum Ermitteln der Domain probieren
                try:
                    domain_info = win32api.GetComputerNameEx(win32con.ComputerNameDnsDomain)
                    if domain_info and domain_info.strip():
                        logger.debug(f"Domain gefunden: {domain_info}")
                        return domain_info.strip()
                except Exception as e:
                    logger.debug(f"GetComputerNameEx fehlgeschlagen: {e}")
                
                # Fallback: Versuche über Umgebungsvariablen
                try:
                    domain = os.environ.get('USERDNSDOMAIN') or os.environ.get('USERDOMAIN')
                    if domain and domain.strip() and domain.upper() != 'WORKGROUP':
                        logger.debug(f"Domain über Umgebungsvariable gefunden: {domain}")
                        return domain.strip()
                except Exception as e:
                    logger.debug(f"Umgebungsvariable-Abfrage fehlgeschlagen: {e}")
                
                # Fallback: Versuche über Registry
                try:
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                      r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters") as key:
                        domain, _ = winreg.QueryValueEx(key, "Domain")
                        if domain and domain.strip():
                            logger.debug(f"Domain über Registry gefunden: {domain}")
                            return domain.strip()
                except Exception as e:
                    logger.debug(f"Registry-Abfrage fehlgeschlagen: {e}")
                    
        except Exception as e:
            logger.debug(f"Allgemeiner Fehler bei Domain-Ermittlung: {e}")
        
        logger.info("Keine Windows-Domain gefunden - verwende localhost")
        return "localhost"
    
    def _initialize_connection(self):
        """Initialisiert die LDAP-Verbindung"""
        if not self.enabled:
            return False
            
        try:
            # Prüfe erst, ob wir überhaupt in einer Domain sind
            if self.domain == "localhost" or not self.domain:
                logger.info("Nicht in einer Windows-Domain - AD-Integration deaktiviert")
                self.enabled = False
                return False
            
            if not self.ad_server:
                # Versuche Domain Controller automatisch zu finden
                self.ad_server = self.domain
            
            logger.debug(f"Versuche AD-Verbindung zu: {self.ad_server}")
            
            # Timeout für Server-Verbindung setzen
            server = Server(self.ad_server, get_info=ALL, connect_timeout=5)
            
            if self.username and self.password:
                # Explizite Anmeldung
                user_dn = f"{self.username}@{self.domain}"
                self.connection = Connection(
                    server, 
                    user=user_dn, 
                    password=self.password, 
                    auto_bind=True,
                    read_only=True,
                    raise_exceptions=False
                )
            else:
                # Versuche mit aktuellen Windows-Credentials
                self.connection = Connection(
                    server, 
                    auto_bind=True, 
                    authentication='NTLM',
                    read_only=True,
                    raise_exceptions=False
                )
            
            # Teste die Verbindung mit einer einfachen Abfrage
            if self.connection and self.connection.bound:
                # Teste mit einer einfachen Abfrage
                test_result = self.connection.search(
                    search_base="",
                    search_filter="(objectClass=*)",
                    search_scope="BASE",
                    size_limit=1
                )
                
                if test_result or not self.connection.last_error:
                    logger.info(f"Active Directory Verbindung erfolgreich: {self.ad_server}")
                    return True
                else:
                    logger.warning(f"AD-Verbindung funktioniert nicht richtig: {self.connection.last_error}")
                    self.enabled = False
                    return False
            else:
                logger.warning("AD-Verbindung konnte nicht aufgebaut werden")
                self.enabled = False
                return False
            
        except Exception as e:
            logger.error(f"Fehler beim Verbinden mit Active Directory: {e}")
            self.enabled = False
            return False
    
    def _search_user(self, username: str) -> Dict:
        """Sucht einen Benutzer im Active Directory"""
        if not self.enabled or not self.connection:
            return {}
        
        try:
            # Verschiedene DN-Basis probieren
            search_bases = [
                f"DC={self.domain.replace('.', ',DC=')}",
                "CN=Users," + f"DC={self.domain.replace('.', ',DC=')}",
                ""  # Root-Suche als Fallback
            ]
            
            # Verschiedene Suchfilter probieren
            search_filters = [
                f"(sAMAccountName={username})",
                f"(userPrincipalName={username}@{self.domain})",
                f"(cn={username})",
                f"(displayName={username})"
            ]
            
            attributes = ['sAMAccountName', 'displayName', 'cn', 'userPrincipalName'] + self.location_attributes
            
            for search_base in search_bases:
                for search_filter in search_filters:
                    try:
                        self.connection.search(
                            search_base=search_base,
                            search_filter=search_filter,
                            search_scope=SUBTREE,
                            attributes=attributes
                        )
                        
                        if self.connection.entries:
                            entry = self.connection.entries[0]
                            logger.debug(f"Benutzer {username} gefunden in {search_base}")
                            return self._extract_user_info(entry)
                            
                    except Exception as e:
                        logger.debug(f"Suche fehlgeschlagen: {search_base} - {search_filter}: {e}")
                        continue
            
            logger.debug(f"Benutzer {username} nicht in AD gefunden")
            return {}
            
        except Exception as e:
            logger.error(f"Fehler bei AD-Suche für {username}: {e}")
            return {}
    
    def _extract_user_info(self, entry) -> Dict:
        """Extrahiert Benutzerinformationen aus einem LDAP-Entry"""
        info = {}
        
        # Standard-Attribute
        info['full_name'] = str(entry.displayName) if entry.displayName else str(entry.cn) if entry.cn else ""
        info['username'] = str(entry.sAMAccountName) if entry.sAMAccountName else ""
        
        # Standort-Attribute extrahieren
        location_parts = []
        
        # Physisches Büro
        if hasattr(entry, 'physicalDeliveryOfficeName') and entry.physicalDeliveryOfficeName:
            info['office'] = str(entry.physicalDeliveryOfficeName)
            location_parts.append(str(entry.physicalDeliveryOfficeName))
        
        # Stadt/Ort
        if hasattr(entry, 'l') and entry.l:
            info['city'] = str(entry.l)
            location_parts.append(str(entry.l))
        
        # Bundesland/State
        if hasattr(entry, 'st') and entry.st:
            info['state'] = str(entry.st)
            location_parts.append(str(entry.st))
        
        # Land
        if hasattr(entry, 'co') and entry.co:
            info['country'] = str(entry.co)
        elif hasattr(entry, 'c') and entry.c:
            info['country'] = str(entry.c)
        
        # Abteilung
        if hasattr(entry, 'department') and entry.department:
            info['department'] = str(entry.department)
        
        # Kombiniere zu einem Standort-String
        if location_parts:
            info['location'] = " - ".join(location_parts)
        elif info.get('country'):
            info['location'] = info['country']
        else:
            info['location'] = "Unknown"
        
        logger.debug(f"User Info: {info}")
        return info
    
    def get_user_location(self, username: str) -> str:
        """Hauptmethode: Ermittelt den Standort eines Benutzers"""
        if not self.enabled:
            return "AD_Disabled"
        
        # Cache prüfen
        current_time = time.time()
        if username in self.user_cache:
            cache_entry = self.user_cache[username]
            if current_time - cache_entry['timestamp'] < self.cache_timeout:
                return cache_entry['location']
        
        # AD-Abfrage
        user_info = self._search_user(username)
        location = user_info.get('location', 'Unknown')
        
        # Cache aktualisieren
        self.user_cache[username] = {
            'location': location,
            'timestamp': current_time,
            'full_info': user_info
        }
        
        return location
    
    def get_user_info(self, username: str) -> UserInfo:
        """Ermittelt vollständige Benutzerinformationen"""
        if not self.enabled:
            return UserInfo(username=username, location="AD_Disabled")
        
        # Cache prüfen
        current_time = time.time()
        if username in self.user_cache:
            cache_entry = self.user_cache[username]
            if current_time - cache_entry['timestamp'] < self.cache_timeout:
                info = cache_entry['full_info']
                return UserInfo(
                    username=username,
                    full_name=info.get('full_name', ''),
                    location=info.get('location', 'Unknown'),
                    department=info.get('department', ''),
                    office=info.get('office', ''),
                    city=info.get('city', ''),
                    country=info.get('country', '')
                )
        
        # AD-Abfrage
        user_info = self._search_user(username)
        
        # Cache aktualisieren
        self.user_cache[username] = {
            'location': user_info.get('location', 'Unknown'),
            'timestamp': current_time,
            'full_info': user_info
        }
        
        return UserInfo(
            username=username,
            full_name=user_info.get('full_name', ''),
            location=user_info.get('location', 'Unknown'),
            department=user_info.get('department', ''),
            office=user_info.get('office', ''),
            city=user_info.get('city', ''),
            country=user_info.get('country', '')
        )
    
    def clear_cache(self):
        """Leert den Benutzer-Cache"""
        self.user_cache.clear()
        logger.info("Benutzer-Cache geleert")
    
    def is_enabled(self) -> bool:
        """Prüft ob AD-Integration verfügbar ist"""
        return self.enabled
