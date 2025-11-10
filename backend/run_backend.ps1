<#
PowerShell helper to create venv (if missing) and run the backend.
Run from repository root: `./backend/run_backend.ps1`
#>

if (-not (Test-Path -Path ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

Write-Host "Installing requirements (if needed)..."
pip install -r backend\requirements.txt

Write-Host "Starting uvicorn (backend.main:app) on port 8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
