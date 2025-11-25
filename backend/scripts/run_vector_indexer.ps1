<#
.SYNOPSIS
  PowerShell wrapper to run the Python vector indexer loop.

.DESCRIPTION
  Activates the venv in this repo (if available) and runs the indexer entrypoint
  `backend/scripts/run_vector_indexer.py`. Useful for running on Windows hosts.

.PARAMETER Interval
  Optional: override `INDEXER_INTERVAL_SECONDS` for this run.
#>
param(
  [int]$Interval = $null,
  [string]$OllamaUrl = $null,
  [string]$Model = $null,
  [string]$ApiKey = $null,
  [switch]$EnableFallback
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# Activate virtualenv if present
$venvActivate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
}

if ($Interval) {
    $env:INDEXER_INTERVAL_SECONDS = $Interval.ToString()
}

# Optional Ollama env setup (prefer secrets for API keys)
if ($OllamaUrl) { $env:OLLAMA_URL = $OllamaUrl }
if ($Model) { $env:OLLAMA_DEFAULT_MODEL = $Model }
if ($ApiKey) { $env:OLLAMA_CLOUD_API_KEY = $ApiKey }
# By default disable deterministic fallback for production runs; pass -EnableFallback to allow it
if ($EnableFallback) { $env:OLLAMA_EMBEDDINGS_FALLBACK = 'true' } else { if (-not $env:OLLAMA_EMBEDDINGS_FALLBACK) { $env:OLLAMA_EMBEDDINGS_FALLBACK = 'false' } }

Write-Host "Starting vector indexer (source: $($env:INDEXER_SOURCE_FILE) interval: $($env:INDEXER_INTERVAL_SECONDS))"
python -u backend/scripts/run_vector_indexer.py
