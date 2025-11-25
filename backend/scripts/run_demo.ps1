$env:PYTHONPATH = (Get-Location).Path
# Ensure OLLAMA_URL is set in this process (use persisted value if present,
# otherwise default to Ollama Cloud endpoint for testing).
if (-not $env:OLLAMA_URL) {
	$env:OLLAMA_URL = 'https://api.ollama.com'
}
python backend/scripts/embeddings_demo.py
