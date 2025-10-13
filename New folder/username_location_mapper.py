#!/usr/bin/env python3
"""
Username-basiertes Location Mapping für FlexLM Exporter
Extrahiert Standort-Informationen aus Benutzernamen basierend auf dem Kürzel
nach der letzten Zahl im Benutzernamen. Codes können alphanumerisch sein (z. B. "hz2").
"""

import json
import logging
import re
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class UserLocationInfo:
    """Benutzerinformationen mit Standort"""
    username: str
    location: str = "Unknown"
    location_code: str = ""
    
class UsernameLocationMapper:
    """Helper-Klasse für Username-basiertes Location Mapping"""
    
    def __init__(self, mapping_file: str = "mapping.json"):
        self.mapping_file = mapping_file
        self.location_mapping = {}
        self.load_mapping()
    
    def load_mapping(self):
        """Lädt das Location Mapping aus der JSON-Datei.
        - Normalisiert Keys auf lowercase (case-insensitive Codes)
        - Toleriert optionale // Kommentarzeilen
        """
        def _normalize_keys(d: Dict[str, str]) -> Dict[str, str]:
            try:
                return {str(k).lower(): v for k, v in d.items()}
            except Exception:
                return {}

        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    # Fallback: entferne // Kommentare und parse erneut
                    f.seek(0)
                    raw = f.read()
                    # Entferne BOM
                    raw = raw.lstrip('\ufeff')
                    # Entferne Zeilen, die mit // beginnen
                    cleaned_lines = []
                    for line in raw.splitlines():
                        line_stripped = line.lstrip()
                        if line_stripped.startswith('//'):
                            continue
                        cleaned_lines.append(line)
                    cleaned = "\n".join(cleaned_lines)
                    data = json.loads(cleaned)

                mapping = data.get('location_mapping', {}) if isinstance(data, dict) else {}
                self.location_mapping = _normalize_keys(mapping)
                logger.info(f"Location Mapping geladen: {len(self.location_mapping)} Standorte")
        except FileNotFoundError:
            logger.warning(f"Mapping-Datei {self.mapping_file} nicht gefunden. Verwende leeres Mapping.")
            self.location_mapping = {}
        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der Mapping-Datei: {e}")
            self.location_mapping = {}
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Laden der Mapping-Datei: {e}")
            self.location_mapping = {}
    
    def extract_location_code_from_username(self, username: str) -> str:
        """
        Extrahiert das Standort-Kürzel aus dem Benutzernamen.
        Regel: Nach der letzten zusammenhängenden Zahl im Benutzernamen folgen das Standort-Kürzel
        als alphanumerische Zeichen bis zum Stringende.
        
        Beispiele:
        - bla99bng -> "bng"
        - user123fra -> "fra" 
        - test42muc -> "muc"
        - admin1 -> "" (keine Zeichen nach der Zahl)
        - user77hz2 -> "hz2" (alphanumerisch)
        """
        if not username:
            return ""
        u = username.strip()
        # Regex: letzte Ziffern gefolgt von alphanumerischem Code bis zum Ende
        # (\d+)([a-zA-Z0-9]+)$
        match = re.search(r'(\d+)([a-zA-Z0-9]+)$', u)
        if match:
            location_code = match.group(2).lower()
            logger.debug(f"Username '{username}' -> Location-Code: '{location_code}'")
            return location_code
        logger.debug(f"Username '{username}' -> Kein Location-Code gefunden")
        return ""
    
    def get_location_from_code(self, location_code: str) -> str:
        """Gibt den vollständigen Standort-Namen für ein Standort-Kürzel zurück."""
        if not location_code:
            return "Unknown"
        location_name = self.location_mapping.get(location_code.lower(), "Unknown")
        logger.debug(f"Location-Code '{location_code}' -> Location: '{location_name}'")
        return location_name
    
    def get_user_location_info(self, username: str) -> UserLocationInfo:
        """Ermittelt Standort-Informationen für einen Benutzer basierend auf dem Benutzernamen."""
        location_code = self.extract_location_code_from_username(username)
        location = self.get_location_from_code(location_code)
        return UserLocationInfo(username=username, location=location, location_code=location_code)
    
    def get_all_locations(self) -> Dict[str, str]:
        """Gibt alle verfügbaren Location-Mappings zurück"""
        return self.location_mapping.copy()
    
    def add_location_mapping(self, code: str, location: str):
        """Fügt ein neues Location-Mapping hinzu (Key wird lowercase gespeichert)."""
        self.location_mapping[str(code).lower()] = location
        logger.info(f"Location-Mapping hinzugefügt: {code} -> {location}")
    
    def save_mapping(self):
        """Speichert das aktuelle Mapping in die JSON-Datei"""
        try:
            data = {"location_mapping": self.location_mapping}
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Mapping erfolgreich gespeichert in {self.mapping_file}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Mappings: {e}")

# Keine eigenständigen Tests/MD erzeugen – Logik nur im Modul
