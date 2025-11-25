$env:PYTHONPATH = (Get-Location).Path
$env:VECTOR_STORE = 'chroma'
$env:CHROMA_PERSIST_DIR = 'backend/artifacts/chroma_store'
python backend/scripts/embeddings_demo.py
