# FlexLM License Server Exporter mit Active Directory Integration

Ein Prometheus-Exporter für FlexLM-basierte Lizenzserver, speziell entwickelt für SolidWorks Lizenzserver mit Active Directory Integration für Standort-Informationen.

## Features

- **Umfassende Metriken**: Sammelt detaillierte Informationen über Lizenzen, Benutzer und Computer
- **Benutzer- und Hostname-Tracking**: Erfasst sowohl Benutzernamen als auch Computer-Namen
- **🆕 Active Directory Integration**: Ermittelt automatisch Standorte der Benutzer über AD
- **🆕 Standort-basierte Metriken**: Lizenzen pro Standort, Benutzer pro Standort
- **Prometheus-kompatibel**: Stellt Metriken im Prometheus-Format bereit
- **Einfache Konfiguration**: Flexibel konfigurierbar über Kommandozeilenparameter
- **Kontinuierliche Überwachung**: Automatische Aktualisierung der Metriken

## Voraussetzungen

- Python 3.7 oder höher
- FlexLM Tools (lmutil muss verfügbar sein)
- Zugriff auf den FlexLM License Server
- **Für AD-Integration**: Windows-Domänen-Umgebung mit entsprechenden Berechtigungen

## Installation

1. **Dependencies installieren:**
   ```cmd
   pip install -r requirements.txt
   ```

2. **FlexLM Tools**: Stellen Sie sicher, dass `lmutil` verfügbar ist.

3. **Active Directory**: Läuft automatisch in Windows-Domänen-Umgebungen.

## Verwendung

### Schnellstart mit AD-Integration
```cmd
python flexlm_exporter.py --verbose
```

### Mit benutzerdefinierten Parametern
```cmd
python flexlm_exporter.py --license-server lic-solidworks-emea.patec.group --license-port 25734 --lmutil-path "C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe" --verbose
```

### AD-Integration deaktivieren
```cmd
python flexlm_exporter.py --disable-ad
```

### Mit expliziten AD-Credentials
```cmd
python flexlm_exporter.py --ad-server domain.company.com --ad-username admin --ad-password secret
```

### Verfügbare Parameter

**Standard-Parameter:**
- `--license-server`: FlexLM Server (default: lic-solidworks-emea.patec.group)
- `--license-port`: FlexLM Port (default: 25734)
- `--exporter-port`: Prometheus Port (default: 9090)
- `--lmutil-path`: Pfad zu lmutil (default: C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe)
- `--verbose`: Ausführliches Logging

**🆕 Active Directory Parameter:**
- `--enable-ad`: AD-Integration aktivieren (default: True)
- `--disable-ad`: AD-Integration deaktivieren
- `--ad-server`: AD-Server (optional, wird automatisch ermittelt)
- `--ad-username`: AD-Benutzername für explizite Anmeldung
- `--ad-password`: AD-Passwort für explizite Anmeldung

## Metriken

### Standard-Metriken
- `flexlm_server_up`: Server erreichbar
- `flexlm_daemon_up`: Status der License Daemons
- `flexlm_feature_total_licenses`: Gesamtanzahl verfügbarer Lizenzen
- `flexlm_feature_used_licenses`: Anzahl verwendeter Lizenzen  
- `flexlm_feature_available_licenses`: Anzahl verfügbarer Lizenzen

### 🆕 Erweiterte Benutzer-Metriken mit Standort
- `flexlm_user_licenses`: Lizenzen pro Benutzer mit Labels:
  - `user`: Benutzername
  - `hostname`: Computer-Name
  - `display`: Display-Informationen
  - `feature`: License Feature
  - **🆕 `location`**: Standort des Benutzers (aus AD)
  - **🆕 `department`**: Abteilung des Benutzers (aus AD)

### 🆕 Standort-basierte Metriken
- `flexlm_location_licenses_total`: Gesamtanzahl Lizenzen pro Standort
- `flexlm_location_users_total`: Anzahl Benutzer pro Standort
- `flexlm_host_licenses_total`: Lizenzen pro Computer (erweitert um Standort)

