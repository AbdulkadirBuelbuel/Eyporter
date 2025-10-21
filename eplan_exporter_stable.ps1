# EPLAN License Prometheus Exporter - Stable HttpListener Version
# Liest Report_current.txt und stellt Metriken über HTTP bereit

$eplanLic_path = "C:\Eplan"

# Verzeichnisse erstellen falls nicht vorhanden
if (!(Test-Path $eplanLic_path)) {
    New-Item -ItemType Directory -Path $eplanLic_path -Force | Out-Null
}
if (!(Test-Path "C:\Temp")) {
    New-Item -ItemType Directory -Path "C:\Temp" -Force | Out-Null
}

# Globale Variablen
$global:eplan_metrics = @{}
$global:http_listener = $null
$global:server_running = $false

function Read-ReportFile {
    param()
    
    BEGIN {
        $PSDefaultParameterValues['Get-Content:Encoding'] = 'unicode'
        $file_to_read = "$eplanLic_path\Report_current.txt"
        $start_reading = $False
        $global:eplan_metrics = @{}  # Reset bei jedem Scan
    }
    
    PROCESS {
        if (!(Test-Path $file_to_read)) {
            Write-Host "WARNUNG: Report-Datei nicht gefunden: $file_to_read"
            # Dummy-Metrik erstellen
            $global:eplan_metrics["dummy|no_data"] = @{
                bundle = "no_data"
                module = "no_data"
                total = 0
                in_use = 0
                borrow_issued = 0
                borrowed = 0
                free = 0
                timestamp = Get-Date
            }
            return
        }

        try {
            $lines = Get-Content -Path $file_to_read -ErrorAction Stop
            foreach ($line in $lines) {
                if ($start_reading) {
                    $columns = $line.Split("`t")
                    if ($columns.Count -ge 8) {
                        $total_issued = $columns[1]
                        $total_license_in_use = $columns[2]
                        $total_borrow_issued = $columns[3]
                        $total_borrowed = $columns[4]
                        $total_free = $columns[5]
                        $bundle = $columns[6]
                        $module = $columns[7]
                        $measurement = $columns[0]
                        $ger_time = (Get-Date $measurement).ToString("yyyy.MM.dd HH:mm")
                        $measurement = $ger_time
                        Update-EplanMetrics -measurement $measurement -bundle $bundle -module $module -total_issued $total_issued -total_license_in_use $total_license_in_use -total_borrow_issued $total_borrow_issued -total_borrowed $total_borrowed -total_free $total_free
                    }
                }
                elseif ($line.StartsWith("Time")) {
                    $start_reading = $True
                }
            }
        } catch {
            Write-Host "FEHLER beim Lesen der Datei: $_"
        }
    }
}

function Update-EplanMetrics {
    param (
        [String]$measurement, 
        [String]$bundle, 
        [String]$module, 
        [String]$total_issued, 
        [String]$total_license_in_use,
        [String]$total_borrow_issued,
        [String]$total_borrowed,
        [String]$total_free
    )
    
    $bundle_clean = ($bundle -replace '"', '\"' -replace '\\', '\\' -replace '\n', ' ' -replace '\r', '').Trim()
    $module_clean = ($module -replace '"', '\"' -replace '\\', '\\' -replace '\n', ' ' -replace '\r', '').Trim()
    
    if ([string]::IsNullOrWhiteSpace($bundle_clean)) { $bundle_clean = "unknown" }
    if ([string]::IsNullOrWhiteSpace($module_clean)) { $module_clean = "unknown" }
    
    try { $total = [int]$total_issued } catch { $total = 0 }
    try { $in_use = [int]$total_license_in_use } catch { $in_use = 0 }
    try { $borrow_issued = [int]$total_borrow_issued } catch { $borrow_issued = 0 }
    try { $borrowed = [int]$total_borrowed } catch { $borrowed = 0 }
    try { $free = [int]$total_free } catch { $free = 0 }
    
    $key = "$bundle_clean|$module_clean"
    
    $global:eplan_metrics[$key] = @{
        bundle = $bundle_clean
        module = $module_clean
        total = $total
        in_use = $in_use
        borrow_issued = $borrow_issued
        borrowed = $borrowed
        free = $free
        timestamp = Get-Date
    }
}

