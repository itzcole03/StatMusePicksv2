**ChromaDB Setup (optional persistent vector store)**

- Install `chromadb` in your backend environment (see `backend/requirements.txt`). For CPU-only setups:

```
pip install chromadb
```

- Configure environment variables (example in `backend/.env.example`):

```
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=./chroma_data
CHROMA_COLLECTION_NAME=statmuse
```

- When running with `docker-compose` ensure `CHROMA_PERSIST_DIR` is mounted as a volume so data persists across restarts.

- The code will attempt to initialize `chromadb.Client()` and fall back with a helpful error if not available. If initialization fails due to a version mismatch, consider pinning `chromadb` to a compatible version.

- Backup: periodically copy the `CHROMA_PERSIST_DIR` to an off-host backup. For large deployments consider using a managed vector DB.
