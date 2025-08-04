# FlexLM License Server Exporter

Ein Prometheus-Exporter für FlexLM-basierte Lizenzserver, speziell entwickelt für SolidWorks Lizenzserver.

## Features

- **Umfassende Metriken**: Sammelt detaillierte Informationen über Lizenzen, Benutzer und Computer
- **Benutzer- und Hostname-Tracking**: Erfasst sowohl Benutzernamen als auch Computer-Namen
- **Prometheus-kompatibel**: Stellt Metriken im Prometheus-Format bereit
- **Einfache Konfiguration**: Flexibel konfigurierbar über Kommandozeilenparameter
- **Kontinuierliche Überwachung**: Automatische Aktualisierung der Metriken

## Voraussetzungen

- Python 3.7 oder höher
- FlexLM Tools (lmutil muss verfügbar sein)
- Zugriff auf den FlexLM License Server

## Installation

1. **Dependencies installieren:**
   ```cmd
   pip install -r requirements.txt
   ```

2. **FlexLM Tools**: Stellen Sie sicher, dass `lmutil` im PATH verfügbar ist oder geben Sie den Pfad explizit an.

## Verwendung

### Schnellstart
```cmd
start_exporter.bat
```

### Manueller Start
```cmd
python flexlm_exporter.py
```

### Mit benutzerdefinierten Parametern
```cmd
python flexlm_exporter.py --license-server 192.168.1.100 --license-port 27000 --exporter-port 9090
```

### Verfügbare Parameter

- `--license-server`: FlexLM Server Hostname/IP (default: localhost)
- `--license-port`: FlexLM Server Port (default: 27000)
- `--exporter-port`: Port für den Prometheus Exporter (default: 9090)
- `--lmutil-path`: Pfad zur lmutil Binary (default: lmutil)
- `--verbose`: Ausführliches Logging aktivieren

## Metriken

Der Exporter stellt folgende Prometheus-Metriken bereit:

### Server Status
- `flexlm_server_up`: Server erreichbar (1 = up, 0 = down)
- `flexlm_daemon_up`: Status der License Daemons

### License Features
- `flexlm_feature_total_licenses`: Gesamtanzahl verfügbarer Lizenzen
- `flexlm_feature_used_licenses`: Anzahl verwendeter Lizenzen  
- `flexlm_feature_available_licenses`: Anzahl verfügbarer Lizenzen

### Benutzer und Computer
- `flexlm_user_licenses`: Lizenzen pro Benutzer mit Labels für:
  - `user`: Benutzername
  - `hostname`: Computer-Name
  - `display`: Display-Informationen
  - `feature`: License Feature
- `flexlm_host_licenses_total`: Gesamtanzahl Lizenzen pro Computer

### Monitoring
- `flexlm_scrape_duration_seconds`: Zeit für Metriken-Sammlung
- `flexlm_scrape_errors_total`: Anzahl der Scrape-Fehler

## Metriken URL

Nach dem Start ist der Exporter unter folgender URL verfügbar:
```
http://localhost:9090/metrics
```

## Beispiel Prometheus Konfiguration

```yaml
scrape_configs:
  - job_name: 'flexlm-solidworks'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
    metrics_path: /metrics
```

## Beispiel Grafana Dashboard Queries

### Lizenz-Auslastung pro Feature
```promql
flexlm_feature_used_licenses / flexlm_feature_total_licenses * 100
```

### Top Benutzer nach Lizenz-Verwendung
```promql
sort_desc(sum by (user) (flexlm_user_licenses))
```

### Computer mit den meisten Lizenzen
```promql
sort_desc(flexlm_host_licenses_total)
```

### Verfügbare Lizenzen
```promql
flexlm_feature_available_licenses
```

## Troubleshooting

### lmutil nicht gefunden
```cmd
python flexlm_exporter.py --lmutil-path "C:\Program Files\FlexLM\lmutil.exe"
```

### Verbindungsprobleme
- Prüfen Sie die Firewall-Einstellungen
- Stellen Sie sicher, dass der License Server läuft
- Überprüfen Sie Server-Adresse und Port

### Logging aktivieren
```cmd
python flexlm_exporter.py --verbose
```

## Anpassungen

Der Code kann einfach erweitert werden für:
- Zusätzliche Metriken
- Andere FlexLM-basierte Software
- Benutzerdefinierte Labels
- Erweiterte Parsing-Logik

## Support

Bei Problemen oder Fragen zum Exporter, prüfen Sie:
1. Die Log-Ausgaben mit `--verbose`
2. Die lmutil Ausgabe manuell: `lmutil lmstat -a -c server@port`
3. Die Prometheus Metriken unter `/metrics`
