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
- If you have Redis running and configured, the backend will use it for caching (player context + predict TTLs).

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
