# Find processes listening on port 3000 and stop them
$matches = netstat -ano | Select-String ':3000' | ForEach-Object { $_.Line }
if (-not $matches) {
    Write-Host 'No listeners on :3000'
    exit 0
}

Write-Host "Found netstat lines for :3000:`n"
$matches | ForEach-Object { Write-Host $_ }

$ids = @()
foreach ($line in $matches) {
    # split on whitespace and take last token as PID
    $parts = -split $line
    $pid = $parts[-1]
    if ($pid -and $pid -match '^[0-9]+$') { $ids += [int]$pid }
}
$ids = $ids | Sort-Object -Unique
if (-not $ids) { Write-Host 'No valid PID found'; exit 0 }

foreach ($pid in $ids) {
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid" -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "PID $pid -> $($proc.Name)"
            Write-Host "CommandLine: $($proc.CommandLine)"
            Write-Host "Stopping PID $pid..."
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped PID $pid"
        } else {
            Write-Host "No process info for PID $pid"
        }
    } catch {
        Write-Host ('Error handling PID ' + $pid + ': ' + $_.Exception.Message)
    }
}

Write-Host 'Done.'
