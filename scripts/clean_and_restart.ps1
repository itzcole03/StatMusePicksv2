# Stop likely leftover PIDs and restart services using start_detached_services.ps1
$knownPids = @(43972,24136)
foreach ($pid in $knownPids) {
    try {
        $p = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host "Stopping PID $pid ($($p.ProcessName))"
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "PID $pid not running"
        }
    } catch {
        Write-Host "Error stopping PID $pid: $($_.Exception.Message)"
    }
}

# Restart services script
Write-Host "Restarting detached services..."
& .\scripts\start_detached_services.ps1
