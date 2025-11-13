$pidFile = Join-Path (Get-Location) 'logs\frontend.pid'
if (Test-Path $pidFile) {
    try {
        $pid = Get-Content $pidFile
        if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
            Stop-Process -Id $pid -Force
            Write-Host "Stopped process $pid"
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    } catch {
        Write-Host "No running frontend process found or failed to stop: $_"
    }
} else {
    Write-Host "No PID file found."
}
Write-Host "Starting updated detached frontend script"
& .\scripts\start_frontend_detached.ps1 -Port 3000
