#!/usr/bin/env python3
"""
Einfacher Test für den FlexLM Exporter Parser
"""

import sys
import re

def debug_parse_lmstat_output(output: str):
    """Debug-Version des lmstat Parsers"""
    print("=== DEBUG: lmstat Parsing ===")
    
    data = {
        'server_status': False,
        'daemons': [],
        'features': [],
        'users': []
    }
    
    lines = output.split('\n')
    current_feature = None
    in_users_section = False
    line_num = 0
    
    for line in lines:
        line_num += 1
        original_line = line
        line = line.strip()
        
        print(f"Zeile {line_num}: '{original_line}'")
        
        # Server Status prüfen
        if 'license server UP' in line:
            data['server_status'] = True
            print(f"  -> Server Status: UP")
        elif 'Cannot connect to license server' in line:
            data['server_status'] = False
            print(f"  -> Server Status: DOWN")
        
        # Daemon Status
        daemon_match = re.search(r'(\w+): UP v([0-9.]+)', line)
        if daemon_match:
            daemon_name = daemon_match.group(1)
            version = daemon_match.group(2)
            data['daemons'].append({
                'name': daemon_name,
                'status': 'UP',
                'version': version
            })
            print(f"  -> Daemon gefunden: {daemon_name} v{version}")
        
        # Feature Informationen
        feature_match = re.search(r'Users of (\w+):\s+\(Total of (\d+) license[s]? issued;\s+Total of (\d+) license[s]? in use\)', line)
        if feature_match:
            feature_name = feature_match.group(1)
            total_licenses = int(feature_match.group(2))
            used_licenses = int(feature_match.group(3))
            
            current_feature = {
                'name': feature_name,
                'total': total_licenses,
                'used': used_licenses,
                'available': total_licenses - used_licenses,
                'users': []
            }
            data['features'].append(current_feature)
            in_users_section = True
            print(f"  -> Feature gefunden: {feature_name} ({used_licenses}/{total_licenses})")
            continue
        
        # Benutzer Informationen
        if in_users_section and current_feature:
            # Verschiedene Patterns probieren
            patterns = [
                r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)',
                r'(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)',
                r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+\(.*?\)',
            ]
            
            user_found = False
            for i, pattern in enumerate(patterns):
                user_match = re.search(pattern, original_line)  # Verwende original_line für besseres Matching
                if user_match:
                    username = user_match.group(1)
                    hostname = user_match.group(2)
                    display = user_match.group(3)
                    
                    user_info = {
                        'username': username,
                        'hostname': hostname,
                        'display': display,
                        'feature': current_feature['name']
                    }
                    
                    current_feature['users'].append(user_info)
                    data['users'].append(user_info)
                    print(f"  -> Benutzer gefunden (Pattern {i+1}): {username}@{hostname}")
                    user_found = True
                    break
            
            if not user_found and line and not line.startswith('"') and not line.startswith('floating'):
                print(f"  -> Keine Benutzer-Pattern gefunden für: '{original_line}'")
            
            # Ende der Benutzer-Sektion erkennen
            if line == '' or line.startswith('Users of ') or line.startswith('"'):
                if in_users_section:
                    print(f"  -> Ende der Benutzer-Sektion für {current_feature['name'] if current_feature else 'unknown'}")
                in_users_section = False
                current_feature = None
    
    return data

def test_parsing():
    """Test des verbesserten Parsers"""
    
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
    
    data = debug_parse_lmstat_output(test_output)
    
    print("\n=== ERGEBNISSE ===")
    print(f"Server Status: {data['server_status']}")
    print(f"Anzahl Daemons: {len(data['daemons'])}")
    print(f"Anzahl Features: {len(data['features'])}")
    print(f"Anzahl Benutzer: {len(data['users'])}")
    
    print("\nDaemons:")
    for daemon in data['daemons']:
        print(f"  - {daemon['name']} v{daemon['version']} ({daemon['status']})")
    
    print("\nFeatures:")
    for feature in data['features']:
        print(f"  - {feature['name']}: {feature['used']}/{feature['total']} ({feature['available']} verfügbar)")
        print(f"    Benutzer: {len(feature['users'])}")
        for user in feature['users']:
            print(f"      * {user['username']} auf {user['hostname']}")
    
    print("\nAlle Benutzer:")
    for user in data['users']:
        print(f"  - {user['username']}@{user['hostname']} ({user['feature']})")

if __name__ == '__main__':
    test_parsing()
