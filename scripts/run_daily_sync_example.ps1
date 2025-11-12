<#
Idempotent runner for scheduled ingestion.

Features:
- Simple filesystem lock to avoid overlapping runs (stale-lock detection).
- Activates the repository virtualenv if not already active.
- Writes output to a log file under `logs/run_daily_sync.log`.
- Exits early when a recent lock is present (configurable max runtime).

Usage (manual):
. .\.venv\Scripts\Activate.ps1
pwsh .\scripts\run_daily_sync_example.ps1

Recommended for Task Scheduler: schedule this PowerShell script to run daily.
#>

$ErrorActionPreference = 'Stop'

# Resolve repo paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

$LockFile = Join-Path $env:TEMP "run_daily_sync.lock"
$MaxRunMinutes = [int]($env:INGEST_RUN_MAX_MINUTES -as [int] -or 120)

function Acquire-Lock {
    if (Test-Path $LockFile) {
        try {
            $age = (Get-Date) - (Get-Item $LockFile).LastWriteTime
            if ($age.TotalMinutes -lt $MaxRunMinutes) {
                Write-Host "Another run is in progress (lock present and $([int]$age.TotalMinutes) minutes old). Exiting.";
                return $false
            }
            else {
                Write-Host "Stale lock detected (older than $MaxRunMinutes minutes). Removing and continuing."
                Remove-Item $LockFile -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Warning "Could not inspect lock file; proceeding cautiously. $_"
        }
    }
    try {
        "$($PID) `n$(Get-Date -Format o)" | Out-File -FilePath $LockFile -Encoding utf8 -Force
        return $true
    } catch {
        Write-Warning "Failed to create lock file: $_"
        return $false
    }
}

function Release-Lock {
    try { Remove-Item $LockFile -ErrorAction SilentlyContinue } catch {}
}

if (-not (Acquire-Lock)) { exit 0 }

try {
    # Ensure audit dir is set and writable
    $env:INGEST_AUDIT_DIR = (Resolve-Path (Join-Path $RepoRoot 'backend' 'ingest_audit') -ErrorAction SilentlyContinue).Path
    if (-not $env:INGEST_AUDIT_DIR) {
        $env:INGEST_AUDIT_DIR = Join-Path $RepoRoot 'backend' 'ingest_audit'
        New-Item -ItemType Directory -Path $env:INGEST_AUDIT_DIR -Force | Out-Null
    }

    # Activate virtualenv if needed (prefer repo .venv)
    $pythonCmd = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $pythonCmd -or ($pythonCmd.Source -notlike "*\\.venv\\*")) {
        $venvActivate = Join-Path $RepoRoot '.venv\Scripts\Activate.ps1'
        if (Test-Path $venvActivate) {
            Write-Host "Activating virtualenv at $venvActivate"
            . $venvActivate
        } else {
            Write-Warning "Virtualenv activate not found at $venvActivate. Ensure an environment with dependencies is available."
        }
    }

    $LogFile = Join-Path $LogsDir "run_daily_sync.log"
    $start = Get-Date
    "$start - Starting run_daily_sync" | Out-File -FilePath $LogFile -Append -Encoding utf8

    # Run ingestion in a subprocess and capture output
    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) { throw "python not found in PATH; ensure venv is activated or python is installed." }

    $script = @'
from datetime import date
from backend.services import data_ingestion_service as dis
res = dis.run_daily_sync(when=date.today())
print(res)
'@

    & $pythonExe - <<"PY" 2>&1 | ForEach-Object { $_ | Out-File -FilePath $LogFile -Append -Encoding utf8 }
$script
    $end = Get-Date
    "$end - Finished run_daily_sync (duration: $([int]($end - $start).TotalSeconds)s)" | Out-File -FilePath $LogFile -Append -Encoding utf8

} catch {
    $err = $_.Exception.Message
    "$(Get-Date) - ERROR: $err" | Out-File -FilePath $LogFile -Append -Encoding utf8
    throw
} finally {
    Release-Lock
}

Write-Host "Done. Log: $LogFile`nAudit dir: $env:INGEST_AUDIT_DIR"
