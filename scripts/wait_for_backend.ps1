# Wait for backend /health endpoint to respond
$uri = 'http://127.0.0.1:8000/health'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-RestMethod -Uri $uri -TimeoutSec 2
        Write-Host "Backend ready: $($r)"
        $ready = $true
        break
    } catch {
        Write-Host "Waiting for backend... ($i)"
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) { Write-Error "Backend did not become ready in time"; exit 1 }
else { exit 0 }