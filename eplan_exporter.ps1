$eplanLic_path = "C:\Eplan"
$syntegon_current_xml = "$eplanLic_path\Syntegon_Current.xml"

# Verzeichnisse erstellen falls nicht vorhanden
if (!(Test-Path $eplanLic_path)) {
    New-Item -ItemType Directory -Path $eplanLic_path -Force | Out-Null
}
if (!(Test-Path "C:\Temp")) {
    New-Item -ItemType Directory -Path "C:\Temp" -Force | Out-Null
}

function read_file {
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
                        $bundle = $columns[6]
                        $module = $columns[7]
                        $measurement = $columns[0]
                        $ger_time = (Get-Date $measurement).ToString("yyyy.MM.dd HH:mm")
                        $measurement = $ger_time
                        eplan_lic_db_update -measurement $measurement -bundle $bundle -module $module -total_issued $total_issued -total_license_in_use $total_license_in_use
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

# Globale Metriken-Sammlung
$global:eplan_metrics = @{}
$global:tcp_listener = $null

function eplan_lic_prometheus_update {
    param (
        [String]$measurement, 
        [String]$bundle, 
        [String]$module, 
        [String]$total_issued, 
        [String]$total_license_in_use
    )
    
    $bundle_clean = ($bundle -replace '"', '\"' -replace '\\', '\\' -replace '\n', ' ' -replace '\r', '').Trim()
    $module_clean = ($module -replace '"', '\"' -replace '\\', '\\' -replace '\n', ' ' -replace '\r', '').Trim()
    
    if ([string]::IsNullOrWhiteSpace($bundle_clean)) { $bundle_clean = "unknown" }
    if ([string]::IsNullOrWhiteSpace($module_clean)) { $module_clean = "unknown" }
    
    try { $total = [int]$total_issued } catch { $total = 0 }
    try { $in_use = [int]$total_license_in_use } catch { $in_use = 0 }
    
    $key = "$bundle_clean|$module_clean"
    
    $global:eplan_metrics[$key] = @{
        bundle = $bundle_clean
        module = $module_clean
        total = $total
        in_use = $in_use
        timestamp = Get-Date
    }
}

function eplan_lic_db_update {
    param (
        [String]$measurement, 
        [String]$bundle, 
        [String]$module, 
        [String]$total_issued, 
        [String]$total_license_in_use
    )
    
    eplan_lic_prometheus_update -measurement $measurement -bundle $bundle -module $module -total_issued $total_issued -total_license_in_use $total_license_in_use
}

function New-MetricsText {
    $t = "# HELP eplan_licenses_total Total number of EPLAN licenses`n"
    $t += "# TYPE eplan_licenses_total gauge`n"
    $t += "# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use`n"
    $t += "# TYPE eplan_licenses_in_use gauge`n"
    if ($global:eplan_metrics.Count -eq 0) {
        $t += "eplan_licenses_total{bundle=`"no_data`",module=`"no_data`"} 0`n"
        $t += "eplan_licenses_in_use{bundle=`"no_data`",module=`"no_data`"} 0`n"
    } else {
        foreach ($k in $global:eplan_metrics.Keys) {
            $m = $global:eplan_metrics[$k]
            $t += "eplan_licenses_total{bundle=`"$($m.bundle)`",module=`"$($m.module)`"} $($m.total)`n"
            $t += "eplan_licenses_in_use{bundle=`"$($m.bundle)`",module=`"$($m.module)`"} $($m.in_use)`n"
        }
    }
    return $t
}

function Update-MetricsCache {
    $cache = "C:\Temp\eplan_metrics_cache.txt"
    try {
        New-MetricsText | Out-File -FilePath $cache -Encoding UTF8 -Force
    } catch {}
}

#-----------------------------------------------------
# Stabiler HTTP-Server via HttpListener (Background-Job, localhost)
$port = 9094

