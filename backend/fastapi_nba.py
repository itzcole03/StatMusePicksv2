from fastapi import FastAPI, HTTPException, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import time
import os
import json
import logging
import re
from typing import Dict
from contextlib import asynccontextmanager

# Caching
from cachetools import TTLCache

# Optional Redis support via the shared cache helper
redis_client = None
try:
    from .services.cache import get_redis
    redis_client = get_redis()
except Exception:
    redis_client = None

# NOTE: `nba_api` is an optional dependency. Install it in the backend venv.
try:
    # Prefer using the centralized client which encapsulates imports and caching
    from .services.nba_stats_client import find_player_id_by_name, fetch_recent_games
    players = None
    playergamelog = None
    playercareerstats = None
except Exception:
    # Fall back to direct `nba_api` imports (older setups)
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.endpoints import playercareerstats
    except Exception:
        players = None
        playergamelog = None
        playercareerstats = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_nba")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Lifespan handler to replace deprecated startup/shutdown events.

    The startup phase preloads persisted models into the ML registry so the
    service is ready to serve requests without lazy initialization. Shutdown
    code may be added after the ``yield`` if cleanup is required.
    """
    # Startup
    try:
        # Ensure registry exists and ml_service is initialized
        global registry, ml_service
        if registry is None:
            try:
                from backend.services.model_registry import ModelRegistry as _MR
                registry = _MR()
            except Exception:
                registry = None

        if ml_service is None:
            try:
                from .services import MLPredictionService as _MS
                ml_service = _MS()
            except Exception:
                ml_service = None

        model_dir = None
        if registry is not None:
            model_dir = registry.model_dir
        elif ml_service is not None and hasattr(ml_service, 'registry'):
            try:
                model_dir = ml_service.registry.model_dir
            except Exception:
                model_dir = None

        if model_dir:
            # load all .pkl models found in the dir
            for fname in sorted(os.listdir(model_dir)):
                if not fname.endswith('.pkl') or fname.endswith('_calibrator.pkl'):
                    continue
                player = fname[:-4].replace('_', ' ')
                try:
                    # prefer loading into the ml_service registry if available
                    if ml_service is not None and hasattr(ml_service, 'registry'):
                        ml_service.registry.load_model(player)
                    elif registry is not None:
                        registry.load_model(player)
                except Exception:
                    logger.exception('Failed to preload model %s', fname)
    except Exception:
        logger.exception('Error during startup model preload')

    yield

    # Shutdown (no-op placeholder)
    try:
        pass
    except Exception:
        logger.exception('Error during lifespan shutdown')


# Create the FastAPI app with the lifespan handler and configure CORS
app = FastAPI(title="NBA Data Backend (example)", lifespan=_lifespan)

# Allow requests from local frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _global_exception_handler(request, exc):
    """Catch-all exception handler to return 500 JSON and log the error
    without bringing down the server process.
    """
    logger.exception('Unhandled exception: %s', exc)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": "internal_server_error"})

class GameItem(BaseModel):
    gameDate: str
    matchup: Optional[str]
    statValue: Optional[float]
    raw: dict

class PlayerSummary(BaseModel):
    player: str
    stat: str
    league: str = "nba"
    recent: Optional[str]
    recentGames: List[GameItem]
    seasonAvg: Optional[float]
    lastGameDate: Optional[str] = None
    lastSeason: Optional[str] = None
    contextualFactors: Optional[dict] = None
    fetchedAt: str


try:
    from pydantic import ConfigDict
except Exception:
    ConfigDict = None

if ConfigDict is not None:
    PlayerSummary.model_config = ConfigDict(json_schema_extra={
        "example": {
            "player": "LeBron James",
            "stat": "points",
            "league": "nba",
            "recentGames": [],
            "seasonAvg": 27.5,
            "fetchedAt": "2025-01-01T00:00:00Z",
        }
    })

# in-memory TTL cache
cache = TTLCache(maxsize=1000, ttl=60 * 10)

STAT_MAP = {
    'points': 'PTS', 'pts': 'PTS',
    'assists': 'AST', 'ast': 'AST',
    'rebounds': 'REB', 'reb': 'REB',
    'stl': 'STL', 'steals': 'STL',
    'blk': 'BLK', 'blocks': 'BLK',
}

# Simple in-memory token-bucket rate limiter per client IP for batch endpoints.
# Keyed by client host. This is a best-effort limiter intended for dev/low-traffic
# use; in production prefer Redis-based or proxy-level rate limiting.
_rate_buckets: Dict[str, Dict[str, float]] = {}
RATE_LIMIT_RPM = int(os.environ.get('BATCH_MAX_RPM', '120'))  # requests per minute

def _consume_tokens(key: str, amount: int) -> bool:
    """Attempt to consume `amount` tokens for `key`. Returns True if allowed.

    Prefer Redis-backed token bucket if `redis_client` is available. Otherwise
    fall back to the in-process token bucket stored in `_rate_buckets`.
    """
    # If Redis is configured, use an atomic Lua script to manage the token bucket.
    if redis_client is not None:
        try:
            # Lua script: refill tokens based on elapsed time, check and deduct.
            # KEYS[1] -> bucket key
            # ARGV[1] -> now (float seconds)
            # ARGV[2] -> rate_limit_per_minute
            # ARGV[3] -> amount to consume
            lua = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local req = tonumber(ARGV[3])
local data = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then
  tokens = rate
  last = now
end
local elapsed = now - last
local refill = elapsed * (rate / 60.0)
tokens = math.min(rate, tokens + refill)
if tokens >= req then
  tokens = tokens - req
  redis.call('HMSET', key, 'tokens', tostring(tokens), 'last', tostring(now))
  redis.call('EXPIRE', key, 120)
  return 1
else
  redis.call('HMSET', key, 'tokens', tostring(tokens), 'last', tostring(now))
  redis.call('EXPIRE', key, 120)
  return 0
end
"""
            now = time.time()
            # Some Redis clients expect bytes/str; use eval
            allowed = redis_client.eval(lua, 1, f"rate_bucket:{key}", now, RATE_LIMIT_RPM, amount)
            return bool(int(allowed))
        except Exception:
            # If Redis fails, gracefully fall back to in-process limiter below
            pass

    # Fallback: in-process token bucket
    now = time.time()
    bucket = _rate_buckets.get(key)
    if bucket is None:
        bucket = {'tokens': float(RATE_LIMIT_RPM), 'last': now}
        _rate_buckets[key] = bucket

    elapsed = now - bucket['last']
    # refill
    refill = elapsed * (RATE_LIMIT_RPM / 60.0)
    bucket['tokens'] = min(float(RATE_LIMIT_RPM), bucket['tokens'] + refill)
    bucket['last'] = now

    if bucket['tokens'] >= amount:
        bucket['tokens'] -= amount
        return True

    return False


