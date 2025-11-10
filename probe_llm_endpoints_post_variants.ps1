$base = 'http://localhost:11434'
$paths = @('/api/chat','/api/generate','/v1/chat/completions','/v1/completions','/v1/generate','/v1/llm/generate','/v1/llm/chat','/api/ollama/generate','/generate')
$outFile = Join-Path $PSScriptRoot 'probe_results_variants.txt'
"Probing POST endpoint variants on $base" | Out-File -FilePath $outFile -Encoding utf8
$modelsResp = try { Invoke-RestMethod -Uri ($base.TrimEnd('/') + '/v1/models') -Method GET -TimeoutSec 3 -ErrorAction Stop } catch { $null }
$models = @()
if ($modelsResp -ne $null) {
  try { $models = @($modelsResp.data | ForEach-Object { $_.id }) } catch { $models = @() }
}
if (-not $models -or $models.Count -eq 0) { $models = @('llama3.2:3b') }

$payloadVariants = @()
# OpenAI chat style
$payloadVariants += @{ name = 'openai_chat'; body = @{ model = $models[0]; messages = @(@{ role='system'; content='You are an assistant.' }, @{ role='user'; content='ping' }); stream = $false } }
# simple prompt style
$payloadVariants += @{ name = 'prompt_simple'; body = @{ model = $models[0]; prompt = 'ping' } }
# ollama generate shape guess
$payloadVariants += @{ name = 'ollama_generate'; body = @{ model = $models[0]; text = 'ping' } }
# alternative input field
$payloadVariants += @{ name = 'input_field'; body = @{ model = $models[0]; input = 'ping' } }
# minimal model-only
$payloadVariants += @{ name = 'model_only'; body = @{ model = $models[0] } }
# messages only
$payloadVariants += @{ name = 'messages_only'; body = @{ messages = @(@{ role='user'; content='ping' }) } }

foreach ($p in $paths) {
  $u = $base.TrimEnd('/') + $p
  "\n=== Testing POST $u ===" | Out-File -FilePath $outFile -Append -Encoding utf8
  foreach ($variant in $payloadVariants) {
    $name = $variant.name
    $body = $variant.body | ConvertTo-Json -Compress
    "-- Variant: $name --" | Out-File -FilePath $outFile -Append -Encoding utf8
    try {
      $r = Invoke-WebRequest -Uri $u -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
      "Status: $($r.StatusCode)" | Out-File -FilePath $outFile -Append -Encoding utf8
      $txt = $r.Content
      if ($txt.Length -gt 1000) { $txt = $txt.Substring(0,1000) + '... [truncated]' }
      $txt | Out-File -FilePath $outFile -Append -Encoding utf8
    } catch {
      "Error: $($_.Exception.Message)" | Out-File -FilePath $outFile -Append -Encoding utf8
    }
  }
}

"Probe complete. Results saved to: $outFile" | Out-File -FilePath $outFile -Append -Encoding utf8
Write-Host "Probe executed; results saved to $outFile"