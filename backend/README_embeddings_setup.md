**Embeddings Setup**

- **Purpose**: Steps to provision Ollama embedding models locally (or on your Ollama host) so `LLMFeatureService` can generate live embeddings.

- **Recommended models**: `embeddinggemma`, `qwen3-embedding`, `all-minilm`.

1) Manual pull (recommended for production/ops):

```
# on the Ollama host where the `ollama` CLI is available
ollama pull embeddinggemma
ollama pull qwen3-embedding
ollama pull all-minilm
```

2) Automated pull (dev/ops):

- Use the helper script shipped in the repo:

```
# from repo root (requires python)
python backend/scripts/pull_ollama_models.py

# or from PowerShell on Windows
.
\backend\scripts\pull_ollama_models.ps1
```

3) Opt-in server auto-pull (not recommended for production):

- Set `OLLAMA_ALLOW_AUTO_PULL=true` in the environment where the FastAPI backend runs.
- The client will attempt `ollama pull <model>` on model-not-found errors and retry the embedding request once.
- Environment controls:
  - `OLLAMA_ALLOW_AUTO_PULL` (true|false)
  - `OLLAMA_PULL_CMD` (defaults to `ollama`)
  - `OLLAMA_PULL_TIMEOUT` (seconds, default 600)

4) Production flags to enable live-only embeddings:

```
# disable deterministic fallback in production
export OLLAMA_EMBEDDINGS_FALLBACK=false

# ensure your runtime points to the Ollama host/cloud and default model
export OLLAMA_URL=http://ollama-host:11434
export OLLAMA_DEFAULT_MODEL=embeddinggemma
```

5) Troubleshooting

- If `ollama` binary is not found on the host, use the manual pull on the host machine where the Ollama daemon runs, or install Ollama per https://ollama.com/docs.
- If pulling large models times out, increase `OLLAMA_PULL_TIMEOUT`.
