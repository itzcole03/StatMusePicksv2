Param(
    [string]$Url = $env:MODEL_DOWNLOAD_URL,
    [string]$OutputDir = "$PSScriptRoot\..\backend\models_store",
    [string]$FileName = $env:MODEL_FILE_NAME
)

if (-not $Url) {
    Write-Error "MODEL_DOWNLOAD_URL environment variable or -Url parameter is required."
    exit 2
}

if (-not (Test-Path -Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

if (-not $FileName) {
    $FileName = Split-Path -Path $Url -Leaf
}

$outPath = Join-Path $OutputDir $FileName

Write-Host "Downloading model from $Url to $outPath"

try {
    Invoke-WebRequest -Uri $Url -OutFile $outPath -UseBasicParsing -ErrorAction Stop
    Write-Host "Downloaded model to $outPath"
} catch {
    Write-Error "Failed to download model: $_"
    exit 3
}

Write-Host "Done."