<#
Start the Vite frontend dev server in a detached process on Windows.
Run from repository root: `./scripts/start_frontend_detached.ps1`
#>
param(
    [int]$Port = 3000
)

$repoRoot = (Get-Location).Path
$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$outFile = Join-Path $logDir "frontend.out.log"
$errFile = Join-Path $logDir "frontend.err.log"
$pidFile = Join-Path $logDir "frontend.pid"

Write-Host "Starting frontend (npm run dev) on port $Port with host binding"

# Use cmd.exe /c to run npm on Windows reliably and forward extra args to Vite
$cmd = "npm run dev -- --host --port $Port"
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -WorkingDirectory $repoRoot -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru

try {
    $proc.Id | Out-File -FilePath $pidFile -Encoding ascii -Force
    Write-Host "Frontend started (PID: $($proc.Id)). Logs: $outFile, $errFile"
} catch {
    Write-Host "Started frontend but failed to write PID file: $_"
}