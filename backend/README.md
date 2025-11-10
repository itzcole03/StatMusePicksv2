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

Quick verification script (starts backend and runs prompt builder):

```pwsh
.\scripts\run_local_backend_and_prompt.ps1 -Mode venv -Player "LeBron James" -Stat points -Limit 5
```

If you want me to wire the frontend to call this service and verify end-to-end,
I can update `src/services/nbaService.ts` and provide the exact commands to run both processes.