#!/usr/bin/env python3
"""
Test-Skript für Enhanced Active Directory Integration
Testet alle Authentifizierungsmethoden und Fallback-Szenarien
"""

import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from active_directory_helper import ActiveDirectoryHelper

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ad_integration_test.log')
    ]
)

logger = logging.getLogger(__name__)

def test_domain_detection():
    """Test der automatischen Domain-Erkennung"""
    print("\n" + "="*60)
    print("🔍 TEST: Domain-Erkennung")
    print("="*60)
    
    try:
        domain_env = ActiveDirectoryHelper.detect_domain_environment()
        current_domain = ActiveDirectoryHelper._get_current_domain()
        
        print(f"Domain-Umgebung erkannt: {domain_env}")
        print(f"Aktuelle Domain: {current_domain}")
        
        if domain_env:
            print("✅ System ist in einer Domain-Umgebung")
        else:
            print("ℹ️  System ist in einer Arbeitsgruppen-Umgebung")
            
    except Exception as e:
        print(f"❌ Fehler bei Domain-Erkennung: {e}")

def test_config_file_loading():
    """Test des Ladens der Konfigurationsdatei"""
    print("\n" + "="*60)
    print("📄 TEST: Konfigurationsdatei-Laden")
    print("="*60)
    
    try:
        # Test mit Standard-Konfigurationsdatei
        ad_helper = ActiveDirectoryHelper()
        print("✅ ActiveDirectoryHelper erfolgreich initialisiert")
        print(f"AD Server: {ad_helper.ad_server}")
        print(f"Domain: {ad_helper.domain}")
        print(f"Username: {ad_helper.username}")
        print(f"Cache Timeout: {ad_helper.cache_timeout}")
        print(f"AD aktiviert: {ad_helper.enabled}")
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Konfiguration: {e}")

def test_authentication_methods():
    """Test der verschiedenen Authentifizierungsmethoden"""
    print("\n" + "="*60)
    print("🔐 TEST: Authentifizierungsmethoden")
    print("="*60)
    
    try:
        ad_helper = ActiveDirectoryHelper()
        
        if not ad_helper.enabled:
            print("ℹ️  AD-Integration nicht verfügbar - überspringe Authentifizierungstests")
            return
        
        # Test 1: Windows Integrated Authentication
        print("\n🔹 Test 1: Windows Integrated Authentication")
        try:
            success = ad_helper._try_windows_integrated_auth()
            print(f"Windows Integrated Auth: {'✅ Erfolgreich' if success else '❌ Fehlgeschlagen'}")
        except Exception as e:
            print(f"Windows Integrated Auth: ❌ Fehler - {e}")
        
        # Test 2: Anonymous Bind
        print("\n🔹 Test 2: Anonymous Bind")
        try:
            success = ad_helper._try_anonymous_bind()
            print(f"Anonymous Bind: {'✅ Erfolgreich' if success else '❌ Fehlgeschlagen'}")
        except Exception as e:
            print(f"Anonymous Bind: ❌ Fehler - {e}")
        
        # Test 3: LDAP-Server Suche
        print("\n🔹 Test 3: LDAP-Server automatische Suche")
        try:
            servers = ad_helper._find_domain_controllers()
            print(f"Gefundene Domain Controller: {servers}")
        except Exception as e:
            print(f"LDAP-Server Suche: ❌ Fehler - {e}")
        
    except Exception as e:
        print(f"❌ Fehler bei Authentifizierungstests: {e}")

def test_user_search():
    """Test der Benutzersuche"""
    print("\n" + "="*60)
    print("👥 TEST: Benutzersuche")
    print("="*60)
    
    try:
        ad_helper = ActiveDirectoryHelper()
        
        if not ad_helper.enabled or not ad_helper.is_enabled():
            print("ℹ️  AD-Integration nicht verfügbar - überspringe Benutzersuchtest")
            return
        
        # Test mit dem aktuellen Benutzer
        import getpass
        current_user = getpass.getuser()
        
        print(f"Suche nach Benutzer: {current_user}")
        location = ad_helper.get_user_location(current_user)
        
        if location:
            print(f"✅ Standort gefunden: {location}")
        else:
            print(f"ℹ️  Kein Standort für Benutzer '{current_user}' gefunden")
            
    except Exception as e:
        print(f"❌ Fehler bei Benutzersuche: {e}")

def test_error_handling():
    """Test der Fehlerbehandlung"""
    print("\n" + "="*60)
    print("⚠️  TEST: Fehlerbehandlung")
    print("="*60)
    
    try:
        # Test mit ungültigen Parametern
        print("🔹 Test mit ungültigem Server")
        ad_helper = ActiveDirectoryHelper(ad_server="invalid.server.com")
        print(f"AD Helper erstellt: {ad_helper.enabled}")
        
        print("🔹 Test mit ungültigen Credentials")
        ad_helper2 = ActiveDirectoryHelper(
            username="invalid_user", 
            password="invalid_password"
        )
        print(f"AD Helper mit ungültigen Credentials: {ad_helper2.enabled}")
        
    except Exception as e:
        print(f"Fehlerbehandlungstest: {e}")

def test_cache_functionality():
    """Test der Cache-Funktionalität"""
    print("\n" + "="*60)
    print("🗄️  TEST: Cache-Funktionalität")
    print("="*60)
    
    try:
        ad_helper = ActiveDirectoryHelper()
        
        if not ad_helper.enabled:
            print("ℹ️  AD-Integration nicht verfügbar - überspringe Cache-Test")
            return
        
        import getpass
        current_user = getpass.getuser()
        
        # Ersten Aufruf (Cache füllen)
        import time
        start_time = time.time()
        location1 = ad_helper.get_user_location(current_user)
        first_call_time = time.time() - start_time
        
        # Zweiten Aufruf (aus Cache)
        start_time = time.time()
        location2 = ad_helper.get_user_location(current_user)
        second_call_time = time.time() - start_time
        
        print(f"Erster Aufruf: {first_call_time:.3f}s")
        print(f"Zweiter Aufruf (Cache): {second_call_time:.3f}s")
        print(f"Ergebnisse identisch: {location1 == location2}")
        print(f"Cache-Einträge: {len(ad_helper.user_cache)}")
        
    except Exception as e:
        print(f"❌ Fehler bei Cache-Test: {e}")

def main():
    """Haupttest-Funktion"""
    print("🚀 Enhanced Active Directory Integration - Umfassender Test")
    print("="*80)
    
    # Systeminfo
    print(f"Python Version: {sys.version}")
    print(f"Arbeitsverzeichnis: {os.getcwd()}")
    print(f"Config-Datei vorhanden: {os.path.exists('ad_config.ini')}")
    
    # Tests ausführen
    test_domain_detection()
    test_config_file_loading()
    test_authentication_methods()
    test_user_search()
    test_cache_functionality()
    test_error_handling()
    
    print("\n" + "="*80)
    print("✅ Alle Tests abgeschlossen!")
    print("📋 Prüfen Sie die Logs für Details: ad_integration_test.log")
    print("="*80)

if __name__ == "__main__":
    main()
