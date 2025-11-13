# Start frontend dev server with VITE_NBA_ENDPOINT set to backend on 8001
$repoRoot = (Get-Location).Path
$logsDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$frontendOut = Join-Path $logsDir 'frontend.env.out.log'
$frontendErr = Join-Path $logsDir 'frontend.env.err.log'
$cmd = 'cmd.exe'
$envLine = 'set VITE_NBA_ENDPOINT=http://localhost:8001 && npm run dev -- --host --port 3000'
Write-Host "Starting frontend with VITE_NBA_ENDPOINT=http://localhost:8001"
$proc = Start-Process -FilePath $cmd -ArgumentList @('/c', $envLine) -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru
Write-Host "Frontend PID: $($proc.Id)"
Write-Host "Logs: $frontendOut / $frontendErr"