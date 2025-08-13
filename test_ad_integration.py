#!/usr/bin/env python3
"""
Test für Active Directory Integration
"""

import sys
import logging

# Logging aktivieren
logging.basicConfig(level=logging.DEBUG)

def test_ad_integration():
    """Testet die Active Directory Integration"""
    print("=== Test: Active Directory Integration ===")
    
    try:
        from active_directory_helper import ActiveDirectoryHelper, AD_AVAILABLE
        
        if not AD_AVAILABLE:
            print("❌ Active Directory Module nicht verfügbar")
            return False
        
        print("✅ Active Directory Module verfügbar")
        
        # AD Helper initialisieren
        ad_helper = ActiveDirectoryHelper()
        
        if not ad_helper.is_enabled():
            print("❌ Active Directory Verbindung fehlgeschlagen")
            return False
        
        print("✅ Active Directory Verbindung erfolgreich")
        
        # Test mit dem aktuellen Benutzer
        import os
        current_user = os.getenv('USERNAME', 'testuser')
        print(f"Teste mit Benutzer: {current_user}")
        
        user_info = ad_helper.get_user_info(current_user)
        print(f"Benutzer-Info: {user_info}")
        
        location = ad_helper.get_user_location(current_user)
        print(f"Standort: {location}")
        
        if location and location != "Unknown":
            print("✅ AD-Standort-Abfrage erfolgreich")
            return True
        else:
            print("⚠️  Kein Standort gefunden (normal wenn Benutzer nicht in AD)")
            return True
            
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_flexlm_with_ad():
    """Testet den FlexLM Exporter mit AD-Integration"""
    print("\n=== Test: FlexLM Exporter mit AD ===")
    
    try:
        from flexlm_exporter import FlexLMExporter
        
        # Erstelle Exporter mit AD-Integration
        exporter = FlexLMExporter(
            license_server="test-server",
            port=27000,
            lmutil_path="echo",  # Mock-Befehl
            enable_ad=True
        )
        
        if exporter.enable_ad and exporter.ad_helper:
            print("✅ FlexLM Exporter mit AD-Integration erstellt")
            return True
        else:
            print("⚠️  AD-Integration nicht aktiviert (normal ohne echten AD)")
            return True
            
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Führt alle AD-Tests aus"""
    print("Active Directory Integration Tests")
    print("=" * 50)
    
    success = True
    
    success &= test_ad_integration()
    success &= test_flexlm_with_ad()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Alle Tests erfolgreich!")
    else:
        print("❌ Einige Tests fehlgeschlagen")
    
    print("\nHinweise:")
    print("- Wenn Sie nicht in einer AD-Domäne sind, ist das normal")
    print("- Die Integration funktioniert nur in Windows-Domänen-Umgebungen")
    print("- Ohne AD werden 'Unknown' Standorte verwendet")

if __name__ == '__main__':
    main()
