# Start backend and frontend as detached processes with log files.
param()
$repoRoot = (Get-Location).Path
$logsDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

# Backend (use centralized start script)
$startScript = Join-Path $repoRoot 'scripts\start_backend.ps1'
if (-not (Test-Path $startScript)) { Write-Error "Start script not found: $startScript"; exit 2 }
$backendOut = Join-Path $logsDir 'backend8000.out.log'
$backendErr = Join-Path $logsDir 'backend8000.err.log'
Write-Host "Starting backend via $startScript"
$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -Port 8000"
$backendProc = Start-Process -FilePath 'powershell' -ArgumentList $psArgs -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
Write-Host "Backend PID: $($backendProc.Id)";

# Frontend
$cmdExe = 'cmd.exe'
$frontendOut = Join-Path $logsDir 'frontend.out.log'
$frontendErr = Join-Path $logsDir 'frontend.err.log'
Write-Host "Starting frontend using cmd.exe -> npm"
# Use cmd.exe /c to run npm (npm is a shell shim on Windows)
$frontendProc = Start-Process -FilePath $cmdExe -ArgumentList @('/c','npm run dev -- --host --port 3000') -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru
Write-Host "Frontend PID: $($frontendProc.Id)";

Write-Host "Started processes. Tail logs with: Get-Content $backendOut -Wait"