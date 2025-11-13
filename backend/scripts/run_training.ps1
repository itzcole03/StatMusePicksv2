<#
Run the example training script to generate a synthetic model (dev only).

Usage (PowerShell):
  . .\.venv\Scripts\Activate.ps1
  ./backend/scripts/run_training.ps1

This trains a tiny synthetic model and writes it to `backend/models_store/`.
#>

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Virtualenv not found at .venv; create and install requirements first." -ForegroundColor Yellow
    exit 1
}

. .\.venv\Scripts\Activate.ps1

Write-Host "Training synthetic model (writes to backend/models_store/)"
python backend/scripts/train_example.py

if ($LASTEXITCODE -eq 0) { Write-Host "Training finished." } else { Write-Host "Training failed." -ForegroundColor Red; exit 1 }
