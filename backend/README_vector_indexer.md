# Vector Indexer

This lightweight indexer periodically reads a JSONL file of items to index and generates embeddings via the project's `LLMFeatureService`, persisting vector metadata in the database.

Quick start

- Put a JSONL file with items to index at the path set in `INDEXER_SOURCE_FILE` (default: `backend/ingest_audit/news_to_index.jsonl`). Each line should be a JSON object with at least `id` and `text` keys, e.g.:

  {"id": "news:1001", "text": "Player X ruled questionable after sprain", "meta": {"player":"Player X"}}

- Set environment variables as needed:
  - `INDEXER_SOURCE_FILE` - path to JSONL file
  - `INDEXER_INTERVAL_SECONDS` - polling interval in seconds (default 300)
  - `DATABASE_URL` - database URL (optional; defaults to sqlite `./dev.db`)
  - `VECTOR_STORE` - configured vector store (e.g., `chroma`)

Run locally (PowerShell):

```powershell
& .\backend\scripts\run_vector_indexer.ps1
```

Or directly with Python:

```bash
python backend/scripts/run_vector_indexer.py
```

Notes
- The indexer will create a `VectorIndex` DB row for each newly indexed item. If you use a persistent vector store (Chroma), ensure `VECTOR_STORE` and persistence directory are configured.
- To pull an Ollama model on the host, use `backend/scripts/ollama_pull_helper.py` on the Ollama host or the included PowerShell wrapper.

Systemd (recommended for Linux servers)

1. Copy the unit file to `/etc/systemd/system/vector-indexer.service` (adjust paths/user as needed):

```bash
sudo cp backend/deploy/vector-indexer.service /etc/systemd/system/vector-indexer.service
sudo systemctl daemon-reload
sudo systemctl enable --now vector-indexer.service
```

2. Check status and logs:

```bash
sudo systemctl status vector-indexer.service
journalctl -u vector-indexer.service -f
```

Notes: Update the `WorkingDirectory`, `ExecStart`, and environment variables in the unit file to match your host layout and virtualenv location.
