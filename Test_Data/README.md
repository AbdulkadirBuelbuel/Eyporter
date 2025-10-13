# FlexLM License Server Exporter mit Username-basiertem Standort-Mapping

Ein Prometheus-Exporter für FlexLM-basierte Lizenzserver, speziell entwickelt für SolidWorks Lizenzserver. Standorte werden aus Benutzernamen abgeleitet und über eine Mapping-Datei (mapping.json) auf vollständige Namen gemappt.

## Features

- Umfassende Metriken: Lizenzen, Benutzer, Hosts
- Benutzer- und Hostname-Tracking
- Standort-basierte Metriken: Lizenzen und Benutzer pro Standort
- Prometheus-kompatibel (Metrics Endpoint)
- Einfache Konfiguration über CLI und mapping.json

## Standort-Mapping (ohne Active Directory)

- Der Standort wird aus dem Benutzernamen abgeleitet: alle Buchstaben nach der letzten Zahl bilden den Standort-Code.
  Beispiele: "bla99bng" -> bng, "user123fra" -> fra, "test42muc" -> muc
- Die Codes werden in `mapping.json` unter `location_mapping` auf Standortnamen gemappt.
- Unbekannte oder fehlende Codes werden als "Unknown" gemeldet.

Siehe `README_LOCATION_MAPPING.md` für Details.

## Voraussetzungen

- Python 3.8 oder höher
- FlexLM Tools (lmutil muss verfügbar sein)
- Zugriff auf den FlexLM License Server

## Installation

1. Dependencies installieren:
   
   pip install -r requirements.txt

2. FlexLM Tools bereitstellen: `lmutil` muss vorhanden und der Pfad bekannt sein.

## Verwendung

Schnellstart mit Standardwerten:

python flexlm_exporter.py --verbose

Mit benutzerdefinierten Parametern:

python flexlm_exporter.py \
  --license-server lic-solidworks-emea.patec.group \
  --license-port 25734 \
  --lmutil-path "C:\\Temp\\SolidWorks_Exporter\\FlexLM_Export\\lmutil.exe" \
  --mapping-file mapping.json \
  --exporter-port 9090 \
  --verbose

### Verfügbare Parameter

- --license-server: FlexLM Server (default: lic-solidworks-emea.patec.group)
- --license-port: FlexLM Port (default: 25734)
- --exporter-port: Prometheus Port (default: 9090)
- --lmutil-path: Pfad zu lmutil (default: C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe)
- --mapping-file: Pfad zur Mapping-Datei (default: mapping.json)
- --verbose: Ausführliches Logging

## Metriken

- flexlm_server_up: Server erreichbar
- flexlm_daemon_up: Status der License Daemons
- flexlm_feature_total_licenses: Gesamtanzahl verfügbarer Lizenzen
- flexlm_feature_used_licenses: Anzahl verwendeter Lizenzen
- flexlm_feature_available_licenses: Anzahl verfügbarer Lizenzen
- flexlm_user_licenses: Lizenzen pro Benutzer mit Labels: server, vendor, feature, user, hostname, display, location, department (immer "Unknown")
- flexlm_location_licenses_total: Gesamtanzahl Lizenzen pro Standort (server, location, feature)
- flexlm_location_users_total: Anzahl Benutzer pro Standort (server, location)
- flexlm_host_licenses_total: Lizenzen pro Computer inkl. Standort (server, hostname, location)
- flexlm_scrape_duration_seconds: Dauer der Sammlung
- flexlm_scrape_errors_total: Anzahl der Fehler

## Beispiel Prometheus-Konfiguration

scrape_configs:
  - job_name: 'flexlm-solidworks'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
    metrics_path: /metrics

## Beispiel PromQL

- Lizenzen pro Standort:
  sum by (location) (flexlm_location_licenses_total)

- Top-Hosts nach Lizenzanzahl:
  sort_desc(flexlm_host_licenses_total)

- Benutzer pro Standort:
  flexlm_location_users_total

## Troubleshooting

- lmutil nicht gefunden: Pfad mit --lmutil-path angeben.
- Keine Standortzuordnung: Code fehlt in mapping.json -> Eintrag hinzufügen.
- Parser findet keine Benutzer: Prüfen Sie, ob die lmstat-Ausgabe zu Ihrem FlexLM passt; ggf. Regex anpassen in parse_lmstat_output.

## Sicherheit

- Es werden keine Verbindungen zu Active Directory hergestellt.
- Keine Passwörter erforderlich. Nur lmutil wird aufgerufen.

## Lizenz / Support

Interne Nutzung. Beiträge willkommen. Für Support bitte Issues mit Beispielausgaben (bereinigt) anlegen.
