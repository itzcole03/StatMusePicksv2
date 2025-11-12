<#
Example PowerShell helper to register a Windows Scheduled Task that runs the idempotent
`run_daily_sync_example.ps1` script daily at 06:15. Adjust the -At time and -User as needed.

Usage (admin required to register for other users):
.
# Run from repository root
pwsh .\scripts\register_run_daily_task.ps1 -TaskName "StatMuseRunDailySync" -User $env:USERNAME -At "06:15"
#>

param(
    [string]$TaskName = "StatMuseRunDailySync",
    [string]$User = $env:USERNAME,
    [string]$At = "06:15",
    [string]$Description = "Run daily ingestion for StatMusePicksv2",
    [string]$ScriptRelative = ".\scripts\run_daily_sync_example.ps1"
)

$ScriptPath = Join-Path (Resolve-Path "..\" -ErrorAction SilentlyContinue).Path $ScriptRelative
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found at $ScriptPath"
    exit 1
}

# Build action to run PowerShell and the script (use -NoProfile for reliability)
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel LeastPrivilege
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task (will overwrite existing with same name)
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description $Description
Write-Host "Registered scheduled task '$TaskName' to run $ScriptPath daily at $At for user $User"
