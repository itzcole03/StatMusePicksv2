$env:PYTHONPATH = (Get-Location).Path
$env:OLLAMA_URL = 'http://localhost:11434'
python backend/scripts/embeddings_demo.py
