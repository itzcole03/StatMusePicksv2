Ollama integration — quick setup
===============================

This file documents quick steps to get Ollama working with the backend services in this repo.

Prerequisites
-------------
- Python virtualenv activated (see project README).
- Optional: a local Ollama server (`ollama` CLI) or Ollama Cloud access.

Install Python client (dev)
---------------------------
Run in the backend virtual environment:

```powershell
pip install ollama requests
```

Environment variables
---------------------
- `OLLAMA_URL` — optional override for the Ollama base URL (eg. `http://localhost:11434` or `https://api.ollama.com`).
- `OLLAMA_CLOUD_API_KEY` or `OLLAMA_API_KEY` — Ollama Cloud API key if using Ollama Cloud.
- `OLLAMA_DEFAULT_MODEL` — optional default model name (eg. `llama3`).
- `BING_API_KEY` — optional for web search tool.

Basic checks
------------
1. Health endpoint (backend must be running):

```bash
curl -sS http://127.0.0.1:8000/api/ollama_health | jq
```

2. List models via the client wrapper (Python REPL):

```python
from backend.services.ollama_client import get_default_client
print(get_default_client().list_models())
```

Streaming from the frontend
--------------------------
The backend exposes `/api/ollama_stream` which accepts a JSON POST body `{ "model": "<model>", "prompt": "..." }` and returns a Server-Sent Events stream of tokens. The frontend helper `src/services/aiService.v2.ts` provides `streamOllamaAnalysis(prompt, opts, onChunk, onDone, onError)` that consumes the stream and invokes callbacks as text or done events.

Feature extraction endpoint
---------------------------
Use `/api/ollama_features` to request LLM-derived qualitative features for a player:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/ollama_features -H 'Content-Type: application/json' \
  -d '{"player":"LeBron James","text":"Player suffered a minor ankle sprain; status questionable."}' | jq
```

Troubleshooting
---------------
- If the backend cannot reach Ollama Cloud, set `OLLAMA_URL` to `http://localhost:11434` and run a local Ollama instance or use the `DEV_OLLAMA_MOCK` file to enable mock streams.
- If embeddings or model pull is failing, check `OLLAMA_ALLOW_AUTO_PULL` and the `ollama` binary availability in PATH.

If you want, I can add an example UI component that consumes `streamOllamaAnalysis` and displays the streaming tokens.
