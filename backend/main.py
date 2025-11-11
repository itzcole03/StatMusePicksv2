"""Backend entrypoint wrapper.

This file exposes `app` for tools that expect `backend.main:app` and
provides minimal startup/shutdown hooks.
"""
from fastapi import FastAPI
import os
import importlib
import pathlib
from typing import Optional
import time

from backend.services import nba_stats_client
from backend.services.cache import redis_get_json, redis_set_json, get_redis

try:
    # import the app defined in fastapi_nba.py
    from .fastapi_nba import app as nba_app
except Exception:
    # fallback: create an empty FastAPI app so the module always imports
    nba_app = FastAPI(title="NBA Data Backend (fallback)")

app: FastAPI = nba_app

if not any(getattr(r, "path", None) == "/health" for r in app.routes):
    @app.get("/health")
    async def _health():
        return {"ok": True}


@app.get("/debug/status")
async def _debug_status():
    """Return simple DB and Redis connectivity checks for local dev."""
    # DB status (quick heuristic)
    try:
        from backend import db as backend_db
        db_url = getattr(backend_db, 'DATABASE_URL', None)
    except Exception:
        db_url = os.environ.get('DATABASE_URL') or 'sqlite+aiosqlite:///./dev.db'

    db_ok = False
    try:
        if db_url and db_url.startswith('sqlite'):
            # check for local file existence
            db_path = pathlib.Path('./dev.db')
            db_ok = db_path.exists()
        else:
            # assume non-sqlite DB is configured if URL present
            db_ok = bool(db_url)
    except Exception:
        db_ok = False

    # Redis status
    redis_url = os.environ.get('REDIS_URL')
    redis_installed = importlib.util.find_spec('redis') is not None
    redis_can_connect = False
    redis_error = None
    if redis_installed:
        try:
            import redis
            url = redis_url or 'redis://127.0.0.1:6379'
            client = redis.from_url(url, socket_connect_timeout=1)
            redis_can_connect = client.ping()
        except Exception as e:
            redis_error = str(e)

    return {
        'db': {'url': db_url, 'ok': db_ok},
        'redis': {'installed': redis_installed, 'env': redis_url, 'can_connect': redis_can_connect, 'error': redis_error}
    }


@app.get("/api/player_context")
async def player_context(player_name: Optional[str] = None, limit: int = 8):
    """Return recent games and simple numeric context for a player.

    - Tries Redis cache first (key: `player_context:{player_name}:{limit}`).
    - Falls back to `nba_api` via `backend.services.nba_stats_client`.
    """
    if not player_name:
        return {"error": "player_name is required"}

    key = f"player_context:{player_name}:{limit}"

    # Try async redis cache
    try:
        cached = await redis_get_json(key)
        if cached:
            cached["cached"] = True
            return cached
    except Exception:
        # ignore cache errors
        pass

    # Resolve player id and fetch recent games
    try:
        pid = nba_stats_client.find_player_id_by_name(player_name) or nba_stats_client.find_player_id(player_name)
    except Exception:
        pid = None

    recent = []
    try:
        if pid:
            recent = nba_stats_client.fetch_recent_games_by_id(pid, limit=limit)
        else:
            recent = nba_stats_client.fetch_recent_games_by_name(player_name, limit=limit)
    except Exception:
        recent = []

    # derive simple seasonAvg if possible
    season_avg = None
    try:
        vals = [g.get('statValue') or g.get('PTS') or g.get('points') for g in recent]
        vals = [v for v in vals if v is not None]
        if vals:
            season_avg = sum(vals) / len(vals)
    except Exception:
        season_avg = None

    out = {
        "player": player_name,
        "player_id": pid,
        "recentGames": recent,
        "seasonAvg": season_avg,
        "fetchedAt": int(time.time()),
        "cached": False,
    }

    # store in cache for 6 hours
    try:
        await redis_set_json(key, out, ex=60 * 60 * 6)
    except Exception:
        pass

    return out


@app.on_event("startup")
async def _startup():
    # placeholder for startup tasks (DB connections, caches)
    return None


@app.on_event("shutdown")
async def _shutdown():
    # placeholder for graceful shutdown
    return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
