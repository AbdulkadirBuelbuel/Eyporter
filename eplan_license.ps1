$eplanLic_path = "D:\Install\SolidWorks_exporter\Eplan_exporter"
$syntegon_current_xml = "$eplanLic_path\Syntegon_Current.xml"

# Verzeichnisse erstellen falls nicht vorhanden
if (!(Test-Path $eplanLic_path)) {
    New-Item -ItemType Directory -Path $eplanLic_path -Force | Out-Null
}
if (!(Test-Path "C:\Temp")) {
    New-Item -ItemType Directory -Path "C:\Temp" -Force | Out-Null
}

function create-license-report {
    BEGIN {
        $elmon_command = "C:\Program Files\EPLAN\ECT\ElmMonitor.exe"
		$args = "/Createreport /Servername:lic-eplan-emea.patec.group /Xmlfile:$syntegon_current_xml /Timezone:CET /Lasthours:1 /Lang:1031 /Silent"
        $elm_monitor = "C:\Program Files\EPLAN\ECT\ElmMonitor.exe"
    }
    PROCESS {
        Start-Process -FilePath $elmon_command -ArgumentList $args -Wait
        #Start-Process -FilePath $elm_monitor
    }
    END {

    }
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

# TCP-Server (benötigt keine Admin-Rech