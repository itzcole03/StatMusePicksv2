# Start backend and frontend as background PowerShell jobs, wait for backend readiness,
# run the prediction smoke test, and run `npm audit`.
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Get-Location).Path
Write-Host "Repo root: $repoRoot"

# Start backend via centralized start script as a job
Write-Host "Starting backend as background job via scripts/start_backend.ps1..."
$startScript = Join-Path $repoRoot 'scripts\start_backend.ps1'
if (-not (Test-Path $startScript)) { Write-Error "Start script not found: $startScript"; exit 2 }
$backendJob = Start-Job -ScriptBlock { & $using:startScript -Port 8000 } 
Write-Host "Backend job id: $($backendJob.Id)"

# Start frontend as a job
Write-Host "Starting frontend (Vite) as background job..."
$frontendJob = Start-Job -ScriptBlock { npm run dev -- --host --port 3000 }
Write-Host "Frontend job id: $($frontendJob.Id)"

# Wait for backend /health
$uri = 'http://127.0.0.1:8000/health'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
        Write-Host "Backend ready: $($r)"
        $ready = $true
        break
    } catch {
        Write-Host "Waiting for backend... ($i)"
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Error "Backend did not become ready in time. Check logs or jobs with Get-Job and Receive-Job." 
    exit 1
}

# Run the existing Python smoke test script
Write-Host "Running prediction smoke test script..."
try {
    & "$(Join-Path $repoRoot '.venv\Scripts\python.exe')" "$(Join-Path $repoRoot 'scripts\check_predict.py')"
} catch {
    Write-Error "Smoke test failed: $($_.Exception.Message)"
}

# Run npm audit
Write-Host "Running npm audit (report only)..."
try {
    npm audit --audit-level=low
} catch {
    Write-Host "npm audit returned non-zero exit code or no audit data. You can run 'npm audit' manually for details."
}

Write-Host "Done. Use Get-Job to inspect background jobs and Receive-Job -Id <id> to tail output."