def find_player_id_by_name(name: str):
    # If central client available, use it
    try:
        from .services.nba_stats_client import find_player_id_by_name as _client_fn

        return _client_fn(name)
    except Exception:
        pass

    if players is None:
        return None
    # Try exact lookup
    try:
        matches = players.find_players_by_full_name(name)
        if matches:
            return matches[0]['id']
    except Exception:
        pass

    # Normalize name and try again
    def normalize(n: str):
        n = n.lower()
        n = re.sub(r"[,\.]", "", n)
        n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
        n = re.sub(r"\s+", " ", n).strip()
        return n

    target = normalize(name)
    try:
        allp = players.get_players()
    except Exception:
        return None

    # First look for exact normalized full name
    for p in allp:
        if normalize(p.get('full_name', '')) == target:
            return p['id']

    # Then partial contains
    for p in allp:
        if target in normalize(p.get('full_name', '')):
            return p['id']

    return None


def model_to_dict(model):
    """Return a plain dict from a Pydantic model with v1/v2 compatibility.

    Some deployments already use Pydantic v2's `model_dump()` while others
    remain on v1 which exposes `dict()`. Use whichever is available to
    preserve backwards compatibility and silence deprecation warnings.
    """
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        try:
            return model.model_dump()
        except Exception:
            pass
    if hasattr(model, "dict"):
        try:
            return model.dict()
        except Exception:
            pass
    # Last resort: attempt to coerce to dict
    try:
        return dict(model)
    except Exception:
        return model


