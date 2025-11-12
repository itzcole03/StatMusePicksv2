<#
Robust CI artifact downloader for this repo.
Usage: In PowerShell, from repo root:
  Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue
  .\scripts\fetch_ci_artifacts.ps1 -branch "chore/deps-audit-fix" -outDir .\ci_artifacts

This script will:
- List recent workflow runs for the repo
- Filter runs by the provided branch and workflow (if present)
- Download artifacts for matching runs into subdirectories under the output directory
#>

param(
    [string]$branch = "chore/deps-audit-fix",
    [string]$outDir = "./ci_artifacts",
    [int]$maxRuns = 20
)

Set-StrictMode -Version Latest

function Fail($msg) { Write-Error $msg; exit 1 }

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail "gh CLI not found in PATH. Install GitHub CLI and authenticate via 'gh auth login'." }

$repo = "itzcole03/StatMusePicksv2"

Write-Output "Listing recent runs for branch '$branch'..."
$runsRaw = gh run list --repo $repo --branch $branch --limit $maxRuns --json databaseId,workflowName,headBranch,status,conclusion 2>&1
if ($LASTEXITCODE -ne 0 -or $runsRaw -match 'HTTP') {
    Write-Warning "Branch-filtered run listing failed or returned HTTP error; falling back to repo-wide listing"
    $runsRaw = gh run list --repo $repo --limit $maxRuns --json databaseId,workflowName,headBranch,status,conclusion 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Failed to list runs: $runsRaw" }
}

$runs = $null
try { $runs = $runsRaw | ConvertFrom-Json } catch { Fail "Failed to parse JSON from gh run list output" }

$matches = $runs | Where-Object { $_.headBranch -eq $branch }
if (-not $matches) { Write-Warning "No runs found for branch '$branch' in the recent $maxRuns runs." }

if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

foreach ($r in $matches) {
    $id = $r.databaseId
    $dest = Join-Path (Resolve-Path $outDir).Path ("run_$id")
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Write-Output "Downloading artifacts for run $id to $dest"
    gh run download $id --repo $repo --dir $dest 2>&1 | Write-Output
    if ($LASTEXITCODE -ne 0) { Write-Warning "Failed to download artifacts for run $id"; continue }
    $files = Get-ChildItem -Path $dest -Recurse -File -ErrorAction SilentlyContinue
    if (-not $files) { Write-Output "No artifacts found for run $id"; continue }
    Write-Output ("Artifacts for run {0}:" -f $id)
    foreach ($f in $files) { Write-Output $f.FullName }
}

Write-Output "Done. Inspect $outDir for downloaded artifacts." 
