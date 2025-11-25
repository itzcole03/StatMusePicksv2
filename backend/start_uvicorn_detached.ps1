# Start uvicorn in a detached process and write PID + logs
# Run from repository root: `./backend/start_uvicorn_detached.ps1`
param(
    [int]$Port = 8000,
    [string]$OllamaUrl = ''
)

$repoRoot = (Get-Location).Path
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Virtualenv python not found at $venvPy, using system python"
    $venvPy = "python"
}

$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$outFile = Join-Path $logDir "uvicorn.out.log"
$errFile = Join-Path $logDir "uvicorn.err.log"
$pidFile = Join-Path $logDir "uvicorn.pid"

$args = "-m uvicorn backend.main:app --host 127.0.0.1 --port $Port"

Write-Host "Starting uvicorn with: $venvPy $args"
if ($OllamaUrl -and $OllamaUrl.Trim() -ne '') {
    Write-Host "Setting OLLAMA_URL=$OllamaUrl for process"
    $env:OLLAMA_URL = $OllamaUrl
}
$proc = Start-Process -FilePath $venvPy -ArgumentList $args -NoNewWindow -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru

# Save PID
try {
    $proc.Id | Out-File -FilePath $pidFile -Encoding ascii -Force
    Write-Host "Uvicorn started (PID: $($proc.Id)). Logs: $outFile, $errFile"
} catch {
    Write-Host "Started uvicorn but failed to write PID file: $_"
}
