$base = 'http://localhost:11434'
$paths = @('/','/api/chat','/api/generate','/v1/chat/completions','/v1/completions','/models','/v1/models','/models/list')
$outFile = Join-Path $PSScriptRoot 'probe_results.txt'
"Probing endpoints on $base" | Out-File -FilePath $outFile -Encoding utf8
foreach ($p in $paths) {
  $u = $base.TrimEnd('/') + $p
  "\n=== GET $u ===" | Out-File -FilePath $outFile -Append -Encoding utf8
  try {
    $r = Invoke-WebRequest -Uri $u -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    "Status: $($r.StatusCode)" | Out-File -FilePath $outFile -Append -Encoding utf8
    $body = $r.Content
    if (-not $body) { "(no body)" | Out-File -FilePath $outFile -Append -Encoding utf8 } else { if ($body.Length -gt 1000) { $body = $body.Substring(0,1000) + '... [truncated]' }; $body | Out-File -FilePath $outFile -Append -Encoding utf8 }
  } catch {
    "GET error: $($_.Exception.Message)" | Out-File -FilePath $outFile -Append -Encoding utf8
  }
}

"\nProbing POST endpoints with a lightweight payload..." | Out-File -FilePath $outFile -Append -Encoding utf8
$payload = @{ model = 'llama3.2:latest'; messages = @(@{ role='user'; content='ping' }); stream = $false } | ConvertTo-Json -Compress
foreach ($p in $paths) {
  $u = $base.TrimEnd('/') + $p
  "\n=== POST $u ===" | Out-File -FilePath $outFile -Append -Encoding utf8
  try {
    $r2 = Invoke-WebRequest -Uri $u -Method POST -Body $payload -ContentType 'application/json' -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
    "Status: $($r2.StatusCode)" | Out-File -FilePath $outFile -Append -Encoding utf8
    $b2 = $r2.Content
    if (-not $b2) { "(no body)" | Out-File -FilePath $outFile -Append -Encoding utf8 } else { if ($b2.Length -gt 1000) { $b2 = $b2.Substring(0,1000) + '... [truncated]' }; $b2 | Out-File -FilePath $outFile -Append -Encoding utf8 }
  } catch {
    "POST error: $($_.Exception.Message)" | Out-File -FilePath $outFile -Append -Encoding utf8
  }
}

"\nProbe complete. Results saved to: $outFile" | Out-File -FilePath $outFile -Append -Encoding utf8
Write-Host "Probe script executed; results saved to $outFile"