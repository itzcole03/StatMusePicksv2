# Start backend on port 8001 via centralized start script
$repoRoot = (Get-Location).Path
$startScript = Join-Path $repoRoot 'scripts\start_backend.ps1'
if (-not (Test-Path $startScript)) { Write-Error "Start script not found: $startScript"; exit 2 }
Write-Host "Invoking $startScript -Port 8001"
& $startScript -Port 8001