<#
Build and run backend image locally for dev verification, then run smoke checks.

Usage (PowerShell):
  . .\.venv\Scripts\Activate.ps1
  ./scripts/docker_dev_verify.ps1

This script will build the backend image, run it detached on port 3002, wait for /health,
hit /api/models and then stop the container.
#>

Write-Host "Building backend Docker image..."
docker build -t statmuse_backend:dev ./backend
if ($LASTEXITCODE -ne 0) { Write-Host "Docker build failed" -ForegroundColor Red; exit 1 }

Write-Host "Starting backend container..."
docker run -d --name statmuse_backend_dev -p 3002:3002 -e DATABASE_URL='sqlite+aiosqlite:///./dev.db' statmuse_backend:dev
Start-Sleep -Seconds 2

$ok = $false
for ($i=0; $i -lt 20; $i++) {
  try {
    $r = Invoke-RestMethod -Uri http://127.0.0.1:3002/health -Method Get -TimeoutSec 2 -ErrorAction Stop
    if ($r -and $r.status) { $ok = $true; break }
  } catch { Start-Sleep -Seconds 1 }
}

if (-not $ok) {
  Write-Host "Backend did not become healthy in time." -ForegroundColor Red
  docker logs statmuse_backend_dev
  docker rm -f statmuse_backend_dev | Out-Null
  exit 1
}

Write-Host "Backend healthy; running smoke checks..."
try {
  Invoke-RestMethod -Uri http://127.0.0.1:3002/api/models -Method Get | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri 'http://127.0.0.1:3002/api/models/load?player=synthetic_player' -Method Post | ConvertTo-Json -Depth 5
} catch {
  Write-Host "Smoke checks failed: $_" -ForegroundColor Red
}

Write-Host "Stopping and removing container..."
docker rm -f statmuse_backend_dev | Out-Null
Write-Host "Done."
