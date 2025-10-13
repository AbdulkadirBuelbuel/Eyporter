$eplanLic_path = "C:\Eplan"
$syntegon_current_xml = "$eplanLic_path\Syntegon_Current.xml"

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
    }
    PROCESS {
        $lines = Get-Content -Path $file_to_read
        foreach ($line in $lines) {
            if ($start_reading) {
                $columns = $line.Split("`t")
                $total_issued = $columns[1]
                $total_license_in_use = $columns[2]
                $bundle = $columns[6]
                $module = $columns[7]
                $measurement = $columns[0]
                $ger_time = (Get-Date $measurement).ToString("yyyy.MM.dd HH:mm")
                $measurement = $ger_time
                eplan_lic_db_update -measurement $measurement -bundle $bundle -module $module -total_issued $total_issued -total_license_in_use $total_license_in_use
            }
            elseif ($line.StartsWith("Time")) {
                $start_reading = $True
            }
        }
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
    BEGIN {
        $sql_connection = New-Object System.Data.SQLClient.SQLConnection
        $sql_connection.ConnectionString=("Data Source=bngcaxreporting.patec.group;Initial Catalog=PACB_ICO_CAx_Reporting;Integrated Security=SSPI")
        $sql_connection.open()
        $sql_command = New-Object System.Data.SQLClient.SQLCommand
    }
    PROCESS {
        $sql_command.CommandText = "INSERT INTO [PACB_ICO_CAx_Reporting].[service].[LicenseMonitorEPLAN] (Time, BundleName, ModuleName, NumberOfLicenses, LicensesInUse) VALUES ('$measurement', '$bundle', '$module', '$total_issued', '$total_license_in_use')"
        #Write-Host $sql_command.CommandText
        $sql_command.Connection = $sql_connection
        $sql_command.ExecuteScalar()
    }
    END {
        $sql_connection.close()
    }
}



#-----------------------------------------------------
create-license-report
read_file