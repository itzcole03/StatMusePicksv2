$root = (Resolve-Path "$PSScriptRoot\..").ProviderPath
$uri = 'http://127.0.0.1:8000/health'
$max = 30
for ($i = 0; $i -lt $max; $i++) {
    try {
        $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
        if ($r.ok -eq $true) { Write-Output "HEALTH:OK"; exit 0 }
    } catch {
        # ignore
    }
    Start-Sleep -Seconds 1
}
Write-Output "HEALTH:FAILED"
exit 1
