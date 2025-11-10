<#
Runs the backend locally in a venv or via Docker Compose (if you prefer), waits for /health, then runs the prompt builder script.

Usage:
  # Run venv backend then prompt builder
  .\scripts\run_local_backend_and_prompt.ps1 -Mode venv -Player "LeBron James" -Stat points -Limit 5

  # Run docker-compose backend then prompt builder
  .\scripts\run_local_backend_and_prompt.ps1 -Mode docker -Player "LeBron James"
#>

param(
  [ValidateSet('venv','docker')]
  [string]$Mode = 'venv',
  [string]$Player = 'LeBron James',
  [string]$Stat = 'points',
  [int]$Limit = 5,
  [int]$TimeoutSeconds = 60
)

function Wait-ForHealth($url, $timeoutSeconds=60) {
  $start = Get-Date
  while ((Get-Date) - $start -lt (New-TimeSpan -Seconds $timeoutSeconds)) {
    try {
      $r = Invoke-RestMethod -Uri $url -UseBasicParsing -ErrorAction Stop
      if ($r -and $r.ok) { return $true }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  return $false
}

if ($Mode -eq 'venv') {
  Push-Location -Path (Join-Path $PSScriptRoot '..\backend')
  if (-not (Test-Path '.venv')) {
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
  }

  # Start backend in background
  $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
  $proc = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','fastapi_nba:app','--host','127.0.0.1','--port','3002' -PassThru -NoNewWindow
  Pop-Location

  Write-Host 'Waiting for backend /health ...'
  if (-not (Wait-ForHealth 'http://127.0.0.1:3002/health' $TimeoutSeconds)) {
    Write-Error 'Backend did not become healthy in time.'; exit 2
  }
} else {
  Write-Host 'Starting via docker compose (requires Docker).'
  docker compose up -d --build backend
  Write-Host 'Waiting for backend /health ...'
  if (-not (Wait-ForHealth 'http://127.0.0.1:3002/health' $TimeoutSeconds)) {
    Write-Error 'Backend did not become healthy in time.'; exit 2
  }
}

# Run prompt builder
Write-Host 'Running prompt builder...'
node scripts/fetch_and_build_prompt.cjs "$Player" $Stat $Limit

Write-Host 'Done.'
