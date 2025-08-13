#!/usr/bin/env python3
"""
Debug-Tool für AD-Integration Probleme
"""

import logging
import sys
import os

# Debug-Logging aktivieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def check_environment():
    """Prüft die Systemumgebung"""
    print("=== Systemumgebung Prüfung ===")
    
    # Windows-Version
    try:
        import platform
        print(f"OS: {platform.system()} {platform.release()}")
        print(f"Computer: {platform.node()}")
    except Exception as e:
        print(f"Platform-Info Fehler: {e}")
    
    # Domain-Informationen
    print(f"USERNAME: {os.environ.get('USERNAME', 'N/A')}")
    print(f"USERDOMAIN: {os.environ.get('USERDOMAIN', 'N/A')}")
    print(f"USERDNSDOMAIN: {os.environ.get('USERDNSDOMAIN', 'N/A')}")
    print(f"COMPUTERNAME: {os.environ.get('COMPUTERNAME', 'N/A')}")
    
    # Prüfe ob in Workgroup oder Domain
    userdomain = os.environ.get('USERDOMAIN', '').upper()
    computername = os.environ.get('COMPUTERNAME', '').upper()
    
    if userdomain == computername or userdomain == 'WORKGROUP':
        print("❌ System ist in WORKGROUP (nicht in Domain)")
        return False
    else:
        print("✅ System scheint in Domain zu sein")
        return True

def check_ad_modules():
    """Prüft AD-Module"""
    print("\n=== AD-Module Prüfung ===")
    
    modules = {
        'win32api': 'pywin32',
        'win32con': 'pywin32', 
        'win32security': 'pywin32',
        'ldap3': 'ldap3'
    }
    
    all_available = True
    for module, package in modules.items():
        try:
            __import__(module)
            print(f"✅ {module} ({package}) verfügbar")
        except ImportError as e:
            print(f"❌ {module} ({package}) nicht verfügbar: {e}")
            all_available = False
    
    return all_available

def test_domain_detection():
    """Testet Domain-Erkennung"""
    print("\n=== Domain-Erkennung Test ===")
    
    try:
        from active_directory_helper import ActiveDirectoryHelper
        
        ad_helper = ActiveDirectoryHelper()
        print(f"Erkannte Domain: {ad_helper.domain}")
        print(f"AD verfügbar: {ad_helper.enabled}")
        
        if ad_helper.enabled:
            print("✅ AD-Helper erfolgreich initialisiert")
        else:
            print("ℹ️  AD-Helper deaktiviert (normal außerhalb von Domains)")
        
        return ad_helper.enabled
        
    except Exception as e:
        print(f"❌ Fehler bei AD-Helper: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_flexlm_with_disabled_ad():
    """Testet FlexLM Exporter mit deaktivierter AD"""
    print("\n=== FlexLM Exporter Test (ohne AD) ===")
    
    try:
        from flexlm_exporter import FlexLMExporter
        
        # Exporter mit deaktivierter AD erstellen
        exporter = FlexLMExporter(
            license_server="test-server",
            port=27000,
            enable_ad=False  # AD explizit deaktivieren
        )
        
        print("✅ FlexLM Exporter ohne AD erfolgreich erstellt")
        print(f"AD aktiviert: {exporter.enable_ad}")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim FlexLM Exporter: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_flexlm_with_ad():
    """Testet FlexLM Exporter mit AD"""
    print("\n=== FlexLM Exporter Test (mit AD) ===")
    
    try:
        from flexlm_exporter import FlexLMExporter
        
        # Exporter mit AD versuchen
        exporter = FlexLMExporter(
            license_server="test-server",
            port=27000,
            enable_ad=True  # AD aktivieren
        )
        
        print(f"✅ FlexLM Exporter erstellt")
        print(f"AD aktiviert: {exporter.enable_ad}")
        
        if exporter.enable_ad:
            print("✅ AD-Integration funktioniert")
        else:
            print("ℹ️  AD-Integration automatisch deaktiviert (normal)")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim FlexLM Exporter mit AD: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Hauptdiagnose-Funktion"""
    print("AD-Integration Diagnose Tool")
    print("=" * 50)
    
    # Schritt 1: Umgebung prüfen
    in_domain = check_environment()
    
    # Schritt 2: Module prüfen
    modules_ok = check_ad_modules()
    
    # Schritt 3: Domain-Erkennung
    ad_works = test_domain_detection()
    
    # Schritt 4: FlexLM ohne AD
    flexlm_no_ad = test_flexlm_with_disabled_ad()
    
    # Schritt 5: FlexLM mit AD
    flexlm_with_ad = test_flexlm_with_ad()
    
    # Zusammenfassung
    print("\n" + "=" * 50)
    print("DIAGNOSE ZUSAMMENFASSUNG")
    print("=" * 50)
    
    print(f"✅ In Windows-Domain: {'Ja' if in_domain else 'Nein'}")
    print(f"✅ AD-Module verfügbar: {'Ja' if modules_ok else 'Nein'}")
    print(f"✅ AD-Erkennung funktioniert: {'Ja' if ad_works else 'Nein'}")
    print(f"✅ FlexLM ohne AD: {'Ja' if flexlm_no_ad else 'Nein'}")
    print(f"✅ FlexLM mit AD: {'Ja' if flexlm_with_ad else 'Nein'}")
    
    if not in_domain:
        print("\n🔧 EMPFEHLUNG:")
        print("   Verwenden Sie --disable-ad um AD-Integration zu deaktivieren")
        print("   python flexlm_exporter.py --disable-ad")
    
    if modules_ok and flexlm_no_ad and flexlm_with_ad:
        print("\n🎉 ALLES FUNKTIONIERT!")
        print("   Der Exporter läuft korrekt mit und ohne AD")
    
    if not modules_ok:
        print("\n❌ MODULE FEHLEN:")
        print("   pip install pywin32 ldap3")

if __name__ == '__main__':
    main()
