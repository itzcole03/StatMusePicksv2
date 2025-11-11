<#
Simple developer setup script for Windows PowerShell.
Usage:
  .\scripts\dev_setup.ps1          # run non-interactively (may prompt for elevation)
  .\scripts\dev_setup.ps1 -DryRun  # print planned steps without executing
#>
param(
    [switch]$DryRun
)

function Run-Plan([string]$description, [ScriptBlock]$action) {
    Write-Host "-- $description --"
    if ($DryRun) {
        Write-Host "DryRun: would execute: $($action.ToString())"
    } else {
        & $action
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Command failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
    }
}

$repoRoot = (Get-Location).Path
Write-Host "Repo root: $repoRoot"

# 1) Create venv if missing
$venvActivate = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
    Run-Plan "Create Python venv (.venv)" { python -m venv .venv }
} else {
    Write-Host "Virtualenv already exists: .venv"
}

# 2) Activate venv in this shell
Write-Host "Activating venv..."
if ($DryRun) {
    Write-Host ('DryRun: would run: & ' + $venvActivate)
} else {
    & $venvActivate
}

# 3) Install Python requirements (backend)
$reqFile = Join-Path $repoRoot 'backend\requirements.txt'
<#
Simple developer setup script for Windows PowerShell.
Usage:
  .\scripts\dev_setup.ps1          # run non-interactively (may prompt for elevation)
  .\scripts\dev_setup.ps1 -DryRun  # print planned steps without executing
#>
param(
    [switch]$DryRun
)

$repoRoot = (Get-Location).Path
Write-Host "Repo root: $repoRoot"

# Paths
$venvActivate = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
$reqFile = Join-Path $repoRoot 'backend\requirements.txt'

function Run-OrPrint([string]$desc, [string]$cmd, [switch]$isCmd) {
    Write-Host "-- $desc --"
    if ($DryRun) {
        Write-Host ('DryRun: would run: ' + $cmd)
    } else {
        try {
            if ($isCmd) {
                iex $cmd
            } else {
                & $cmd
            }
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Command failed with exit code $LASTEXITCODE"
                exit $LASTEXITCODE
            }
        } catch {
            Write-Error "Failed to run: $cmd`n$($_.Exception.Message)"
            exit 1
        }
    }
}

# 1) Create venv if missing
if (-not (Test-Path $venvActivate)) {
    Run-OrPrint 'Create Python venv (.venv)' 'python -m venv .venv' -isCmd
} else {
    Write-Host 'Virtualenv already exists: .venv'
}

# 2) Activate venv in this shell
Write-Host 'Activating venv...'
if ($DryRun) {
    Write-Host ('DryRun: would run: & ' + $venvActivate)
} else {
    & $venvActivate
}

# 3) Install Python requirements (backend)
if (Test-Path $reqFile) {
    Run-OrPrint 'Install Python requirements (backend)' 'pip install -r "backend\requirements.txt"' -isCmd
} else {
    Write-Host 'No backend requirements file found at backend/requirements.txt — skipping pip install.'
}

# 4) Install frontend deps
Run-OrPrint 'Install frontend dependencies (npm install)' 'npm install' -isCmd

# 5) Show dev start commands
Write-Host ''
Write-Host 'Dev start commands (run manually):'
Write-Host '# Start backend:'
Write-Host '& .\.venv\Scripts\Activate.ps1 ; $env:PYTHONPATH = (Get-Location).Path ; python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000'
Write-Host '# Start frontend (interactive):'
Write-Host 'npm run dev -- --host --port 3000'
Write-Host '# Or use helper to start frontend detached: .\scripts\run_restart_frontend.ps1'

Write-Host ''
Write-Host 'Done. If you ran with -DryRun, nothing was executed.'
