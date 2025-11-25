Param(
    [string]$Models = $env:OLLAMA_MODELS,
    [string]$PullCmd = $env:OLLAMA_PULL_CMD -or 'ollama',
    [int]$Timeout = [int]($env:OLLAMA_PULL_TIMEOUT -or 600)
)

if (-not $Models) {
    $Models = 'embeddinggemma,qwen3-embedding,all-minilm'
}

$list = $Models -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
foreach ($m in $list) {
    Write-Host "Pulling model: $m using $PullCmd pull $m"
    try {
        & $PullCmd pull $m
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Pull command exited with code $LASTEXITCODE for model $m"
            exit $LASTEXITCODE
        }
        Write-Host "Pulled model: $m"
    } catch {
        Write-Error "Failed to pull model $m: $_"
        exit 1
    }
}
