# Development README

This file contains quick developer instructions for running the backend and integration tests locally, including a small Docker Compose snippet to start a Redis service used by the prediction caching integration test.

## Start Redis (for integration tests)

Create a `docker-compose.redis.yml` with the following content (or copy the snippet below):

```yaml
version: '3.8'
services:
	redis:
		image: redis:6
		ports:
			- "6379:6379"
		healthcheck:
			test: ["CMD-SHELL", "redis-cli ping || exit 1"]
			interval: 5s
			timeout: 2s
			retries: 5

# Optionally run with: docker-compose -f docker-compose.redis.yml up -d
```

On Windows PowerShell, run:

```pwsh
# Start Redis in background
docker-compose -f docker-compose.redis.yml up -d

# Verify Redis is healthy
docker-compose -f docker-compose.redis.yml ps
```

## Activate virtualenv & run Redis integration test

Make sure you have the project's virtual environment activated and `PYTHONPATH` set so tests import the `backend` package correctly.

```pwsh
# Activate venv (Windows PowerShell)
& .\.venv\Scripts\Activate.ps1

# Ensure PYTHONPATH points to the repo root
$env:PYTHONPATH = "$PWD"

# Run only the Redis integration test
pytest backend/tests/test_api_predict_redis_integration.py -q
```

If you prefer one-off Docker usage without creating the compose file, run:

```pwsh
# Run Redis container (temporary)
docker run -d -p 6379:6379 --name statmuse_dev_redis redis:6

# Stop and remove when done
docker rm -f statmuse_dev_redis
```

## Notes

- The integration test expects Redis reachable at `localhost:6379`. If your Docker host differs (WSL2/network config), set `REDIS_HOST`/`REDIS_PORT` environment variables before running the test.
- The repo contains CI workflows that start Redis for the integration job; local steps above mirror that setup for developer convenience.
Development README — StatMusePicksv2

This short developer guide covers the common local dev tasks: creating/activating the Python venv, starting the backend and frontend in dev, running tests, and quick API examples used for smoke checks.

**Prerequisites**

- Node.js (recommended >= 18) and `npm`
- Python 3.10+ and `venv`
- (Optional) Redis if you want to enable Redis caching locally

**Activate Python virtualenv (PowerShell)**

```powershell
# Create once
python -m venv .venv
# Activate for current shell (do this in repo root)
& .\.venv\Scripts\Activate.ps1
# Ensure PYTHONPATH points to the repo root when running uvicorn/tests from tooling
$env:PYTHONPATH = (Get-Location).Path
```

**Install dependencies**

```powershell
# Python deps (from backend/requirements.txt or root requirements)
& .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
# Frontend deps
npm install
```

**Start backend (development)**

```powershell
# From repo root (activate venv first)
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Notes:

- The backend includes startup model preloading and a global error handler to avoid process exits on unexpected exceptions.
- If you have Redis running and configured, the backend will use it for caching (player context + predict TTLs).

**Start frontend (development)**

The repo contains helper scripts to start the frontend detached on Windows. For an interactive foreground start:

```powershell
npm run dev -- --host --port 3000
```

Or use the provided helper script to start/restart the detached frontend (it writes logs and PID into `logs/`):

```powershell
# Stop/start helper (repo has scripts/run_restart_frontend.ps1)
.\scripts\run_restart_frontend.ps1
# Tail the frontend stdout log
Get-Content -Path .\logs\frontend.out.log -Wait -Tail 200
```

Frontend dev server binds to all interfaces when started with `--host`. Logs are saved to `logs/frontend.out.log` and the PID to `logs/frontend.pid` when using the detached helper.

**Quick API smoke checks**

From PowerShell (examples used during debugging):

- GET player context (query string)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/player_context?player=LeBron%20James&limit=3" -Method GET | ConvertTo-Json -Depth 5
```

- POST predict (JSON body) — requires `line` field

```powershell
$json = '{"player":"LeBron James","stat":"points","line":25.5,"player_data":{},"opponent_data":{}}'
Invoke-RestMethod -Uri 'http://localhost:8000/api/predict' -Method Post -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5
```

Alternative (curl):

```powershell
curl.exe -X POST "http://localhost:8000/api/predict" -H "Content-Type: application/json" -d "{\"player\":\"LeBron James\",\"stat\":\"points\",\"line\":25.5,\"player_data\":{},\"opponent_data\":{}}"
```

There is a small helper script used during checks: `scripts/check_predict.py` which POSTs a valid payload to `/api/predict` using the Python standard library.

**Run tests**

```powershell
& .\.venv\Scripts\Activate.ps1
python -m pytest -q
# Or run a specific test file
python -m pytest backend/tests/test_ml_prediction_service_unit.py -q
```

**CI / Deterministic smoke tests**

- The repo uses an in-process FastAPI TestClient for a deterministic smoke test of `/api/predict` in CI. See `.github/workflows/backend-ci.yml` for details.

**Troubleshooting & notes**

- If the frontend appears unreachable, ensure it was started with `--host` so it binds both IPv4 and IPv6 loopback addresses.
- If `nba_api` or other optional dependencies are missing, the backend falls back to graceful behavior (player context endpoints may report `noGamesThisSeason` or return limited data).
- Logs: frontend logs are in `logs/frontend.out.log` and backend logs may be captured in `logs/uvicorn*.log` depending on how you start uvicorn.

If you'd like, I can:

- Add these dev instructions to the main `README.md` instead of a separate `README.dev.md`.
- Create a short PowerShell script `scripts/dev_setup.ps1` that runs the common activation + install steps.
- Add an automated `make dev` or `npm` script to unify backend/frontend start steps.