### Monitoring-Metriken
- `flexlm_scrape_duration_seconds`: Zeit für Metriken-Sammlung
- `flexlm_scrape_errors_total`: Anzahl der Scrape-Fehler

## Active Directory Integration

### Automatische Erkennung
Die AD-Integration erkennt automatisch:
- **Standort**: Aus `l` (Location), `physicalDeliveryOfficeName`, `st` (State)
- **Abteilung**: Aus `department`
- **Land**: Aus `co` (Country) oder `c`
- **Vollständiger Name**: Aus `displayName` oder `cn`

### Unterstützte AD-Attribute
- `l`: Stadt/Ort
- `st`: Bundesland/State  
- `c`, `co`: Land
- `physicalDeliveryOfficeName`: Büro
- `department`: Abteilung
- `streetAddress`: Straße
- `company`: Firma

### Standort-Zusammensetzung
Der Standort wird automatisch aus verfügbaren Attributen zusammengesetzt:
```
"Büro - Stadt - Bundesland"
oder
"Stadt - Bundesland"  
oder
"Land"
```

## Beispiel Prometheus Queries

### 🆕 Lizenz-Auslastung pro Standort
```promql
sum by (location) (flexlm_location_licenses_total)
```

### 🆕 Top Standorte nach Lizenz-Verwendung
```promql
sort_desc(sum by (location) (flexlm_user_licenses))
```

### 🆕 Benutzer pro Abteilung
```promql
count by (department) (flexlm_user_licenses)
```

### Lizenz-Auslastung pro Feature
```promql
flexlm_feature_used_licenses / flexlm_feature_total_licenses * 100
```

### Computer mit den meisten Lizenzen (mit Standort)
```promql
sort_desc(flexlm_host_licenses_total)
```

## Beispiel Grafana Dashboard

### Standort-Übersicht Panel
```promql
# Lizenzen pro Standort
sum by (location) (flexlm_location_licenses_total)

# Benutzer pro Standort  
flexlm_location_users_total

# Auslastung pro Standort und Feature
sum by (location, feature) (flexlm_location_licenses_total)
```

## Troubleshooting

### Active Directory Probleme

**AD-Verbindung fehlgeschlagen:**
```
ERROR: Fehler beim Verbinden mit Active Directory
```
- Prüfen Sie, ob Sie in einer Windows-Domäne sind
- Versuchen Sie explizite Credentials: `--ad-server domain.com --ad-username user`
- Deaktivieren Sie AD temporär: `--disable-ad`

**Benutzer nicht gefunden:**
- Standort wird als "Unknown" angezeigt
- Normal für lokale Benutzer oder externe Accounts
- Prüfen Sie AD-Berechtigungen

**Performance-Optimierung:**
- Benutzer-Cache läuft 5 Minuten
- Bei vielen Benutzern Cache-Zeit anpassen
- AD-Abfragen nur bei neuen Benutzern

### Standard-Troubleshooting

**lmutil nicht gefunden:**
```cmd
python flexlm_exporter.py --lmutil-path "C:\Path\To\lmutil.exe"
```

**Verbindungsprobleme:**
- Firewall-Einstellungen prüfen
- License Server läuft und erreichbar
- Server-Adresse und Port korrekt

## Konfigurationsdateien

### Prometheus Scrape Config
```yaml
scrape_configs:
  - job_name: 'flexlm-solidworks-with-locations'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
    metrics_path: /metrics
```

### Grafana Dashboard Import
Die erweiterten Metriken ermöglichen Dashboards mit:
- Standort-basierte Auslastung
- Geografische Lizenz-Verteilung  
- Abteilungs-spezifische Berichte
- Computer-Standort-Zuordnung

## Sicherheit

- AD-Integration verwendet Standard Windows-Authentifizierung
- Keine Passwörter im Klartext (außer bei expliziter Angabe)
- Benutzer-Cache wird nur im Arbeitsspeicher gehalten
- AD-Abfragen werden minimiert durch Caching

## Support

Die AD-Integration funktioniert am besten in Windows-Domänen-Umgebungen. Ohne AD werden alle Standorte als "Unknown" angezeigt, die Basis-Funktionalität bleibt aber erhalten.
