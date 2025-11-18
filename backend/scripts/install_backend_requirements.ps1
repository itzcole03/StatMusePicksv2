<#
Install backend Python requirements into the current venv.

Usage (PowerShell):
  & .\.venv\Scripts\Activate.ps1; .\backend\scripts\install_backend_requirements.ps1
#>
try {
    if (-not (Test-Path -Path ".\.venv\Scripts\Activate.ps1")) {
        Write-Host "No .venv found in repo root. Create one with: python -m venv .venv" -ForegroundColor Yellow
    }
    Write-Host "Installing backend requirements from backend/requirements.txt..."
    python -m pip install --upgrade pip
    python -m pip install -r backend/requirements.txt
    Write-Host "Backend requirements installed." -ForegroundColor Green
} catch {
    Write-Host "Failed to install requirements: $_" -ForegroundColor Red
    exit 1
}
