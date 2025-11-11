$procs = Get-Process -Name python -ErrorAction SilentlyContinue
if (-not $procs) {
    Write-Host "No python processes found via Get-Process"
} else {
    foreach ($p in $procs) {
        try { $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine } catch { $cmd = '<no-cmdline>' }
        Write-Host "PID:$($p.Id) Name:$($p.ProcessName) Cmd:$cmd"
    }
}

# Also show cmd.exe processes that may host npm
$cmds = Get-Process -Name cmd -ErrorAction SilentlyContinue
if ($cmds) {
    foreach ($c in $cmds) {
        try { $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($c.Id)").CommandLine } catch { $cmdline = '<no-cmdline>' }
        Write-Host "CMD PID:$($c.Id) Cmd:$cmdline"
    }
} else { Write-Host "No cmd.exe processes found via Get-Process" }
