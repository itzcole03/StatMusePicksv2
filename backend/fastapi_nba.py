from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import time
import os
import json
import logging
import re

# Caching
from cachetools import TTLCache

# Optional Redis support
redis_client = None
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    try:
        import redis as _redis
        redis_client = _redis.from_url(REDIS_URL)
    except Exception:
        redis_client = None

# NOTE: `nba_api` is an optional dependency. Install it in the backend venv.
try:
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.endpoints import playercareerstats
except Exception:
    players = None
    playergamelog = None
    playercareerstats = None

app = FastAPI(title="NBA Data Backend (example)")

# basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_nba")

# Allow requests from local frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    fetchedAt: str

# in-memory TTL cache
cache = TTLCache(maxsize=1000, ttl=60 * 10)

STAT_MAP = {
    'points': 'PTS', 'pts': 'PTS',
    'assists': 'AST', 'ast': 'AST',
    'rebounds': 'REB', 'reb': 'REB',
    'stl': 'STL', 'steals': 'STL',
    'blk': 'BLK', 'blocks': 'BLK',
}


def find_player_id_by_name(name: str):
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


def fetch_recent_games(player_id: int, limit: int = 8):
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

    # Attach debug info when requested (non-breaking)
    if debug:
        out['debug'] = debug_info

    # store in caches
    cache[cache_key] = out
    if redis_client:
        try:
            redis_client.setex(cache_key, 60 * 10, json.dumps(out))
        except Exception:
            pass

    return out


class PlayerContextRequest(BaseModel):
    player: str
    stat: Optional[str] = 'points'
    limit: Optional[int] = 8


@app.post('/api/player_context', response_model=PlayerSummary)
def api_player_context(req: PlayerContextRequest):
    """POST wrapper for client usage. Accepts JSON body and returns the same
    structured PlayerSummary as `/player_summary` but avoids CORS/query-string
    related issues for some clients."""
    return player_summary(player=req.player, stat=req.stat or 'points', limit=req.limit or 8)


@app.post('/api/batch_player_context')
def api_batch_player_context(requests: List[PlayerContextRequest]):
    """Accepts a list of player context requests and returns an array of
    player summaries. If an individual request fails (player not found), the
    response will include an object with `error` for that entry to enable
    partial results handling on the client."""
    results = []
    for r in requests:
        try:
            res = player_summary(player=r.player, stat=r.stat or 'points', limit=r.limit or 8)
            results.append(res)
        except HTTPException as he:
            results.append({'player': r.player, 'error': he.detail})
        except Exception as e:
            results.append({'player': r.player, 'error': str(e)})
    return results


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


@app.post('/api/predict')
async def api_predict(req: PredictionRequest):
    if ml_service is None:
        raise HTTPException(status_code=503, detail='ML service unavailable')
    result = await ml_service.predict(
        player_name=req.player,
        stat_type=req.stat,
        line=req.line,
        player_data=req.player_data or {},
        opponent_data=req.opponent_data or {}
    )
    return result


@app.post('/api/batch_predict')
async def api_batch_predict(requests: List[PredictionRequest]):
    results = []
    for r in requests:
        try:
            if ml_service is None:
                results.append({'player': r.player, 'error': 'ML service unavailable'})
            else:
                res = await ml_service.predict(
                    player_name=r.player,
                    stat_type=r.stat,
                    line=r.line,
                    player_data=r.player_data or {},
                    opponent_data=r.opponent_data or {}
                )
                results.append(res)
        except Exception as e:
            results.append({'player': r.player, 'error': str(e)})
    return {'predictions': results}


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