def fetch_recent_games(player_id: int, limit: int = 8):
    # Prefer centralized client
    try:
        from .services.nba_stats_client import fetch_recent_games as _client_fn

        return _client_fn(player_id, limit)
    except Exception:
        pass

    if playergamelog is None:
        return []
    # `nba_api` PlayerGameLog signature varies between versions; use the simple
    # constructor form that accepts `player_id` only to maximize compatibility.
    gl = playergamelog.PlayerGameLog(player_id=player_id)
    df = gl.get_data_frames()[0]
    recent = df.head(limit)
    return recent.to_dict(orient='records')


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/player_summary', response_model=PlayerSummary)
def player_summary(player: str, stat: str = 'points', limit: int = 8, debug: Optional[int] = Query(0)):
    cache_key = f"player_summary:{player}:{stat}:{limit}"

    # Check Redis cache first
    if redis_client:
        try:
            raw = redis_client.get(cache_key)
            if raw:
                data = json.loads(raw.decode('utf-8')) if isinstance(raw, (bytes, bytearray)) else json.loads(raw)
                data['cached'] = True
                return data
        except Exception:
            pass

    # Check in-memory cache
    if cache_key in cache:
        out = cache[cache_key]
        out['cached'] = True
        return out

    pid = find_player_id_by_name(player)
    debug_info = { 'player_query': player, 'found_player_id': pid }
    if not pid:
        raise HTTPException(status_code=404, detail='player not found')

    recent = fetch_recent_games(pid, limit)
    debug_info['recent_count'] = len(recent)

    # Build structured games
    recent_games = []
    stat_field = STAT_MAP.get(stat.lower(), stat.upper())
    vals = []
    for g in recent:
        val = g.get(stat_field) if stat_field and stat_field in g else None
        recent_games.append({
            'gameDate': g.get('GAME_DATE'),
            'matchup': g.get('MATCHUP'),
            'statValue': val,
            'raw': g,
        })
        try:
            if val is not None:
                vals.append(float(val))
        except Exception:
            pass

    season_avg = (sum(vals) / len(vals)) if vals else None
    recent_text = None
    if recent_games:
        sample_vals = [str(g['statValue']) if g['statValue'] is not None else 'null' for g in recent_games]
        recent_text = f"Last {len(recent_games)} games {stat}: {', '.join(sample_vals)}"

    # Attempt to determine last game date and last season (factual only)
    last_game_date = None
    last_season = None
    if recent_games:
        try:
            # assume recent_games is ordered most-recent-first
            last_game_date = recent_games[0].get('gameDate')
        except Exception:
            last_game_date = None
    else:
        # try to fetch career seasons to determine last season with data
        if playercareerstats is not None:
            try:
                pcs = playercareerstats.PlayerCareerStats(player_id=pid)
                dfpcs = pcs.get_data_frames()[0]
                if not dfpcs.empty and 'SEASON_ID' in dfpcs.columns:
                    # pick the latest season id (sort descending)
                    try:
                        s = dfpcs['SEASON_ID'].tolist()
                        # take the most recent-looking value
                        last_season = s[0] if s else None
                    except Exception:
                        last_season = None
            except Exception:
                last_season = None

    out = {
        'player': player,
        'stat': stat,
        'league': 'nba',
        'recent': recent_text,
        'recentGames': recent_games,
        'seasonAvg': round(season_avg, 2) if season_avg is not None else None,
        'lastGameDate': last_game_date,
        'lastSeason': last_season,
        'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    # If there are no recent games this season, explicitly mark it (no fallbacks/mocks).
    if not recent_games:
        out['noGamesThisSeason'] = True
        out['note'] = 'No recent games available for this player this season.'

    # Derive simple contextual factors used by feature engineering and frontend:
    # - daysRest: integer days since the previous game (None if insufficient data)
    # - isBackToBack: True if daysRest == 0
    try:
        days_rest = None
        is_b2b = False
        if len(recent_games) >= 2:
            from datetime import datetime

            # recent_games assumed ordered most-recent-first
            d0 = recent_games[0].get('gameDate')
            d1 = recent_games[1].get('gameDate')
            if d0 and d1:
                try:
                    fmt = None
                    # Accept common date formats (ISO-like or nba_api format)
                    for f in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            dt0 = datetime.strptime(d0, f)
                            dt1 = datetime.strptime(d1, f)
                            fmt = f
                            break
                        except Exception:
                            continue
                    if fmt is None:
                        # Fallback: try parsing only the date portion
                        dt0 = datetime.fromisoformat(d0.split('T')[0])
                        dt1 = datetime.fromisoformat(d1.split('T')[0])

                    # days between games minus 1 equals days_rest
                    delta_days = (dt0.date() - dt1.date()).days
                    days_rest = max(0, delta_days - 1)
                    is_b2b = (days_rest == 0)
                except Exception:
                    days_rest = None
                    is_b2b = False

        out['contextualFactors'] = {'daysRest': days_rest, 'isBackToBack': is_b2b}
    except Exception:
        out['contextualFactors'] = {'daysRest': None, 'isBackToBack': False}

    # Attach debug info when requested (non-breaking)
    if debug:
        out['debug'] = debug_info

    # store in caches
    cache[cache_key] = out
    if redis_client:
        try:
            # persist player context longer (6 hours) per roadmap guidance
            redis_client.setex(cache_key, 60 * 60 * 6, json.dumps(out))
        except Exception:
            pass

    return out


class PlayerContextRequest(BaseModel):
    player: str
    stat: Optional[str] = 'points'
    limit: Optional[int] = 8


class BatchPlayerRequest(BaseModel):
    player: str
    stat: Optional[str] = 'points'
    limit: Optional[int] = 8

    class Config:
        schema_extra = {
            "example": {"player": "LeBron James", "stat": "points", "limit": 8}
        }


# Provide Pydantic v2 compatible JSON schema extras when available.
try:
    # pydantic v2
    from pydantic import ConfigDict

    BatchPlayerRequest.model_config = ConfigDict(json_schema_extra={
        "example": {"player": "LeBron James", "stat": "points", "limit": 8}
    })
except Exception:
    pass


@app.post('/api/player_context', response_model=PlayerSummary)
def api_player_context(req: PlayerContextRequest):
    """POST wrapper for client usage. Accepts JSON body and returns the same
    structured PlayerSummary as `/player_summary` but avoids CORS/query-string
    related issues for some clients."""
    return player_summary(player=req.player, stat=req.stat or 'points', limit=req.limit or 8)


MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', '50'))


@app.post('/api/batch_player_context')
async def api_batch_player_context(
    requests: List[BatchPlayerRequest] = Body(
        ...,
        examples={
            "example": {
                "summary": "Batch of players",
                "value": [
                    {"player": "LeBron James", "stat": "points", "limit": 8},
                    {"player": "Stephen Curry", "stat": "points", "limit": 8},
                ],
            }
        },
    ),
    max_concurrency: int = Query(6, description="Max concurrent requests"),
    request_obj: Request = None,
):
    """Accepts a list of player context requests (either `player` or
    `player_name` keys) and returns an array of player summaries. Runs
    requests concurrently up to `max_concurrency`. If an individual request
    fails (player not found), the response will include an object with
    `error` for that entry to enable partial results handling on the client.
    """
    import asyncio

    data = [model_to_dict(r) for r in requests]

    if len(data) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f'max batch size exceeded (max {MAX_BATCH_SIZE})')

    # Rate limit: count requests as number of player items. Use client IP when available.
    client_host = None
    try:
        client_host = request_obj.client.host if request_obj and request_obj.client is not None else 'local'
    except Exception:
        client_host = 'local'

    needed = max(1, len(data))
    allowed = _consume_tokens(client_host, needed)
    if not allowed:
        # Ask client to retry later; include simple hint
        raise HTTPException(status_code=429, detail=f'rate limit exceeded, try later')

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _call_summary(item: dict):
        player = item.get('player') or item.get('player_name')
        stat = item.get('stat') or 'points'
        limit = item.get('limit') or 8

        if not player:
            return {'player': player, 'error': 'player name required'}

        try:
            async with semaphore:
                # `player_summary` is synchronous; run in threadpool to avoid blocking
                res = await asyncio.to_thread(player_summary, player, stat, limit)
                return res
        except HTTPException as he:
            return {'player': player, 'error': he.detail}
        except Exception as e:
            return {'player': player, 'error': str(e)}

    tasks = [asyncio.create_task(_call_summary(item)) for item in data]
    gathered = await asyncio.gather(*tasks)
    return gathered


