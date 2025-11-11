# Inspect Python and cmd processes with command line and write to logs/process_list.txt
$out = Join-Path (Get-Location).Path 'logs\process_list.txt'
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python.exe' -or $_.Name -match 'cmd.exe' } | Select-Object ProcessId, Name, CommandLine | Out-String -Width 4096 | Set-Content $out
Write-Host "Wrote process list to: $out"
