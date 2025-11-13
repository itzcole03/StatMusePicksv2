<#
Run Alembic migrations for the backend.

Usage (PowerShell):
  . .\.venv\Scripts\Activate.ps1
  ./backend/scripts/run_migrations.ps1

This will run `alembic -c backend/alembic.ini upgrade head` using the
current virtualenv Python. Ensure dependencies are installed.
#>

Write-Host "Running backend migrations..."

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Virtualenv not found at .venv; create and install requirements first." -ForegroundColor Yellow
    exit 1
}

. .\.venv\Scripts\Activate.ps1

 # Set a sensible default for dev. Use async sqlite URL since the app uses aiosqlite.
 # Allow an already-set env var to override.
 if (-not $env:DATABASE_URL -or $env:DATABASE_URL -eq '') {
   $env:DATABASE_URL = 'sqlite+aiosqlite:///./dev.db'
   Write-Host "DATABASE_URL not set; using default: $env:DATABASE_URL"
 } else {
   Write-Host "Using DATABASE_URL from environment: $env:DATABASE_URL"
 }

python -m alembic -c backend/alembic.ini upgrade head

if ($LASTEXITCODE -eq 0) { Write-Host "Migrations applied." } else { Write-Host "Migrations failed." -ForegroundColor Red; exit 1 }
