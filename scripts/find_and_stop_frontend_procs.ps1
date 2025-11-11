# Find processes likely to be the frontend (npm/vite/node) started in this repo and stop them
$repoRoot = (Get-Location).Path
Write-Host "Repo root: $repoRoot"
$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'vite' -or $_.CommandLine -match 'npm run dev' -or $_.CommandLine -match 'node') -and ($_.CommandLine -match [regex]::Escape($repoRoot)) } 
if (-not $procs) { Write-Host 'No matching frontend processes found' ; exit 0 }
foreach ($p in $procs) {
    Write-Host "Found PID $($p.ProcessId) Name $($p.Name)"
    Write-Host "Cmd: $($p.CommandLine)"
    try {
        Write-Host ('Stopping PID ' + $p.ProcessId)
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host ('Stopped PID ' + $p.ProcessId)
    } catch {
        Write-Host ('Failed to stop PID ' + $p.ProcessId + ': ' + $_.Exception.Message)
    }
}
Write-Host 'Done'