function Get-PrometheusMetrics {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("# HELP eplan_licenses_total Total number of EPLAN licenses")
    [void]$sb.AppendLine("# TYPE eplan_licenses_total gauge")
    [void]$sb.AppendLine("# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use")
    [void]$sb.AppendLine("# TYPE eplan_licenses_in_use gauge")
    [void]$sb.AppendLine("# HELP eplan_licenses_borrow_issued Total number of borrow licenses issued")
    [void]$sb.AppendLine("# TYPE eplan_licenses_borrow_issued gauge")
    [void]$sb.AppendLine("# HELP eplan_licenses_borrowed Number of licenses currently borrowed")
    [void]$sb.AppendLine("# TYPE eplan_licenses_borrowed gauge")
    [void]$sb.AppendLine("# HELP eplan_licenses_free Number of free licenses available")
    [void]$sb.AppendLine("# TYPE eplan_licenses_free gauge")
    
    if ($global:eplan_metrics.Count -eq 0) {
        [void]$sb.AppendLine('eplan_licenses_total{bundle="no_data",module="no_data"} 0')
        [void]$sb.AppendLine('eplan_licenses_in_use{bundle="no_data",module="no_data"} 0')
        [void]$sb.AppendLine('eplan_licenses_borrow_issued{bundle="no_data",module="no_data"} 0')
        [void]$sb.AppendLine('eplan_licenses_borrowed{bundle="no_data",module="no_data"} 0')
        [void]$sb.AppendLine('eplan_licenses_free{bundle="no_data",module="no_data"} 0')
    } else {
        foreach ($key in $global:eplan_metrics.Keys) {
            $metric = $global:eplan_metrics[$key]
            $bundle = $metric.bundle
            $module = $metric.module
            [void]$sb.Append("eplan_licenses_total")
            [void]$sb.Append('{bundle="')
            [void]$sb.Append($bundle)
            [void]$sb.Append('",module="')
            [void]$sb.Append($module)
            [void]$sb.Append('"} ')
            [void]$sb.AppendLine($metric.total)
            
            [void]$sb.Append("eplan_licenses_in_use")
            [void]$sb.Append('{bundle="')
            [void]$sb.Append($bundle)
            [void]$sb.Append('",module="')
            [void]$sb.Append($module)
            [void]$sb.Append('"} ')
            [void]$sb.AppendLine($metric.in_use)
            
            [void]$sb.Append("eplan_licenses_borrow_issued")
            [void]$sb.Append('{bundle="')
            [void]$sb.Append($bundle)
            [void]$sb.Append('",module="')
            [void]$sb.Append($module)
            [void]$sb.Append('"} ')
            [void]$sb.AppendLine($metric.borrow_issued)
            
            [void]$sb.Append("eplan_licenses_borrowed")
            [void]$sb.Append('{bundle="')
            [void]$sb.Append($bundle)
            [void]$sb.Append('",module="')
            [void]$sb.Append($module)
            [void]$sb.Append('"} ')
            [void]$sb.AppendLine($metric.borrowed)
            
            [void]$sb.Append("eplan_licenses_free")
            [void]$sb.Append('{bundle="')
            [void]$sb.Append($bundle)
            [void]$sb.Append('",module="')
            [void]$sb.Append($module)
            [void]$sb.Append('"} ')
            [void]$sb.AppendLine($metric.free)
        }
    }
    
    return $sb.ToString()
}

