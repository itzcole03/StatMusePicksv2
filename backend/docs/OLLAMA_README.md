# Ollama Configuration & Ops

This file documents environment variables and recommended production defaults for Ollama integration used by the backend.

Required / Common environment variables

- `OLLAMA_URL` - override Ollama base URL (e.g. `http://localhost:11434` or `https://api.ollama.com`).
- `OLLAMA_CLOUD_API_KEY` / `OLLAMA_API_KEY` - Cloud API key when using Ollama Cloud.
- `OLLAMA_DEFAULT_MODEL` - default model name used by services (optional).

Important operational flags

- `OLLAMA_ALLOW_AUTO_PULL` (default: `false`) - when `true`, the backend may attempt to auto-pull missing models via the `ollama pull <model>` CLI. For production, keep this disabled to avoid unexpected large downloads or side effects.
- `OLLAMA_EMBEDDINGS_FALLBACK` (default: `false` in production) - if enabled in non-production, allows deterministic fallback embeddings when live embeddings are unavailable.
- `OLLAMA_PREFER_LOCAL` - when set, prefer `http://localhost:11434` as the Ollama host (useful for local dev environments).
- `DEV_OLLAMA_MOCK` - enable an internal mock SSE stream for frontend/dev without a real Ollama server.

Rate limiting and cost controls

- Use proxy- or infra-level rate limiting for production. The backend includes lightweight in-process guards for dev:
  - `WEB_SEARCH_MAX_RPM` (default `60`) controls tool web-search usage.
  - `BATCH_MAX_RPM` controls batch endpoints rate limiting.

Testing & CI

- Live Ollama smoke tests are guarded by the presence of `OLLAMA_CLOUD_API_KEY` (or `OLLAMA_API_KEY`) and will be skipped otherwise. Do not commit API keys to source control.
- Use `DEV_OLLAMA_MOCK=1` in local dev to exercise streaming UI and SSE parsing without a live Ollama instance.

Security

- Sanitize tool inputs (the backend does basic sanitization and length limits). Ensure any tool-callable functions that perform web requests validate and escape arguments.
- Restrict tool-calling to trusted code paths and audit logs to detect unexpected usage.

Defaults recommended for production

- `OLLAMA_ALLOW_AUTO_PULL=false`
- `OLLAMA_EMBEDDINGS_FALLBACK=false`
- Provide `OLLAMA_CLOUD_API_KEY` if using Ollama Cloud and set `OLLAMA_URL` accordingly.

If you want, I can add a small ops check script to validate these settings at startup.
