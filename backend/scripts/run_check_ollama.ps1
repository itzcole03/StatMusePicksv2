$env:PYTHONPATH = (Get-Location).Path
if (-not $env:OLLAMA_URL) {
	$env:OLLAMA_URL = 'https://api.ollama.com'
}
python backend/scripts/check_ollama_embeddings.py
