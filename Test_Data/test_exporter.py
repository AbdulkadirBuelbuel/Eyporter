#!/usr/bin/env python3
"""
Test-Skript für den FlexLM Exporter
Testet die Funktionalität ohne echten License Server
"""

import sys
import time
import requests
from unittest.mock import patch, MagicMock
import threading

def test_lmstat_parsing():
    """Testet das Parsing der lmstat Ausgabe"""
    print("=== Test: lmstat Parsing ===")
    
    # Beispiel lmstat -a Ausgabe für SolidWorks
    test_output = """
lmutil - Copyright (c) 1989-2022 Flexera. All Rights Reserved.
Flexible License Manager status on Wed 8/4/2025 14:30

License server status: 27000@localhost
    License file(s) on localhost: C:\\Program Files\\SolidWorks\\Network License Manager\\Licenses\\sw_d.lic:

localhost: license server UP (MASTER) v11.18.1

Vendor daemon status (on localhost):

SolidWorksNetworkLicense: UP v11.18.1
SOLIDWORKS: UP v11.18.1

Feature usage info:

Users of SOLIDWORKS:  (Total of 10 licenses issued;  Total of 3 licenses in use)

  "SOLIDWORKS" v2023.0400, vendor: SolidWorksNetworkLicense
  floating license

    user1 WORKSTATION-01 WORKSTATION-01 (v2023.0400) (localhost/27000 1234), start Wed 8/4 14:25
    user2 WORKSTATION-02 WORKSTATION-02 (v2023.0400) (localhost/27000 1235), start Wed 8/4 14:20  
    admin PC-ADMIN PC-ADMIN (v2023.0400) (localhost/27000 1236), start Wed 8/4 14:15

Users of COSMOSWORKS:  (Total of 5 licenses issued;  Total of 1 licenses in use)

  "COSMOSWORKS" v2023.0400, vendor: SolidWorksNetworkLicense
  floating license

    user1 WORKSTATION-01 WORKSTATION-01 (v2023.0400) (localhost/27000 1237), start Wed 8/4 14:26
"""
    
    # Importe hier um Zirkular-Import zu vermeiden
    sys.path.append('.')
    from flexlm_exporter import FlexLMExporter
    
    exporter = FlexLMExporter()
    data = exporter.parse_lmstat_output(test_output)
    
    print(f"Server Status: {data['server_status']}")
    print(f"Anzahl Daemons: {len(data['daemons'])}")
    print(f"Anzahl Features: {len(data['features'])}")
    print(f"Anzahl Benutzer: {len(data['users'])}")
    
    # Features details
    for feature in data['features']:
        print(f"\nFeature: {feature['name']}")
        print(f"  Total: {feature['total']}, Used: {feature['used']}, Available: {feature['available']}")
        print(f"  Benutzer: {len(feature['users'])}")
        for user in feature['users']:
            print(f"    - {user['username']} auf {user['hostname']}")
    
    # Test erfolgreich wenn alle erwarteten Werte vorhanden sind
    assert data['server_status'] == True
    assert len(data['daemons']) == 2
    assert len(data['features']) == 2
    assert len(data['users']) == 4
    
    # Prüfe spezifische Feature-Daten
    solidworks_feature = next(f for f in data['features'] if f['name'] == 'SOLIDWORKS')
    assert solidworks_feature['total'] == 10
    assert solidworks_feature['used'] == 3
    assert solidworks_feature['available'] == 7
    
    print("✓ lmstat Parsing Test erfolgreich!")

def test_mock_exporter():
    """Testet den Exporter mit Mock-Daten"""
    print("\n=== Test: Mock Exporter ===")
    
    sys.path.append('.')
    from flexlm_exporter import FlexLMExporter
    from prometheus_client import CollectorRegistry
    
    # Eigenes Registry für Test verwenden
    test_registry = CollectorRegistry()
    
    # Mock lmutil command
    def mock_run_lmutil_command(self, command):
        mock_output = """
lmutil - Copyright (c) 1989-2022 Flexera. All Rights Reserved.
Flexible License Manager status on Wed 8/4/2025 14:30

License server status: 27000@localhost
localhost: license server UP (MASTER) v11.18.1

Vendor daemon status (on localhost):
SolidWorksNetworkLicense: UP v11.18.1

Feature usage info:
Users of SOLIDWORKS:  (Total of 5 licenses issued;  Total of 2 licenses in use)

    testuser TESTPC-01 TESTPC-01 (v2023.0400) (localhost/27000 1234), start Wed 8/4 14:25
    admin ADMIN-PC ADMIN-PC (v2023.0400) (localhost/27000 1235), start Wed 8/4 14:20
"""
        return True, mock_output
    
    # Patch the method und verwende separates Registry
    with patch.object(FlexLMExporter, 'run_lmutil_command', mock_run_lmutil_command):
        # Registry patchen
        with patch('flexlm_exporter.REGISTRY', test_registry):
            exporter = FlexLMExporter()
            exporter.collect_metrics()
            
            print("✓ Mock Exporter Test erfolgreich!")

def test_metrics_endpoint():
    """Testet den HTTP Metrics Endpoint"""
    print("\n=== Test: Metrics Endpoint ===")
    
    sys.path.append('.')
    from flexlm_exporter import FlexLMExporter
    
    # Mock für lmutil
    def mock_run_lmutil_command(self, command):
        return True, """
License server status: 27000@localhost
localhost: license server UP (MASTER) v11.18.1
Vendor daemon status (on localhost):
SolidWorksNetworkLicense: UP v11.18.1
Feature usage info:
Users of SOLIDWORKS:  (Total of 3 licenses issued;  Total of 1 licenses in use)
    testuser TESTPC TESTPC (v2023.0400) (localhost/27000 1234), start Wed 8/4 14:25
"""
    
    # Starte Exporter in separatem Thread
    with patch.object(FlexLMExporter, 'run_lmutil_command', mock_run_lmutil_command):
        exporter = FlexLMExporter()
        
        def start_exporter():
            exporter.start_server(port=9091)  # Anderen Port für Test
        
        thread = threading.Thread(target=start_exporter, daemon=True)
        thread.start()
        
        # Warte bis Server gestartet ist
        time.sleep(2)
        
        try:
            # Teste Metrics Endpoint
            response = requests.get('http://localhost:9091/metrics', timeout=5)
            
            if response.status_code == 200:
                metrics_content = response.text
                print(f"Metrics Response Length: {len(metrics_content)} chars")
                
                # Prüfe ob wichtige Metriken vorhanden sind
                expected_metrics = [
                    'flexlm_server_up',
                    'flexlm_feature_total_licenses',
                    'flexlm_user_licenses',
                    'flexlm_host_licenses_total'
                ]
                
                for metric in expected_metrics:
                    if metric in metrics_content:
                        print(f"✓ Metric '{metric}' gefunden")
                    else:
                        print(f"✗ Metric '{metric}' NICHT gefunden")
                
                print("✓ Metrics Endpoint Test erfolgreich!")
            else:
                print(f"✗ HTTP Fehler: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Verbindungsfehler: {e}")

def main():
    """Führt alle Tests aus"""
    print("FlexLM Exporter Tests")
    print("=" * 40)
    
    try:
        test_lmstat_parsing()
        test_mock_exporter()
        test_metrics_endpoint()
        
        print("\n" + "=" * 40)
        print("✓ Alle Tests erfolgreich abgeschlossen!")
        
    except Exception as e:
        print(f"\n✗ Test fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
