# Start frontend (detached) and tail recent log lines
$repoRoot = (Get-Location).Path
$logsDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$out = Join-Path $logsDir 'frontend.out.log'
$err = Join-Path $logsDir 'frontend.err.log'

Write-Host "Starting frontend (detached)..."
$proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev -- --host --port 3000' -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Write-Host "Started frontend PID: $($proc.Id)"

Start-Sleep -Seconds 2
if (Test-Path $out) {
    Write-Host (Get-Content $out -Tail 80 | Out-String)
} else {
    Write-Host 'No frontend.out.log yet'
}
