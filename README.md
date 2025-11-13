Development README — StatMusePicksv2

This short developer guide covers the common local dev tasks: creating/activating the Python venv, starting the backend and frontend in dev, running tests, and quick API examples used for smoke checks.

Prerequisites

- Node.js (recommended >= 18) and `npm`
- Python 3.10+ and `venv`
- (Optional) Redis if you want to enable Redis caching locally

Activate Python virtualenv (PowerShell)

```powershell
# Create once
python -m venv .venv
# Activate for current shell (do this in repo root)
& .\.venv\Scripts\Activate.ps1
# Ensure PYTHONPATH points to the repo root when running uvicorn/tests from tooling
$env:PYTHONPATH = (Get-Location).Path
```

Install dependencies

```powershell
# Python deps (from backend/requirements.txt or root requirements)
& .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
# Frontend deps
npm install
```

Start backend (development)

```powershell
# From repo root (activate venv first)
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Notes:

- The backend includes startup model preloading and a global error handler to avoid process exits on unexpected exceptions.
- Recent: the project uses FastAPI lifespan handlers for startup/shutdown lifecycle (preferred over the
	deprecated `@app.on_event` decorator). See `backend/fastapi_nba.py` and `backend/main.py` for examples.

- Pydantic compatibility helper: to maintain compatibility between Pydantic v1 and v2, the backend includes a
	small helper `model_to_dict()` in `backend/fastapi_nba.py` that calls either `.model_dump()` (v2) or `.dict()` (v1)
	as available. This avoids breaking changes while migrating to Pydantic v2.

- If you still see deprecation warnings (Pydantic class-config, FastAPI `on_event`, SQLAlchemy UTC usage, or
	scikit-learn unpickle version warnings), those are non-blocking and tracked as follow-up cleanup tasks in the
	roadmap. We plan to (a) finish Pydantic migration, (b) address SQLAlchemy UTC timezone usage, and (c) surface
	safer model serialization to address sklearn pickle version warnings.

- If you have Redis running and configured, the backend will use it for caching (player context + predict TTLs).

Redis (optional)

- The repo includes a `redis` service in `docker-compose.dev.yml` which exposes Redis on `6379`.
- Start only Redis locally with Docker Compose (from repo root):

```powershell
# Start the redis service in the dev compose file
docker compose -f docker-compose.dev.yml up -d redis
```

- Set `REDIS_URL` for the backend (PowerShell example):

```powershell
# Connect to local redis instance (DB 0)
$env:REDIS_URL = 'redis://localhost:6379/0'
# Then start the backend (example)
& .\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

When `REDIS_URL` is set, the backend cache helpers will connect to Redis; otherwise an in-memory fallback is used for local dev and tests.

Start frontend (development)

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

Quick API smoke checks

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

API Examples

GET player context (cached) — PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/player_context?player_name=LeBron%20James&limit=5" -Method GET | ConvertTo-Json -Depth 5
```

GET player context (curl + jq):

```bash
curl -s "http://localhost:8000/api/player_context?player_name=LeBron%20James&limit=5" | jq .
```

Notes:

- `/api/player_context` will attempt to return a cached response from Redis using the key `player_context:{player_name}:{limit}`. Cached responses include `cached: true` and a `fetchedAt` timestamp.
- The response includes `recentGames`, `seasonAvg`, and enhanced fields when available: `rollingAverages`, `contextualFactors`, and `opponentInfo`.

Batch fetch example (POST):

PowerShell:

```powershell
$body = @(
	@{ player_name = 'LeBron James'; limit = 3 },
	@{ player_name = 'Stephen Curry'; limit = 3 }
 ) | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/batch_player_context" -Method Post -Body $body -ContentType 'application/json' | ConvertTo-Json -Depth 5
```

curl example:

```bash
echo '[{"player_name":"LeBron James","limit":3},{"player_name":"Stephen Curry","limit":3}]' > /tmp/batch.json
curl -s -X POST "http://localhost:8000/api/batch_player_context" -H "Content-Type: application/json" -d @/tmp/batch.json | jq .
```

Run tests

```powershell
& .\.venv\Scripts\Activate.ps1
python -m pytest -q
# Or run a specific test file
python -m pytest backend/tests/test_ml_prediction_service_unit.py -q
```

CI / Deterministic smoke tests

- The repo uses an in-process FastAPI TestClient for a deterministic smoke test of `/api/predict` in CI. See `.github/workflows/backend-ci.yml` for details.

Troubleshooting & notes

- If the frontend appears unreachable, ensure it was started with `--host` so it binds both IPv4 and IPv6 loopback addresses.
- If `nba_api` or other optional dependencies are missing, the backend falls back to graceful behavior (player context endpoints may report `noGamesThisSeason` or return limited data).
- Logs: frontend logs are in `logs/frontend.out.log` and backend logs may be captured in `logs/uvicorn*.log` depending on how you start uvicorn.

If you'd like, I can:

- Add these dev instructions to the main `README.md` instead of a separate `README.dev.md`.
- Create a short PowerShell script `scripts/dev_setup.ps1` that runs the common activation + install steps.
- Add an automated `make dev` or `npm` script to unify backend/frontend start steps.

Model artifacts & changelog

- **New features (Nov 12, 2025):** This project now computes additional rolling statistics used by the ML feature pipeline. The feature set includes moving averages (SMA), exponential moving averages (EMA), weighted moving averages (WMA) for common windows (3/5/10 where applicable), rolling standard deviation/min/max/median, a linear `slope_10` trend over the last 10 games, and a `momentum_vs_5_avg` comparison. These are implemented in `backend/services/feature_engineering.py` and are used by both training and serving to avoid feature drift.

- **Toy model artifact:** A toy RandomForest model was trained during the current development work and persisted locally at `backend/models_store/LeBron_James.pkl`. Large model artifacts should not be committed directly to `git`. Use one of these options instead:
	- Track large artifacts with Git LFS (recommended for small teams):

		```pwsh
		git lfs install
		git lfs track "backend/models_store/*.pkl"
		git add .gitattributes
		git add backend/models_store/LeBron_James.pkl
		git commit -m "chore(models): add LeBron_James.pkl via LFS"
		```

	- Publish models as GitHub Release assets or store them in an external artifact storage (S3, GCS) and provide a download script that places files into `backend/models_store/` during CI or local setup.

Mocking / Live NBA integration
--------------------------------

- Production runtime is live-only: the backend no longer fabricates `recentGames` or other NBA data.
- The previous behavior that injected deterministic mock data via `ENABLE_DEV_MOCKS` has been removed from production code.
- Tests and developer tooling that need deterministic behavior must explicitly stub or monkeypatch `backend.services.nba_stats_client`, or use the `--mock` flags available on some helper scripts (these flags are explicit dev-time conveniences and do not alter production behavior).
- Gated live-network tests can be run from CI using the manual workflow: `.github/workflows/live-nba-integration.yml` (use the "Run workflow" button and ensure any required API credentials are available in the runner environment).

Guidance:

- For deterministic unit/integration tests: monkeypatch `nba_stats_client` in your test (see `backend/tests/*` for examples).
- For quick developer smoke runs you can pass `--mock` to scripts that support it (e.g., `scripts/generate_sample_prompt.*`). These flags are for local/dev use only.
- Do NOT rely on `ENABLE_DEV_MOCKS` as a runtime toggle in production; CI or production environments should never enable mock fallbacks.

- **Changelog:** See `CHANGELOG.md` in the repo root for recent notable changes and short release notes.
