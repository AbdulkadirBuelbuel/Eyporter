#!/usr/bin/env python3
"""
Demo für den FlexLM Exporter mit simulierten Daten
Startet den Exporter mit Mock-Daten für Demonstrationszwecke
"""

import time
import threading
from unittest.mock import patch
import logging

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mock_lmstat_output():
    """Erstellt realistische Mock-Daten für SolidWorks"""
    return """
lmutil - Copyright (c) 1989-2022 Flexera. All Rights Reserved.
Flexible License Manager status on Mon 8/4/2025 14:30

License server status: 27000@localhost
    License file(s) on localhost: C:\\Program Files\\SolidWorks\\Network License Manager\\Licenses\\sw_d.lic:

localhost: license server UP (MASTER) v11.18.1

Vendor daemon status (on localhost):

SolidWorksNetworkLicense: UP v11.18.1
SOLIDWORKS: UP v11.18.1

Feature usage info:

Users of SOLIDWORKS:  (Total of 15 licenses issued;  Total of 8 licenses in use)

  "SOLIDWORKS" v2023.0400, vendor: SolidWorksNetworkLicense
  floating license    mueller ENGR-WS001 ENGR-WS001 (v2023.0400) (localhost/27000 1234), start Mon 8/4 08:30
    bla99bng CAD-PC-05 CAD-PC-05 (v2023.0400) (localhost/27000 1235), start Mon 8/4 09:15
    user123fra DESIGN-01 DESIGN-01 (v2023.0400) (localhost/27000 1236), start Mon 8/4 09:45
    test42muc LAPTOP-ENGR LAPTOP-ENGR (v2023.0400) (localhost/27000 1237), start Mon 8/4 10:20
    admin1dus WORKSTATION-A WORKSTATION-A (v2023.0400) (localhost/27000 1238), start Mon 8/4 11:00
    john007lon CAD-STATION-12 CAD-STATION-12 (v2023.0400) (localhost/27000 1239), start Mon 8/4 11:30
    marie56par MOBILE-CAD-01 MOBILE-CAD-01 (v2023.0400) (localhost/27000 1240), start Mon 8/4 12:00
    peter88ber ADMIN-PC ADMIN-PC (v2023.0400) (localhost/27000 1241), start Mon 8/4 13:00

Users of COSMOSWORKS:  (Total of 8 licenses issued;  Total of 3 licenses in use)

  "COSMOSWORKS" v2023.0400, vendor: SolidWorksNetworkLicense
  floating license

    mueller ENGR-WS001 ENGR-WS001 (v2023.0400) (localhost/27000 1242), start Mon 8/4 08:35
    weber DESIGN-01 DESIGN-01 (v2023.0400) (localhost/27000 1243), start Mon 8/4 09:50
    bauer WORKSTATION-A WORKSTATION-A (v2023.0400) (localhost/27000 1244), start Mon 8/4 11:05

Users of PDMWORKS:  (Total of 5 licenses issued;  Total of 2 licenses in use)

  "PDMWORKS" v2023.0400, vendor: SolidWorksNetworkLicense
  floating license

    admin ADMIN-PC ADMIN-PC (v2023.0400) (localhost/27000 1245), start Mon 8/4 13:05
    schmidt CAD-PC-05 CAD-PC-05 (v2023.0400) (localhost/27000 1246), start Mon 8/4 09:20
"""

def mock_run_lmutil_command(self, command):
    """Mock-Funktion für lmutil Aufrufe, liefert (rc, stdout, stderr)."""
    current_time = time.time()
    if int(current_time) % 60 < 30:
        return 0, create_mock_lmstat_output(), ""
    else:
        reduced_output = create_mock_lmstat_output().replace(
            'Total of 8 licenses in use', 'Total of 5 licenses in use'
        ).replace(
            'Total of 3 licenses in use', 'Total of 2 licenses in use'
        )
        lines = reduced_output.split('\n')
        filtered_lines = []
        skip_next = 0
        for line in lines:
            if skip_next > 0:
                skip_next -= 1
                continue
            if 'wagner MOBILE-CAD-01' in line or 'meyer CAD-STATION-12' in line or 'fischer LAPTOP-ENGR' in line:
                skip_next = 0
                continue
            filtered_lines.append(line)
        return 0, '\n'.join(filtered_lines), ""

def main():
    """Startet den Demo-Exporter"""
    print("FlexLM Exporter Demo")
    print("=" * 40)
    print("Startet einen FlexLM Exporter mit simulierten SolidWorks-Daten")
    print("Verfügbar unter: http://localhost:9090/metrics")
    print("Drücken Sie Ctrl+C zum Beenden")
    print()
    
    # Import nach der Ausgabe um Verzögerung zu vermeiden
    from flexlm_exporter import FlexLMExporter
    
    # Patch lmutil command mit Mock-Daten
    with patch.object(FlexLMExporter, 'run_lmutil_command', mock_run_lmutil_command):
        try:
            exporter = FlexLMExporter(
                license_server="demo-server",
                port=27000,
                lmutil_path="mock-lmutil"
            )
            
            print("Starte Mock FlexLM Exporter...")
            print("Die Daten ändern sich alle 60 Sekunden zur Demonstration")
            
            exporter.start_server(port=9090)
            
        except KeyboardInterrupt:
            print("\nExporter gestoppt.")
        except Exception as e:
            print(f"Fehler: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
