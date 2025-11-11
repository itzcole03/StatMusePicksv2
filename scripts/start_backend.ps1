<#
.SYNOPSIS
  Start the backend (uvicorn) from the project's venv and write logs.

.PARAMETER Port
  Port to start uvicorn on (default 8000).

.PARAMETER WaitForHealth
  If supplied, the script will poll /health for up to 30s and exit non-zero if not ready.

USAGE:
  .\scripts\start_backend.ps1 -Port 8000 -WaitForHealth
#>

param(
    [int]$Port = 8000,
    [switch]$WaitForHealth
)

Set-StrictMode -Version Latest

$root = (Resolve-Path "$PSScriptRoot\.." -ErrorAction Stop).ProviderPath
$logsDir = Join-Path $root 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error "Python not found at $python. Activate venv or create it with scripts/dev_setup.ps1"
    exit 2
}

$stdout = Join-Path $logsDir ("backend{0}.out.log" -f $Port)
$stderr = Join-Path $logsDir ("backend{0}.err.log" -f $Port)

$args = "-m uvicorn backend.main:app --host 127.0.0.1 --port $Port"

Write-Output "Starting backend on port $Port (logs: $stdout, $stderr)"
$p = Start-Process -FilePath $python -ArgumentList $args -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -PassThru
Write-Output "Started PID: $($p.Id)"

if ($WaitForHealth) {
    $uri = "http://127.0.0.1:$Port/health"
    $max = 30
    for ($i = 0; $i -lt $max; $i++) {
        try {
            $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
            if ($r.ok -eq $true) { Write-Output "HEALTH:OK"; exit 0 }
        } catch { }
        Start-Sleep -Seconds 1
    }
    Write-Error "HEALTH:FAILED after $max seconds"
    exit 1
}

exit 0
