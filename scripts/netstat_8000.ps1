$lines = (netstat -ano) -join "`n"
$matches = $lines -split "`n" | Where-Object { $_ -match ":8000\b" }
if ($matches) { $matches | ForEach-Object { Write-Host $_ } } else { Write-Host 'No listeners on :8000' }