function Start-HttpServerSimple {
    param([int]$Port = 9094)
    
    try {
        # Listener nur im Background-Job starten (kein Bind im Main-Thread)
        $global:http_job = Start-Job -ScriptBlock {
            param($Port)
            
            $logFile = "C:\Temp\eplan_exporter_http.log"
            try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) HTTP job starting on port $Port" } catch {}

            try {
                $listener = New-Object System.Net.HttpListener
                $listener.Prefixes.Clear()
                # Remotezugriff: an alle Interfaces binden (URLACL erforderlich)
                $listener.Prefixes.Add("http://+:$Port/")
                $listener.Start()
                
                while ($listener.IsListening) {
                    $context = $null
                    try {
                        $context = $listener.GetContext()
                        $request = $context.Request
                        $response = $context.Response
                        $response.KeepAlive = $false
                        $response.SendChunked = $false
                        $response.Headers['Cache-Control'] = 'no-cache'
                        $path = $request.Url.AbsolutePath.ToLowerInvariant()
                        try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Request: $($request.HttpMethod) $($request.Url.AbsoluteUri)" } catch {}
                          if ($path -eq "/metrics") {
                            $metrics_file = "D:\Test\eplan_metrics_cache.txt"
                            $metrics_content = ""
                            try {
                                if (Test-Path $metrics_file) {
                                    $metrics_content = Get-Content -Path $metrics_file -Raw -ErrorAction Stop
                                    $metrics_content = ($metrics_content -replace "`r`n","`n" -replace "`r","`n").TrimStart([char]0xFEFF,"`n")
                                } else {
                                    $fallback = @'
# HELP eplan_licenses_total Total number of EPLAN licenses
# TYPE eplan_licenses_total gauge
eplan_licenses_total{bundle="no_data",module="no_data"} 0
# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use
# TYPE eplan_licenses_in_use gauge
eplan_licenses_in_use{bundle="no_data",module="no_data"} 0
# HELP eplan_licenses_borrow_issued Total number of borrow licenses issued
# TYPE eplan_licenses_borrow_issued gauge
eplan_licenses_borrow_issued{bundle="no_data",module="no_data"} 0
# HELP eplan_licenses_borrowed Number of licenses currently borrowed
# TYPE eplan_licenses_borrowed gauge
eplan_licenses_borrowed{bundle="no_data",module="no_data"} 0
# HELP eplan_licenses_free Number of free licenses available
# TYPE eplan_licenses_free gauge
eplan_licenses_free{bundle="no_data",module="no_data"} 0
'@
                                    $metrics_content = $fallback -replace "`r`n","`n"
                                }
                            } catch {
                                $fallback_error = @'
# HELP eplan_licenses_total Total number of EPLAN licenses
# TYPE eplan_licenses_total gauge
eplan_licenses_total{bundle="error",module="io"} 0
# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use
# TYPE eplan_licenses_in_use gauge
eplan_licenses_in_use{bundle="error",module="io"} 0
# HELP eplan_licenses_borrow_issued Total number of borrow licenses issued
# TYPE eplan_licenses_borrow_issued gauge
eplan_licenses_borrow_issued{bundle="error",module="io"} 0
# HELP eplan_licenses_borrowed Number of licenses currently borrowed
# TYPE eplan_licenses_borrowed gauge
eplan_licenses_borrowed{bundle="error",module="io"} 0
# HELP eplan_licenses_free Number of free licenses available
# TYPE eplan_licenses_free gauge
eplan_licenses_free{bundle="error",module="io"} 0
'@
                                $metrics_content = $fallback_error -replace "`r`n","`n"
                            }
                            $buffer = [System.Text.Encoding]::UTF8.GetBytes($metrics_content)
                            $response.StatusCode = 200
                            $response.ContentType = "text/plain; charset=utf-8"
                            $response.ContentLength64 = $buffer.Length
                            $response.OutputStream.Write($buffer, 0, $buffer.Length)
                            try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Responded /metrics with $($buffer.Length) bytes" } catch {}
                        } elseif ($path -eq "/" -or $path -eq "") {
                            $msg = "ok"
                            $buffer = [System.Text.Encoding]::UTF8.GetBytes($msg)
                            $response.StatusCode = 200
                            $response.ContentType = "text/plain; charset=utf-8"
                            $response.ContentLength64 = $buffer.Length
                            $response.OutputStream.Write($buffer, 0, $buffer.Length)
                            try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Responded / with OK" } catch {}
                        } else {
                            $error_msg = "404 - Use /metrics endpoint"
                            $buffer = [System.Text.Encoding]::UTF8.GetBytes($error_msg)
                            $response.StatusCode = 404
                            $response.ContentType = "text/plain"
                            $response.ContentLength64 = $buffer.Length
                            $response.OutputStream.Write($buffer, 0, $buffer.Length)
                            try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Responded 404 to $path" } catch {}
                        }
                    } catch {
                        try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Request error: $_" } catch {}
                    } finally {
                        try { if ($context -and $context.Response) { $context.Response.Close() } } catch {}
                    }
                }
            } catch {
                try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) Listener error: $_" } catch {}
            } finally {
                try { $listener.Stop() } catch {}
                try { $listener.Close() } catch {}
                try { Add-Content -Path $logFile -Value "$(Get-Date -Format o) HTTP job stopping" } catch {}
            }
        } -ArgumentList $Port

        Write-Host "EPLAN Prometheus Exporter gestartet auf Port $Port"
        Write-Host "Metrics verfügbar unter: http://<host>:$Port/metrics"
        
        return $true
    } catch {
        Write-Host "FEHLER beim Starten des HTTP-Servers: $_"
        Write-Host "HINWEIS: Für Remote-Zugriff ist ggf. URLACL (netsh) und Firewall-Regel nötig"
        return $false
    }
}

