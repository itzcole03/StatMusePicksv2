"""Backend entrypoint wrapper.

This file exposes `app` for tools that expect `backend.main:app` and
provides minimal startup/shutdown hooks.
"""
from fastapi import FastAPI, Response, Request
from pydantic import BaseModel
from typing import List
from backend.schemas.player_context import PlayerContextResponse
import os
import importlib
import pathlib
from typing import Optional
import time

from backend.services import nba_stats_client
from backend.services.cache import redis_get_json, redis_set_json, get_redis
from backend.services.cache import get_cache_metrics
try:
    # Prefer using our metrics helper which supports multiprocess mode.
    from backend.services.metrics import generate_latest, CONTENT_TYPE_LATEST
except Exception:
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
import logging

logger = logging.getLogger(__name__)

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
    # DB status (quick heuristic with optional async connectivity test)
    try:
        from backend import db as backend_db
        db_url = getattr(backend_db, 'DATABASE_URL', None)
    except Exception:
        db_url = os.environ.get('DATABASE_URL') or 'sqlite+aiosqlite:///./dev.db'

    db_ok = False
    db_error = None
    try:
        if db_url and db_url.startswith('sqlite'):
            # check for local file existence
            db_path = pathlib.Path('./dev.db')
            db_ok = db_path.exists()
        else:
            # try an async DB connection if backend.db available
            try:
                from backend import db as backend_db
                backend_db._ensure_engine_and_session()
                if getattr(backend_db, 'engine', None) is not None:
                    async with backend_db.engine.connect() as conn:
                        await conn.run_sync(lambda sync_conn: None)
                    db_ok = True
                else:
                    db_ok = bool(db_url)
            except Exception as e:
                db_ok = False
                db_error = str(e)
    except Exception as e:
        db_ok = False
        db_error = str(e)

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

    try:
        cache_metrics = get_cache_metrics()
    except Exception:
        cache_metrics = None

    return {
        'db': {'url': db_url, 'ok': db_ok, 'error': db_error},
        'redis': {'installed': redis_installed, 'env': redis_url, 'can_connect': redis_can_connect, 'error': redis_error},
        'cache_metrics': cache_metrics,
    }



@app.get('/metrics')
async def _metrics():
    """Expose Prometheus metrics if available (dev-only)."""
    if generate_latest is None:
        return {"error": "prometheus_client not installed"}
    try:
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception:
        return {"error": "failed to render metrics"}
    


@app.get("/api/player_context", response_model=PlayerContextResponse)
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


class BatchPlayerRequest(BaseModel):
    # Accept either `player` or `player_name` keys so callers/tests can use either shape.
    player: Optional[str] = None
    player_name: Optional[str] = None
    limit: Optional[int] = None


@app.post("/api/batch_player_context")
async def batch_player_context(request: Request, default_limit: int = 8, max_concurrency: int = 6):
    """Fetch player contexts for a batch of players in parallel (bounded concurrency).

    Returns a dict with `results` (list) and `errors` (list of player names with errors).
    Each result is the same shape as `/api/player_context`.
    """
    import asyncio

    # read raw JSON to avoid Pydantic body validation differences between callers
    data = await request.json()
    if not isinstance(data, list):
        return {"results": [], "errors": [{"error": "request body must be an array of player requests"}]}

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _fetch_one(req: dict):
        # support either `player` or `player_name` keys
        name = req.get("player") or req.get("player_name")
        lim = req.get("limit") or default_limit
        try:
            async with semaphore:
                # Reuse existing route logic to ensure caching and behavior are consistent
                res = await player_context(name, lim)
                return {"player_name": name, "ok": True, "context": res}
        except Exception as e:
            return {"player_name": name, "ok": False, "error": str(e)}

    tasks = [asyncio.create_task(_fetch_one(r)) for r in requests]
    gathered = await asyncio.gather(*tasks)

    results = [g for g in gathered if g.get("ok")]
    errors = [g for g in gathered if not g.get("ok")]

    return {"results": results, "errors": errors}


@app.get("/api/db_health")
async def db_health():
    """Check DB connectivity and basic query health."""
    try:
        from backend import db as backend_db

        backend_db._ensure_engine_and_session()
        if getattr(backend_db, 'engine', None) is None:
            return {"ok": False, "db": {"ok": False, "error": "no engine"}}

        # run a lightweight sync no-op to validate connection
        async with backend_db.engine.connect() as conn:
            await conn.run_sync(lambda sync_conn: None)

        return {"ok": True, "db": {"ok": True}}
    except Exception as e:
        logger.exception("DB health check failed")
        return {"ok": False, "db": {"ok": False, "error": str(e)}}


async def _startup():
    # Initialize DB engine/session factory so the app is ready to use DB.
    try:
        from backend import db as backend_db

        # ensure engine and sessionmaker are created
        backend_db._ensure_engine_and_session()

        # quick connectivity check for non-sqlite DBs
        try:
            if getattr(backend_db, 'engine', None) is not None:
                async with backend_db.engine.connect() as conn:
                    # no-op sync call to validate connection
                    await conn.run_sync(lambda sync_conn: None)
        except Exception as e:
            logger.warning("DB engine created but connectivity test failed: %s", e)

    except Exception as e:
        logger.debug("No backend.db available on startup: %s", e)

    return None


async def _shutdown():
    # placeholder for graceful shutdown
    return None


# Register lifecycle handlers using `add_event_handler` instead of the
# `@app.on_event` decorator which is deprecated. This preserves the same
# behavior while avoiding decorator deprecation warnings.
try:
    app.add_event_handler("startup", _startup)
    app.add_event_handler("shutdown", _shutdown)
except Exception:
    # If `app` doesn't support adding handlers for some reason, ignore
    # to avoid import-time failures in tests that import this module.
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