# --- ML prediction endpoints (scaffold) ---------------------------------
try:
    from .services import MLPredictionService
except Exception:
    MLPredictionService = None


ml_service = MLPredictionService() if MLPredictionService is not None else None


# Model registry endpoints (optional)
try:
    from backend.services.model_registry import ModelRegistry
except Exception:
    ModelRegistry = None

registry = ModelRegistry() if ModelRegistry is not None else None


class PredictionRequest(BaseModel):
    player: str
    stat: str = 'points'
    line: float
    player_data: Optional[dict] = None
    opponent_data: Optional[dict] = None
    class Config:
        schema_extra = {
            "example": {
                "player": "LeBron James",
                "stat": "points",
                "line": 25.5,
                "player_data": {},
                "opponent_data": {}
            }
        }


try:
    from pydantic import ConfigDict

    PredictionRequest.model_config = ConfigDict(json_schema_extra={
        "example": {
            "player": "LeBron James",
            "stat": "points",
            "line": 25.5,
            "player_data": {},
            "opponent_data": {}
        }
    })
except Exception:
    pass


class PredictionResponse(BaseModel):
    player: str
    stat: str
    line: float
    predicted_value: Optional[float] = None
    over_probability: Optional[float] = None
    under_probability: Optional[float] = None
    recommendation: Optional[str] = None
    expected_value: Optional[float] = None
    confidence: Optional[float] = None
    error: Optional[str] = None


