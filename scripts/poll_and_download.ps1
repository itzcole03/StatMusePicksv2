param(
    [string]$Repo = 'itzcole03/StatMusePicksv2',
    [string]$Workflow = 'alembic_timescale_smoke.yml',
    [int]$MaxMinutes = 15
)

$ErrorActionPreference = 'Stop'
Write-Output "Starting poll_and_download for $Repo / $Workflow"

function Fail([string]$msg) {
    Write-Error $msg
    exit 1
}

# get latest run id
$tryRaw = $null
Write-Output "Listing recent runs for workflow $Workflow (primary attempt using --workflow)..."
$tryRaw = gh run list --repo $Repo --workflow $Workflow --limit 1 --json databaseId,workflowName,headBranch,status,conclusion,createdAt 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Output "Primary workflow-filtered listing failed (will fallback to repo-wide listing):"
    Write-Output $tryRaw
    Write-Output "Listing recent runs across repo and filtering by workflowName..."
    $rawAll = gh run list --repo $Repo --limit 50 --json databaseId,workflowName,headBranch,status,conclusion,createdAt 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Output $rawAll; Fail "gh run list (repo-wide) failed with exit $LASTEXITCODE" }
    try { $arrAll = $rawAll | ConvertFrom-Json } catch { Write-Output $rawAll; Fail 'Failed to parse repo-wide gh run list JSON' }
    $matches = $arrAll | Where-Object { $_.workflowName -eq $Workflow }
    if (-not $matches -or $matches.Count -eq 0) { Fail "No runs found matching workflow name '$Workflow' in recent runs" }
    $run = $matches[0]
} else {
    try { $arr = $tryRaw | ConvertFrom-Json } catch { Write-Output $tryRaw; Fail 'Failed to parse gh run list JSON (workflow-filtered)' }
    if (-not $arr -or $arr.Count -eq 0) { Fail "No runs found for workflow $Workflow" }
    $run = $arr[0]
}
$id = $run.databaseId
Write-Output "Found run id=$id, branch=$($run.headBranch), status=$($run.status), createdAt=$($run.createdAt)"

# Poll until completed
$maxAttempts = [int](($MaxMinutes * 60) / 10)
$attempt = 0
while ($attempt -lt $maxAttempts) {
    $attempt++
    $infoRaw = gh run view $id --repo $Repo --json status,conclusion 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Output $infoRaw; Write-Output "gh run view failed (exit $LASTEXITCODE). Retrying..."; Start-Sleep -Seconds 10; continue }
    try { $info = $infoRaw | ConvertFrom-Json } catch { Write-Output $infoRaw; Start-Sleep -Seconds 10; continue }
    Write-Output ("Attempt {0}: status={1} conclusion={2}" -f $attempt, $info.status, $info.conclusion)
    if ($info.status -eq 'completed') { break }
    Start-Sleep -Seconds 10
}

if ($info.status -ne 'completed') { Fail "Timed out waiting for run $id to complete" }

Write-Output "Run $id completed with conclusion: $($info.conclusion)"

# Download artifacts
$dest = Join-Path $PSScriptRoot "ci_artifacts_$id"
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Write-Output "Downloading artifacts to $dest"
gh run download $id --repo $Repo --dir $dest 2>&1 | Write-Output
if ($LASTEXITCODE -ne 0) { Fail 'gh run download failed' }

Write-Output "Artifacts saved under: $dest"
Get-ChildItem -Path $dest -Recurse -File | ForEach-Object { Write-Output $_.FullName }

# Search for logs and junit
$alembicFiles = Get-ChildItem -Path $dest -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'alembic*' -or $_.Name -ieq 'alembic.log' }
$junitFiles = Get-ChildItem -Path $dest -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'junit*.xml' -or $_.Name -ieq 'junit.xml' }

if ($alembicFiles.Count -gt 0) {
    Write-Output "`n=== ALEMBIC LOGS ==="
    foreach ($f in $alembicFiles) {
        Write-Output "--- $($f.FullName) ---"
        Get-Content $f.FullName -Raw | Write-Output
    }
} else { Write-Output 'No alembic log files found in artifacts.' }

if ($junitFiles.Count -gt 0) {
    Write-Output "`n=== JUNIT XML(s) ==="
    foreach ($f in $junitFiles) {
        Write-Output "--- $($f.FullName) ---"
        $xml = Get-Content $f.FullName -Raw
        if ($xml.Length -gt 15000) { Write-Output ($xml.Substring(0,15000) + "`n...[truncated]") } else { Write-Output $xml }
    }
} else { Write-Output 'No junit xml files found in artifacts.' }

Write-Output "Done."
