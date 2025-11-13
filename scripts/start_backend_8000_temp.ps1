$root = (Resolve-Path "$PSScriptRoot\..").ProviderPath
$logsDir = Join-Path $root 'logs'
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$python = Join-Path $root '.venv\Scripts\python.exe'
$stdout = Join-Path $logsDir 'backend8000.out.log'
$stderr = Join-Path $logsDir 'backend8000.err.log'
$p = Start-Process -FilePath $python -ArgumentList '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000' -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -PassThru
Write-Output "Started PID:$($p.Id)" 
