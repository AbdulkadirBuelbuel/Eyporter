#!/usr/bin/env python3
"""
Test für automatische Domain-Erkennung
"""

import logging
import os

# Debug-Logging aktivieren
logging.basicConfig(level=logging.DEBUG)

def test_domain_detection():
    """Testet die automatische Domain-Erkennung"""
    print("=== Automatische Domain-Erkennung Test ===")
    
    # Zeige Umgebungsvariablen
    print("\nSysteminformationen:")
    print(f"USERNAME: {os.environ.get('USERNAME', 'N/A')}")
    print(f"USERDOMAIN: {os.environ.get('USERDOMAIN', 'N/A')}")
    print(f"USERDNSDOMAIN: {os.environ.get('USERDNSDOMAIN', 'N/A')}")
    print(f"COMPUTERNAME: {os.environ.get('COMPUTERNAME', 'N/A')}")
    
    try:
        from active_directory_helper import ActiveDirectoryHelper
        
        # Teste automatische Erkennung
        is_domain = ActiveDirectoryHelper.detect_domain_environment()
        
        print(f"\n🔍 Domain-Erkennung Ergebnis: {'✅ Domain-Umgebung' if is_domain else '❌ Keine Domain'}")
        
        return is_domain
        
    except Exception as e:
        print(f"\n❌ Fehler bei Domain-Erkennung: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_flexlm_auto_ad():
    """Testet FlexLM mit automatischer AD-Erkennung"""
    print("\n=== FlexLM Exporter mit Auto-AD Test ===")
    
    try:
        from flexlm_exporter import FlexLMExporter
        
        # Exporter mit automatischer AD-Erkennung erstellen
        exporter = FlexLMExporter(
            license_server="test-server",
            port=27000,
            lmutil_path="echo",
            # enable_ad nicht gesetzt = automatische Erkennung
        )
        
        print(f"✅ FlexLM Exporter erstellt")
        print(f"🔧 AD automatisch aktiviert: {'✅ Ja' if exporter.enable_ad else '❌ Nein'}")
        
        if exporter.enable_ad:
            print("🎉 In Domain-Umgebung - AD-Integration automatisch aktiviert!")
        else:
            print("ℹ️  Nicht in Domain - AD-Integration automatisch deaktiviert")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim FlexLM Exporter: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_manual_override():
    """Testet manuelle Überschreibung der automatischen Erkennung"""
    print("\n=== Manuelle Überschreibung Test ===")
    
    try:
        from flexlm_exporter import FlexLMExporter
        
        # Test 1: Explizit aktivieren
        print("\n1. Test: --enable-ad (explizit aktivieren)")
        exporter1 = FlexLMExporter(
            license_server="test-server",
            port=27001,  # Anderer Port
            enable_ad=True
        )
        print(f"   AD aktiviert: {'✅ Ja' if exporter1.enable_ad else '❌ Nein'}")
        
        # Test 2: Explizit deaktivieren
        print("\n2. Test: --disable-ad (explizit deaktivieren)")
        exporter2 = FlexLMExporter(
            license_server="test-server",
            port=27002,  # Anderer Port
            enable_ad=False
        )
        print(f"   AD aktiviert: {'✅ Ja' if exporter2.enable_ad else '❌ Nein'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim manuellen Test: {e}")
        return False

def main():
    """Haupttest-Funktion"""
    print("Automatische Domain-Erkennung Tests")
    print("=" * 50)
    
    # Test 1: Domain-Erkennung
    is_domain = test_domain_detection()
    
    # Test 2: Automatische AD-Integration
    auto_test = test_flexlm_auto_ad()
    
    # Test 3: Manuelle Überschreibung
    manual_test = test_manual_override()
    
    # Zusammenfassung
    print("\n" + "=" * 50)
    print("ZUSAMMENFASSUNG")
    print("=" * 50)
    
    print(f"🔍 Domain erkannt: {'✅ Ja' if is_domain else '❌ Nein'}")
    print(f"🤖 Auto-AD funktioniert: {'✅ Ja' if auto_test else '❌ Nein'}")
    print(f"🔧 Manuelle Kontrolle: {'✅ Ja' if manual_test else '❌ Nein'}")
    
    print(f"\n🎯 **Ihr System:**")
    if is_domain:
        print("   ✅ Domain-Umgebung erkannt")
        print("   🚀 AD-Integration wird automatisch aktiviert")
        print("   📊 Standort-Metriken werden verfügbar sein")
    else:
        print("   ℹ️  Test-System ohne Domain")
        print("   🔧 AD-Integration bleibt automatisch deaktiviert")
        print("   📊 Standard-Metriken ohne Standort-Info")
    
    print(f"\n🎮 **Verwendung:**")
    print("   # Automatisch (empfohlen)")
    print("   python flexlm_exporter.py --verbose")
    print("   ")
    print("   # Explizit aktivieren")
    print("   python flexlm_exporter.py --enable-ad --verbose")
    print("   ")
    print("   # Explizit deaktivieren")
    print("   python flexlm_exporter.py --disable-ad --verbose")

if __name__ == '__main__':
    main()
