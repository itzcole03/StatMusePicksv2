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

Running NBA client tests
------------------------

Unit and integration tests for the NBA client live under `backend/tests/`.
Run only the NBA client tests locally with PowerShell (from repo root):

```pwsh
& .venv\Scripts\Activate.ps1
python -m pytest backend/tests/test_nba_stats_client.py -q
python -m pytest backend/tests/test_nba_stats_client_integration.py -q
```

The integration test spins up a small local HTTP server that mimics a lightweight NBA proxy; it is deterministic and fast.


Debug/status endpoint

```powershell
# Friendly dev endpoint that reports DB and Redis connectivity
Invoke-RestMethod http://localhost:8000/debug/status | ConvertTo-Json -Depth 5
```

Notes

- The code uses `nba_api` optionally; if `nba_api` is not installed the endpoints will still run but will return limited results or 404 for missing players.
- To enable Redis caching set `REDIS_URL` environment variable before starting the server.
- This backend is intended for local/dev use only; secure and harden before exposing publicly.

Ingestion validation & alerting
--------------------------------

- `run_daily_sync()` performs a best-effort fetch -> persist raw -> normalize -> validate -> ingest flow for game data. It writes raw fetches to the directory configured by `INGEST_AUDIT_DIR` (defaults to `./backend/ingest_audit`).
- Validation: the pipeline runs `validate_batch()` which checks for required fields (e.g. `game_date`, `home_team`, `away_team`), basic type checks, and numeric outliers. The result is returned as part of the `run_daily_sync()` summary under the `validation` key and includes `missing`, `type_errors`, and `outliers` lists.
- Filtering policy: records missing critical fields are filtered out of ingestion by default. The `run_daily_sync()` return value contains `filtered_out_count` so automated tooling can detect dropped rows.
- Alerting: if validation finds missing or type errors the service will attempt a best-effort POST of a small JSON summary to the webhook URL configured in the `INGEST_ALERT_WEBHOOK` environment variable. If no webhook is configured the message is logged as a warning.

Example (env vars):

```powershell
# Audit directory for raw fetches
$env:INGEST_AUDIT_DIR = "C:\path\to\audit_dir"

# Optional: webhook that will receive validation summaries (POST JSON)
$env:INGEST_ALERT_WEBHOOK = "https://hooks.example.com/ingest-alerts"
```

Webhook secrets & verification
------------------------------

The ingestion pipeline can POST small JSON validation summaries to a webhook when issues are found. These environment variables control the alerting behavior and verification:

- `INGEST_ALERT_WEBHOOK`: (optional) URL to POST validation summaries to. If unset, validation findings are logged but not sent.
- `INGEST_ALERT_SECRET`: (optional) an opaque secret string sent in the `X-Ingest-Secret` header for simple authentication (e.g., webhook expects a header match).
- `INGEST_ALERT_HMAC_SECRET`: (optional) when set, the backend computes an HMAC-SHA256 over the request body and sends `X-Ingest-Signature: sha256=<hex>` so receivers can verify payload integrity and authenticity. Example receiver pseudocode:

```python
import hmac, hashlib
def verify(body_bytes, header_sig, secret):
    expected = hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()
    return header_sig == f"sha256={expected}"
```

- `INGEST_ALERT_RETRIES`: (optional) number of retry attempts for transient failures; default `3`.
- `INGEST_ALERT_BACKOFF`: (optional) base backoff factor in seconds for retries; default `0.5`. Exponential backoff is applied.

Recommendations:

- Store `INGEST_ALERT_HMAC_SECRET` and `INGEST_ALERT_SECRET` in your platform's secret store (e.g., GitHub Actions Secrets, Azure Key Vault, AWS Secrets Manager) and inject at runtime; do not commit them to source control.
- Verify the HMAC signature on the receiver side before acting on alerts; use constant-time compare functions to avoid timing attacks.
- If you need advanced retry policies or non-blocking background alerting, consider forwarding alerts to a dedicated queuing service (SQS, Pub/Sub) and processing asynchronously.

Async usage
-----------

If your application is already running inside an `asyncio` event loop (for example, a FastAPI background task
or another async worker), prefer the async entrypoint `run_daily_sync_async()` so you can `await` the work
without blocking the loop. Example:

```python
import asyncio
from datetime import date
from backend.services import data_ingestion_service as dis

async def do_ingest():
    result = await dis.run_daily_sync_async(when=date.today())
    print(result)

# schedule/run inside existing loop
asyncio.create_task(do_ingest())
```

If you call from synchronous code, continue to use `run_daily_sync()` which will call the async variant via
`asyncio.run()` under the hood.


Example `run_daily_sync()` summary (returned from the function):

```json
{
    "audit_path": ".../games_raw_2025-11-12.json",
    "player_rows": 10,
    "team_rows": 30,
    "validation": { "missing": [], "type_errors": [], "outliers": [] },
    "filtered_out_count": 0
}
```

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

### Training dataset generation (CLI)

The repository includes a lightweight dataset generator used to build per-player
training datasets from historical `player_stats`. Use the CLI helper to
generate parquet/csv datasets and metadata for downstream training.

Quick example (PowerShell):

```pwsh
& .venv\Scripts\Activate.ps1
python -m backend.services.training_data_service --stat-types points --out-dir backend/data/training_datasets
```

Notes:
- The CLI will prefer Parquet output when `pyarrow` or `fastparquet` is installed; otherwise it falls back to CSV.
- Per-player time-based splitting and a conservative filter for players with insufficient games are applied in the pipeline. See `backend/services/training_data_service.py` for details.
- The CLI writes a small JSON metadata file alongside each dataset containing `version_id`, `rows`, and `created_at`.

Quick programmatic usage (from Python):

```python
from backend.services.training_data_service import generate_samples_from_game_history, time_based_split
# supply a player's game list (newest-first) and get a DataFrame of samples
df = generate_samples_from_game_history("LeBron James", games)
train, val, test = time_based_split(df)
```


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

## Scheduling & CI smoke tests

- Use the provided `systemd` unit and timer templates in `scripts/systemd/` to schedule the daily ingestion job. A secure environment file template is available at `scripts/systemd/env.example` and an idempotent installer script `scripts/systemd/install_env.sh` prepares `/etc/statmuse/env` with `0600` permissions.

- We also include an example GitHub Actions workflow `.github/workflows/ingest-smoke.yml` that demonstrates how to inject the `INGEST_ALERT_HMAC_SECRET` repository secret and run the CLI against a local webhook receiver started inside the job for smoke-testing. To use it in your repository:

    1. Add `INGEST_ALERT_HMAC_SECRET` to the repository Secrets in GitHub (Settings → Secrets).
    2. Trigger the workflow manually from the Actions tab or push to `main`/`master`.

- Local installer example (run on the target host as root):

```bash
# generate a secure HMAC secret
HMAC_SECRET=$(openssl rand -hex 32)

# run installer as root to create /etc/statmuse/env (idempotent)
sudo ./scripts/systemd/install_env.sh --repo-root /srv/statmusepicks --hmac "$HMAC_SECRET" --service-user statmuse
```

Notes:

- Keep `/etc/statmuse/env` owned by `root:root` and set to `0600`.
- For production use, prefer a secrets manager (Vault, AWS Secrets Manager) and adapt the installer to fetch secrets at deploy time.
- The GitHub Actions workflow is a smoke test pattern: it starts a local HTTP receiver to verify webhook posts and demonstrates secrets injection; tune or disable network-dependent steps in CI if your runner blocks outbound requests.