try:
    # Attach v2-compatible config if available, keep v1 behavior otherwise.
    from pydantic import ConfigDict
except Exception:
    ConfigDict = None

if ConfigDict is not None:
    PredictionResponse.model_config = ConfigDict(json_schema_extra={
        "example": {
            "player": "LeBron James",
            "stat": "points",
            "line": 25.5,
            "predicted_value": 26.2,
            "over_probability": 0.56,
            "recommendation": "over",
            "confidence": 0.8,
        }
    })


class BatchPredictResponse(BaseModel):
    predictions: List[PredictionResponse]


@app.post('/api/predict', response_model=PredictionResponse, responses={503: {"description": "ML service unavailable"}})
async def api_predict(req: PredictionRequest):
    if ml_service is None:
        raise HTTPException(status_code=503, detail='ML service unavailable')
    # Simple caching by player|stat|line when Redis is available.
    cache_key = f"predict:{req.player}:{req.stat}:{req.line}"
    if redis_client:
        try:
            raw = redis_client.get(cache_key)
            if raw:
                # stored as JSON string
                import json
                return json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception:
            pass

    result = await ml_service.predict(
        player_name=req.player,
        stat_type=req.stat,
        line=req.line,
        player_data=req.player_data or {},
        opponent_data=req.opponent_data or {}
    )

    # store in redis for 1 hour
    if redis_client:
        try:
            import json
            redis_client.setex(cache_key, 60 * 60, json.dumps(result))
        except Exception:
            pass

    return result


@app.post('/api/batch_predict', response_model=BatchPredictResponse, responses={503: {"description": "ML service unavailable"}})
async def api_batch_predict(requests: List[PredictionRequest]):
    results: List[PredictionResponse] = []
    for r in requests:
        try:
            if ml_service is None:
                results.append(PredictionResponse(player=r.player, stat=r.stat, line=r.line, error='ML service unavailable'))
            else:
                res = await ml_service.predict(
                    player_name=r.player,
                    stat_type=r.stat,
                    line=r.line,
                    player_data=r.player_data or {},
                    opponent_data=r.opponent_data or {}
                )
                # coerce into PredictionResponse when possible
                if isinstance(res, dict):
                    results.append(PredictionResponse(**res))
                else:
                    # unknown shape, wrap minimally
                    results.append(PredictionResponse(player=r.player, stat=r.stat, line=r.line, error='unexpected result format'))
        except Exception as e:
            results.append(PredictionResponse(player=r.player, stat=r.stat, line=r.line, error=str(e)))
    return BatchPredictResponse(predictions=results)


# Model management API
@app.get('/api/models')
def api_list_models():
    """List available model files in the model registry directory."""
    if registry is None:
        raise HTTPException(status_code=503, detail='Model registry unavailable')

    try:
        files = []
        for fname in sorted(os.listdir(registry.model_dir)):
            if fname.endswith('.pkl'):
                files.append(fname)
        return {'models': files, 'model_dir': registry.model_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/models/load')
def api_load_model(player: str):
    """Attempt to load a model for a player into the registry (no-op if missing)."""
    if registry is None:
        raise HTTPException(status_code=503, detail='Model registry unavailable')

    try:
        loaded = registry.load_model(player)
        return {'player': player, 'loaded': bool(loaded)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


