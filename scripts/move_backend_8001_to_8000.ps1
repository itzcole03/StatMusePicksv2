# Stop backend processes bound to port 8001, start backend on port 8000, wait for /health, run smoke test
$ErrorActionPreference = 'Stop'
$repoRoot = (Get-Location).Path
Write-Host "Repo root: $repoRoot"

# Find processes with 8001 in their command line
$matches = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match '\b8001\b') }
if (-not $matches) {
    Write-Host 'No processes with 8001 in command line found.'
} else {
    foreach ($p in $matches) {
        Write-Host ('Found PID ' + $p.ProcessId + ' Name ' + $p.Name)
        Write-Host ('Cmd: ' + $p.CommandLine)
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host ('Stopped PID ' + $p.ProcessId)
        } catch {
            Write-Host ('Failed to stop PID ' + $p.ProcessId + ': ' + $_.Exception.Message)
        }
    }
}

# Ensure logs directory
$logsDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

# Start backend on port 8000 using centralized script
$startScript = Join-Path $repoRoot 'scripts\start_backend.ps1'
if (-not (Test-Path $startScript)) { Write-Error "Start script not found: $startScript"; exit 2 }
Write-Host "Starting backend on port 8000 via $startScript"
& $startScript -Port 8000 -WaitForHealth
Write-Host 'Started backend via start_backend.ps1'

# Wait for /health
$uri = 'http://127.0.0.1:8000/health'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
        Write-Host ('Backend ready: ' + ($r | Out-String))
        $ready = $true
        break
    } catch {
        Write-Host ('Waiting for backend... (' + $i + ')')
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) { Write-Error 'Backend did not become ready in time on port 8000'; exit 1 }

# Run smoke test (Python script targets port 8000)
Write-Host 'Running smoke test scripts/check_predict.py'
try {
    & $pythonExe (Join-Path $repoRoot 'scripts\check_predict.py')
} catch {
    Write-Host ('Smoke test failed: ' + $_.Exception.Message)
    exit 1
}

Write-Host 'Done.'