function Update-MetricsCache {
    $metrics_content = Get-PrometheusMetrics
    $cache_file = "D:\Test\eplan_metrics_cache.txt"
    try {
        $metrics_content | Out-File -FilePath $cache_file -Encoding UTF8 -Force
    } catch {
        Write-Host "WARNUNG: Konnte Metrics-Cache nicht schreiben: $_"
    }
    $cache_file = "D:\Test\eplan_metrics_cache.txt"
    $normalized = ($metrics_content -replace "`r`n","`n" -replace "`r","`n")
    [System.IO.File]::WriteAllText($cache_file, $normalized, [System.Text.UTF8Encoding]::new($false))
}

#-----------------------------------------------------
# MAIN SCRIPT EXECUTION
#-----------------------------------------------------

Write-Host "Starte EPLAN License Prometheus Exporter (Stable HttpListener Version)..."

# Server starten
if (!(Start-HttpServerSimple -Port 9094)) {
    Write-Host "FEHLER: Server konnte nicht gestartet werden. Beende Script."
    exit 1
}

# Initial Dummy-Metriken setzen
$global:eplan_metrics["initial|no_data"] = @{
    bundle = "no_data"
    module = "no_data"
    total = 0
    in_use = 0
    borrow_issued = 0
    borrowed = 0
    free = 0
    timestamp = Get-Date
}

Update-MetricsCache

try {
    $last_report_time = Get-Date
    
    Write-Host "Server läuft. Starte Monitoring-Loop..."
    
    while ($true) {
        # Report alle 30 Sekunden aktualisieren
        $current_time = Get-Date
        if (($current_time - $last_report_time).TotalSeconds -ge 30) {
            Write-Host "Aktualisiere EPLAN Lizenz-Daten..."
            $script_start = Get-Date
            
            Read-ReportFile
            Update-MetricsCache
            
            $last_report_time = Get-Date
            $elapsed = (Get-Date) - $script_start
            Write-Host "Report-Zyklus abgeschlossen in $([math]::Round($elapsed.TotalSeconds, 2)) Sekunden"
            Write-Host "Aktuelle Metriken: $($global:eplan_metrics.Count) Einträge"
        }
        
        # Kurze Pause zwischen Checks
        Start-Sleep -Milliseconds 1000
    }
} finally {
    Write-Host "Beende EPLAN License Monitor..."
    
    if ($global:http_job) {
        Stop-Job $global:http_job -Force
        Remove-Job $global:http_job -Force
    }
    
    if ($global:http_listener) {
        $global:http_listener.Stop()
        $global:http_listener.Close()
    }
    
    Write-Host "EPLAN License Monitor beendet"
}
