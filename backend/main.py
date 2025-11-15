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
from backend.services import feature_engineering
from backend.services.model_registry import PlayerModelRegistry
from backend.services.ml_prediction_service import MLPredictionService, PlayerModelRegistry as InMemoryPlayerModelRegistry
from fastapi import HTTPException
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
async def player_context(player_name: Optional[str] = None, player: Optional[str] = None, limit: int = 8):
    """Return recent games and simple numeric context for a player.

    - Tries Redis cache first (key: `player_context:{player_name}:{limit}`).
    - Falls back to `nba_api` via `backend.services.nba_stats_client`.
    """
    # Accept either `player_name` or `player` query param for compatibility
    if not player_name:
        player_name = player
    if not player_name:
        # Return a proper 400-like shape to avoid response_model validation errors
        return {"error": "player_name is required"}

    key = f"player_context:{player_name}:{limit}"

    # Try async redis cache
    try:
        cached = await redis_get_json(key)
        # If cached exists and appears to be a full enriched context, return it.
        # However, older cached entries may not include `rollingAverages` (added
        # in a later release). Treat such entries as stale and fall through to
        # rebuild the enhanced context so callers receive consistent fields.
        # If the cached payload already indicates it's a cached response,
        # respect it (tests may monkeypatch redis_get_json to return a cached
        # payload). Otherwise, prefer caches that include the enriched
        # `rollingAverages` field; treat older caches without that field as
        # stale so we rebuild enhanced context.
        if cached and cached.get("cached") is True:
            return cached
        if cached and cached.get("rollingAverages") is not None:
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

    # NOTE: Removed dev-only deterministic mock fallback. The NBA integration
    # is now live-only in production code. Tests and dev scripts should
    # explicitly monkeypatch or provide stub clients when deterministic
    # behavior is required.

    out = {
        "player": player_name,
        "player_id": pid,
        "recentGames": recent,
        "seasonAvg": season_avg,
        # will populate enhanced context below
        "rollingAverages": None,
        "contextualFactors": {},
        "opponentInfo": None,
        "fetchedAt": int(time.time()),
        "cached": False,
    }

    # store in cache for 6 hours
    try:
        await redis_set_json(key, out, ex=60 * 60 * 6)
    except Exception:
        pass

    # Build enhanced numeric context using local feature engineering helpers
    try:
        player_data = {"seasonAvg": season_avg, "recentGames": recent, "contextualFactors": {}}
        # opponent info: try to extract from most recent game if available
        opponent_info = None
        if recent and isinstance(recent, list) and len(recent) > 0:
            g0 = recent[0]
            opponent_info = {
                "teamId": g0.get("opponentTeamId") or g0.get("opponent") or g0.get("opponentAbbrev"),
                "defensiveRating": g0.get("opponentDefRating") or g0.get("opponentDef") or None,
                "pace": g0.get("opponentPace") or None,
            }
        out["opponentInfo"] = opponent_info

        df = feature_engineering.engineer_features(player_data, opponent_info)
        if df is not None and not df.empty:
            # extract rolling averages and opponent-adjusted fields
            row = df.iloc[0].to_dict()
            rolling_keys = [k for k in row.keys() if k.startswith("last_") or "exponential" in k or k.startswith("wma_") or k in ("slope_10", "momentum_vs_5_avg")]
            rolling = {k: row.get(k) for k in rolling_keys}
            out["rollingAverages"] = rolling
            out["contextualFactors"] = {"is_home": int(row.get("is_home", 0)), "days_rest": int(row.get("days_rest", 0)), "is_back_to_back": int(row.get("is_back_to_back", 0))}
    except Exception:
        # non-fatal: return best-effort context
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


