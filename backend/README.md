# Backend (NBA proxy) - Quick start

This small FastAPI backend is a development helper that wraps `nba_api` for player contexts. The repository already contains `fastapi_nba.py` which defines a FastAPI `app` and endpoints such as `/health`, `/player_summary`, and `/api/player_context`.

Prerequisites

- Python 3.9+
- Create and activate a virtual environment (recommended)

Install dependencies (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the dev server (recommended)

```powershell
# From the repository root (ensures `backend` is importable):
# Start the FastAPI app (recommended):
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Notes:
# - Start this command from the project root so Python can import the `backend` package.
# - If port `8000` is in use the process may auto-bind a different port; check the uvicorn logs.
# - Use `backend/main.py` as the canonical entrypoint in tooling and docker-compose.
```

Health check

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Debug/status endpoint

```powershell
# Friendly dev endpoint that reports DB and Redis connectivity
Invoke-RestMethod http://localhost:8000/debug/status | ConvertTo-Json -Depth 5
```

Notes

- The code uses `nba_api` optionally; if `nba_api` is not installed the endpoints will still run but will return limited results or 404 for missing players.
- To enable Redis caching set `REDIS_URL` environment variable before starting the server.
- This backend is intended for local/dev use only; secure and harden before exposing publicly.

# Backend (FastAPI) - NBA data example

This folder contains an example FastAPI app that demonstrates how to use the
`nba_api` Python library server-side and expose a minimal `player_summary`
endpoint for the frontend.

Important notes:

- `nba_api` must be installed into the Python environment used to run this server.
- This is a development example. Add caching (Redis or cachetools), authentication,
  and sensible rate-limiting before using in production.

Quick start (PowerShell - venv):

```pwsh
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn fastapi_nba:app --host 127.0.0.1 --port 3002
```

Endpoint:

- `GET /player_summary?player=LeBron%20James&stat=points&limit=8`

Response shape (JSON):

- `player`, `stat`, `league`, `recent`, `recentGames` (array), `seasonAvg`, `fetchedAt`

Optional Redis caching

- Set `REDIS_URL` environment variable (e.g., `redis://localhost:6379/0`) and the server will use Redis as a persistent cache in addition to an in-memory TTL cache.

Health check

- `GET /health` returns `{ "ok": true }` useful for simple readiness checks.

Run via Docker Compose (reproducible dev):

```pwsh
docker compose up -d --build backend
Invoke-RestMethod 'http://127.0.0.1:3002/health' -UseBasicParsing | ConvertTo-Json -Depth 5
```

## Migrations & Training (development)

Run Alembic migrations (uses `.venv` virtualenv):

```pwsh
. .\.venv\Scripts\Activate.ps1
./backend/scripts/run_migrations.ps1
```

Create a synthetic model for quick testing:

```pwsh
. .\.venv\Scripts\Activate.ps1
./backend/scripts/run_training.ps1
```

Notes:

- The migrations use `DATABASE_URL` env var; if unset the helper defaults to `sqlite:///./dev.db`.
- The training script writes a small model to `backend/models_store/` for local dev; it is not production-grade.

Quick verification script (starts backend and runs prompt builder):

```pwsh
.\scripts\run_local_backend_and_prompt.ps1 -Mode venv -Player "LeBron James" -Stat points -Limit 5
```

If you want me to wire the frontend to call this service and verify end-to-end,
I can update `src/services/nbaService.ts` and provide the exact commands to run both processes.

## Prometheus metrics (multiprocess workers)

If you run the backend with multiple worker processes (e.g., Gunicorn/Uvicorn with workers),
Prometheus client library requires a multiprocess mode to correctly collect metrics across
processes. The repository includes a helper `backend/services/metrics.py` that will
automatically use `PROMETHEUS_MULTIPROC_DIR` when present.

Quick setup (PowerShell):

```pwsh
# create a directory for multiprocess metrics files
mkdir .\prom_metrics
$env:PROMETHEUS_MULTIPROC_DIR = (Resolve-Path .\prom_metrics).Path
# start uvicorn/gunicorn worker processes in the same environment
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 4
```

Notes:
- Ensure the directory is writable by all worker processes.
- In CI or systemd setups, set `PROMETHEUS_MULTIPROC_DIR` in the unit/service environment and
    ensure the directory is cleaned between runs (it accumulates temporary metric files).