# HTTP Listener im Hintergrundjob starten (nur localhost Bindings)
$global:http_job = Start-Job -ScriptBlock {
    param($Port)
    $listener = $null
    try {
        $listener = New-Object System.Net.HttpListener
        $listener.Prefixes.Clear()
        $listener.Prefixes.Add("http://localhost:$Port/")
        $listener.Prefixes.Add("http://127.0.0.1:$Port/")
        $listener.Start()
        while ($listener.IsListening) {
            $context = $null
            try {
                $context = $listener.GetContext()
                $req = $context.Request
                $res = $context.Response
                $res.KeepAlive = $false
                $res.SendChunked = $false
                $path = $req.Url.AbsolutePath.ToLowerInvariant()
                if ($path -eq "/metrics") {
                    $metrics_file = "C:\Temp\eplan_metrics_cache.txt"
                    $metrics_content = ""
                    try {
                        if (Test-Path $metrics_file) { $metrics_content = Get-Content -Raw -Path $metrics_file -ErrorAction Stop }
                        else {
                            $metrics_content = "# HELP eplan_licenses_total Total number of EPLAN licenses`n# TYPE eplan_licenses_total gauge`neplan_licenses_total{bundle=`"no_data`",module=`"no_data`"} 0`n# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use`n# TYPE eplan_licenses_in_use gauge`neplan_licenses_in_use{bundle=`"no_data`",module=`"no_data`"} 0`n"
                        }
                    } catch {
                        $metrics_content = "# HELP eplan_licenses_total Total number of EPLAN licenses`n# TYPE eplan_licenses_total gauge`neplan_licenses_total{bundle=`"error`",module=`"io`"} 0`n# HELP eplan_licenses_in_use Number of EPLAN licenses currently in use`n# TYPE eplan_licenses_in_use gauge`neplan_licenses_in_use{bundle=`"error`",module=`"io`"} 0`n"
                    }
                    $buf = [System.Text.Encoding]::UTF8.GetBytes($metrics_content)
                    $res.StatusCode = 200
                    $res.ContentType = "text/plain; version=0.0.4; charset=utf-8"
                    $res.ContentLength64 = $buf.Length
                    $res.OutputStream.Write($buf, 0, $buf.Length)
                } elseif ($path -eq "/" -or $path -eq "") {
                    $msg = "ok"
                    $buf = [System.Text.Encoding]::UTF8.GetBytes($msg)
                    $res.StatusCode = 200
                    $res.ContentType = "text/plain; charset=utf-8"
                    $res.ContentLength64 = $buf.Length
                    $res.OutputStream.Write($buf, 0, $buf.Length)
                } else {
                    $msg = "404 - Use /metrics endpoint"
                    $buf = [System.Text.Encoding]::UTF8.GetBytes($msg)
                    $res.StatusCode = 404
                    $res.ContentType = "text/plain; charset=utf-8"
                    $res.ContentLength64 = $buf.Length
                    $res.OutputStream.Write($buf, 0, $buf.Length)
                }
            } catch {
            } finally {
                try { if ($context -and $context.Response) { $context.Response.Close() } } catch {}
            }
        }
    } catch {
    } finally {
        try { if ($listener) { $listener.Stop(); $listener.Close() } } catch {}
    }
} -ArgumentList $port

# Initial Dummy-Metriken setzen
if (-not $global:eplan_metrics) { $global:eplan_metrics = @{} }
if ($global:eplan_metrics.Count -eq 0) {
    $global:eplan_metrics["initial|no_data"] = @{ bundle = "no_data"; module = "no_data"; total = 0; in_use = 0; timestamp = Get-Date }
}

# Erste Cache-Erstellung
Update-MetricsCache

# Hauptloop: Datei lesen und Cache alle 30s aktualisieren
try {
    $last_report_time = Get-Date
    while ($true) {
        $now = Get-Date
        if (($now - $last_report_time).TotalSeconds -ge 30) {
            read_file
            Update-MetricsCache
            $last_report_time = $now
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    if ($global:http_job) { try { Stop-Job $global:http_job -Force } catch {}; try { Remove-Job $global:http_job -Force } catch {} }
    Write-Host "EPLAN License Monitor beendet"
}