@app.post("/api/admin/promote")
async def admin_promote(request: Request):
    """Admin endpoint to mark a model version as promoted.

    Protects access with `X-ADMIN-KEY` header (value read from `ADMIN_API_KEY`).
    Body: JSON {"player": "Name", "version": "v123", "promoted_by": "alice", "notes": "...", "write_legacy": true}
    """
    try:
        # simple header-based auth for admin actions
        admin_key = os.environ.get("ADMIN_API_KEY")
        hdr = request.headers.get("x-admin-key") or request.headers.get("X-ADMIN-KEY")
        if admin_key and hdr != admin_key:
            raise HTTPException(status_code=401, detail="unauthorized")

        body = await request.json()
        player = body.get("player") or body.get("player_name")
        if not player:
            raise HTTPException(status_code=400, detail="player is required")

        version = body.get("version")
        promoted_by = body.get("promoted_by") or body.get("by")
        notes = body.get("notes")
        write_legacy = bool(body.get("write_legacy", False))

        store_dir = os.environ.get("MODEL_STORE_DIR", "backend/models_store")
        reg = PlayerModelRegistry(store_dir)
        meta = reg.promote_model(player, version=version, promoted_by=promoted_by, notes=notes, write_legacy_pkl=write_legacy)
        if meta is None:
            raise HTTPException(status_code=404, detail="player/version not found")
        return {"ok": True, "metadata": meta}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("admin promote failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/load")
async def api_models_load(request: Request):
    """Load a persisted model for a player into the in-memory registry.

    Body: {"player": "Name", "model_dir": "optional dir"}
    """
    try:
        body = await request.json()
        player = body.get("player") or body.get("player_name")
        if not player:
            raise HTTPException(status_code=400, detail="player is required")

        model_dir = body.get("model_dir") or os.environ.get("MODEL_STORE_DIR")
        svc = MLPredictionService(model_dir=model_dir)
        wrapper = svc.registry.load_model(player)
        loaded = wrapper is not None
        count = len(svc.registry._models.get(player, []))
        # Persist the runtime registry onto the app so subsequent requests
        # (e.g., /api/predict) can reuse the loaded models without re-loading
        # from disk on every request. This is intentionally best-effort and
        # only affects the in-process runtime used in dev and tests.
        try:
            app.state.model_registry = svc.registry
        except Exception:
            pass
        return {"ok": True, "player": player, "loaded": loaded, "versions": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("models.load failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
async def api_predict(request: Request):
    """Predict endpoint for a single player.

    Body: {"player": "Name", "stat": "PTS", "line": 10.5, "player_data": {...}}
    """
    try:
        body = await request.json()
        player = body.get("player") or body.get("player_name")
        stat = body.get("stat")
        line = body.get("line")
        player_data = body.get("player_data") or body.get("context") or {}
        model_dir = body.get("model_dir") or os.environ.get("MODEL_STORE_DIR")
        if not player or stat is None or line is None:
            raise HTTPException(status_code=400, detail="player, stat and line are required")

        # Prefer a shared runtime registry when available so we avoid
        # re-loading artifacts repeatedly in tests/dev.
        if getattr(app.state, "model_registry", None) is not None:
            svc = MLPredictionService(registry=app.state.model_registry)
        else:
            svc = MLPredictionService(model_dir=model_dir)
        # attempt to load model on demand (best-effort)
        try:
            svc.registry.load_model(player)
        except Exception:
            pass
        # If load_model didn't register a model (different registry
        # implementations may behave differently), attempt a legacy
        # `.pkl` load from the provided `model_dir` or the default
        # `backend/models_store` and register it into the in-memory
        # registry so subsequent prediction uses the persisted model.
        try:
            if svc.registry.get_model(player) is None:
                import joblib
                from pathlib import Path
                safe = player.replace(' ', '_')
                candidates = []
                if model_dir:
                    candidates.append(Path(model_dir) / f"{safe}.pkl")
                candidates.append(Path('backend/models_store') / f"{safe}.pkl")
                for p in candidates:
                    try:
                        if p.exists():
                            m = joblib.load(p)
                            # register into the runtime registry (do not re-persist)
                            try:
                                svc.registry.save_model(player, m, persist=False)
                            except Exception:
                                # best-effort only
                                svc.registry._models.setdefault(player, []).append(svc.registry.SimpleModelWrapper(m) if hasattr(svc.registry, 'SimpleModelWrapper') else svc.registry._models.setdefault(player, []))
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        # DEBUG: report whether a model is registered for the player
        try:
            has = svc.registry.get_model(player) is not None
            print(f"DEBUG: model registered for {player}: {has}")
        except Exception:
            print(f"DEBUG: model registered for {player}: ERROR")

        res = await svc.predict(player, stat, float(line), player_data)
        return {"ok": True, "prediction": res}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("predict failed")
        raise HTTPException(status_code=500, detail=str(e))


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
