"""Data ingestion service scaffold.

This module should contain functions to fetch and normalize external data
from NBA APIs or commercial providers. For now it provides a small
interface and TODO notes for implementation.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import date
from typing import Dict, List

# HTTP client with retries
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Directory to persist raw ingested payloads for auditing
AUDIT_DIR = os.environ.get("INGEST_AUDIT_DIR", "./backend/ingest_audit")
os.makedirs(AUDIT_DIR, exist_ok=True)

# Critical fields required for ingestion; configurable via env var (comma-separated)
CRITICAL_FIELDS = [
    f.strip()
    for f in os.environ.get(
        "INGEST_CRITICAL_FIELDS", "game_date,home_team,away_team"
    ).split(",")
    if f.strip()
]

# Small mapping table to translate common team full names to 3-letter abbreviations.
# Extend this table as needed for other providers or locale variations.
TEAM_NAME_MAP = {
    "los angeles lakers": "LAL",
    "lakers": "LAL",
    "los angeles clippers": "LAC",
    "clippers": "LAC",
    "golden state warriors": "GSW",
    "warriors": "GSW",
    "boston celtics": "BOS",
    "celtics": "BOS",
    "new york knicks": "NYK",
    "knicks": "NYK",
    "chicago bulls": "CHI",
    "bulls": "CHI",
    "miami heat": "MIA",
    "heat": "MIA",
    "brooklyn nets": "BKN",
    "nets": "BKN",
    "houston rockets": "HOU",
    "rockets": "HOU",
    "dallas mavericks": "DAL",
    "mavericks": "DAL",
}


def _normalize_team_name(name: str) -> str:
    """Normalize a team name to a 3-letter abbreviation when possible.

    - Accepts full names, short names, and already-abbreviated values.
    - Returns uppercase 3-letter abbreviation when known; otherwise returns
      the original input (stripped).
    """
    if not name:
        return name
    s = str(name).strip()
    # If already 3-letter uppercase, assume it's an abbreviation
    if len(s) == 3 and s.isupper():
        return s
    key = s.lower()
    # Try direct mapping (TEAM_NAME_MAP may be overridden from JSON file below)
    if key in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[key]
    # Some providers include city + nickname, try last token
    parts = key.split()
    if parts and parts[-1] in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[parts[-1]]
    # fallback: return original uppercased first 3 chars as a weak abbreviation
    return s.upper()[:3]


# Attempt to load a fuller mapping from `backend/data/team_abbrevs.json` if present.
try:
    data_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "team_abbrevs.json")
    )
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as _fh:
                import json as _json

                loaded = _json.load(_fh)
                # Normalize keys to lowercase and values to uppercase
                TEAM_NAME_MAP = {
                    str(k).lower(): str(v).upper() for k, v in loaded.items()
                }
        except Exception:
            logger.debug("Failed to load team_abbrevs.json", exc_info=True)
except Exception:
    # Non-fatal if file read fails
    pass


def invalidate_player_contexts(player_names: List[str]) -> None:
    """Invalidate cached `player_context:{player}:*` entries for given players.

    Uses the synchronous cache helper so callers don't need an event loop.
    """
    try:
        from backend.services import cache as cache_module
    except Exception:
        logger.debug("cache module not available for invalidation")
        return

    for p in player_names:
        try:
            cache_module.redis_delete_prefix_sync(f"player_context:{p}:")
        except Exception:
            logger.exception("Failed to invalidate player_context cache for %s", p)


def invalidate_all_player_contexts() -> None:
    """Invalidate all `player_context:` keys (use with caution)."""
    try:
        from backend.services import cache as cache_module

        cache_module.redis_delete_prefix_sync("player_context:")
    except Exception:
        logger.exception("Failed to invalidate all player_context caches")


async def fetch_yesterday_game_results() -> List[Dict]:
    """Placeholder: Fetch yesterday's game results from data sources.

    Implementations should return a list of normalized game dicts suitable
    for ingestion into the feature store / DB.
    """
    logger.info("fetch_yesterday_game_results called - attempting provider fetch")
    try:
        # Try to delegate to a helper in `nba_stats_client` if present.
        from backend.services import nba_stats_client

        if hasattr(nba_stats_client, "fetch_yesterday_games"):
            return nba_stats_client.fetch_yesterday_games()
    except Exception:
        logger.debug("nba_stats_client helper not available or failed", exc_info=True)

    logger.info("No provider available for yesterday games; returning empty list")
    return []


def save_raw_games(raw: List[Dict], when: date | None = None) -> str:
    """Persist raw fetch results to disk with a timestamped filename.

    Returns the path written or empty string on failure.
    """
    if not raw:
        return ""
    when = when or date.today()
    # Use a stable filename per-day but append batches as JSONL so multiple
    # flushes do not overwrite earlier batches. This preserves all fetched
    # records for auditing while remaining easy to parse line-by-line.
    fname = os.path.join(AUDIT_DIR, f"games_raw_{when.isoformat()}.json")
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # Append each record as a single JSON object per line (JSONL)
        with open(fname, "a", encoding="utf-8") as fh:
            for rec in raw:
                try:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except Exception:
                    # Skip individual records that fail to serialize
                    logger.debug(
                        "Failed to serialize audit record: %s", rec, exc_info=True
                    )
        logger.info("Appended %d raw games to %s", len(raw), fname)
        return fname
    except Exception:
        logger.exception("Failed to append raw games to %s", fname)
        return ""


def normalize_raw_game(raw: Dict) -> Dict:
    """Normalize a raw game row into the internal schema.

    This should map external field names to our canonical names.
    """
    # Make a shallow copy so we don't mutate caller data
    r = dict(raw or {})

    # Map common provider-specific field names to our canonical schema
    # Canonical keys: game_date, game_id, home_team, away_team, home_score, away_score
    synonyms = {
        "game_id": ["game_id", "id", "gid"],
        "home_team": [
            "home_team",
            "homeTeam",
            "homeTeamName",
            "home_team_name",
            "h_team",
            "home",
            "home_team_name",
        ],
        "away_team": [
            "away_team",
            "awayTeam",
            "awayTeamName",
            "away_team_name",
            "a_team",
            "away",
            "away_team_name",
        ],
        "home_score": [
            "home_score",
            "homeScore",
            "home_pts",
            "homePoints",
            "hScore",
            "h_score",
            "h_pts",
            "home_points",
            "home-team-score",
            "homePoints",
        ],
        "away_score": [
            "away_score",
            "awayScore",
            "away_pts",
            "awayPoints",
            "aScore",
            "a_score",
            "a_pts",
            "away_points",
            "away-team-score",
            "awayPoints",
        ],
        "timestamp": ["timestamp", "time", "utc_time", "start_time", "game_time"],
        "date": ["date", "game_date_str", "date_str"],
    }

    for target, keys in synonyms.items():
        if target in r and r.get(target) is not None:
            # already present
            continue
        for k in keys:
            if k in r and r.get(k) is not None:
                r[target] = r.get(k)
                break

    # Normalize score types: convert string numbers to ints when possible
    for score_key in ("home_score", "away_score"):
        val = r.get(score_key)
        if isinstance(val, str):
            try:
                # strip commas and whitespace
                v = int(val.replace(",", "").strip())
                r[score_key] = v
            except Exception:
                # leave as-is if not parseable
                pass

    # Normalize team names to abbreviations when possible
    try:
        if "home_team" in r and r.get("home_team"):
            r["home_team"] = _normalize_team_name(r.get("home_team"))
        if "away_team" in r and r.get("away_team"):
            r["away_team"] = _normalize_team_name(r.get("away_team"))
    except Exception:
        # Be resilient: if normalization fails, leave original values
        logger.debug("Team name normalization failed for record: %s", r, exc_info=True)

    # If a date-like candidate is already present, try to parse it into a
    # datetime so callers get a canonical `game_date` value.
    gd = r.get("game_date") or r.get("date") or r.get("timestamp")
    if gd:
        try:
            import datetime as _dt

            parsed = None
            if isinstance(gd, (_dt.datetime,)):
                parsed = gd
            elif isinstance(gd, (int, float)):
                # epoch seconds vs milliseconds
                if gd > 1e12:
                    parsed = _dt.datetime.fromtimestamp(gd / 1000)
                else:
                    parsed = _dt.datetime.fromtimestamp(gd)
            else:
                # try dateutil then fromisoformat
                try:
                    from dateutil import parser as _parser

                    parsed = _parser.parse(str(gd))
                except Exception:
                    parsed = _dt.datetime.fromisoformat(str(gd))

            if parsed is not None:
                r["game_date"] = parsed
                return r
        except Exception:
            # fall through to the more exhaustive parsing below
            pass

    # Try common alternative fields where providers may store a date/time
    candidates = [
        "date",
        "game_date_str",
        "game_time",
        "start_time",
        "timestamp",
        "utc_time",
        "time",
    ]
    for key in candidates:
        val = r.get(key)
        if not val:
            continue
        try:
            # Numeric epoch (seconds or milliseconds)
            if isinstance(val, (int, float)):
                import datetime as _dt

                # Heuristic: very large numbers are milliseconds
                if val > 1e12:
                    gd = _dt.datetime.fromtimestamp(val / 1000)
                else:
                    gd = _dt.datetime.fromtimestamp(val)
            else:
                # Parse common string formats using dateutil when available
                try:
                    from dateutil import parser as _parser

                    gd = _parser.parse(str(val))
                except Exception:
                    # Fallback to datetime.fromisoformat for ISO-like strings
                    import datetime as _dt

                    gd = _dt.datetime.fromisoformat(str(val))

            r["game_date"] = gd
            return r
        except Exception:
            # Try next candidate
            continue

    # Try to extract a date embedded in an ID field (e.g., YYYYMMDD)
    gid = r.get("game_id") or r.get("id")
    if gid:
        try:
            import datetime as _dt
            import re

            s = str(gid)
            m = re.search(r"(20\d{6})", s)
            if m:
                ymd = m.group(1)
                gd = _dt.datetime.strptime(ymd, "%Y%m%d")
                r["game_date"] = gd
                return r
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", s)
            if m:
                gd = _dt.datetime.fromisoformat(m.group(1))
                r["game_date"] = gd
                return r
        except Exception:
            pass

    return r


## Validation helpers
def detect_missing_values(record: Dict, required_fields: List[str]) -> List[str]:
    """Return a list of required fields that are missing or falsy in record."""
    missing = []
    for f in required_fields:
        if record.get(f) is None or (
            isinstance(record.get(f), str) and record.get(f).strip() == ""
        ):
            missing.append(f)
    return missing


def validate_field_types(record: Dict, schema: Dict[str, type]) -> Dict[str, str]:
    """Validate types for keys in `schema`. Returns dict of field->error message for failures."""
    errors: Dict[str, str] = {}
    for key, expected in (schema or {}).items():
        if key not in record:
            continue
        val = record.get(key)
        if val is None:
            continue
        # allow numbers that are convertible to numeric types
        try:
            if expected is int:
                if not isinstance(val, int):
                    if isinstance(val, str) and val.isdigit():
                        continue
                    # allow float that is integer-valued
                    if isinstance(val, float) and val.is_integer():
                        continue
                    raise TypeError()
            elif expected is float:
                if not isinstance(val, (int, float)):
                    # try converting from string
                    try:
                        float(str(val))
                    except Exception:
                        raise TypeError()
            elif expected is str:
                if not isinstance(val, str):
                    raise TypeError()
            elif (
                expected.__name__ == "datetime"
                or expected.__name__ == "datetime.datetime"
            ):
                # accept datetime-like or ISO strings
                import datetime as _dt

                if not isinstance(val, _dt.datetime):
                    try:
                        from dateutil import parser as _parser

                        _parser.parse(str(val))
                    except Exception:
                        raise TypeError()
            else:
                # fallback: isinstance check
                if not isinstance(val, expected):
                    raise TypeError()
        except Exception:
            errors[key] = f"expected {expected}, got {type(val)}"
    return errors


def detect_outliers(
    records: List[Dict], field: str, z_thresh: float = 3.0
) -> List[int]:
    """Return list of indices where `field` is an outlier.

    Uses a robust Modified Z-score based on median and MAD. Falls back to
    simple z-score if MAD is zero or there are too few points.
    """
    vals = []
    for r in records:
        v = r.get(field)
        try:
            vals.append(float(v))
        except Exception:
            vals.append(None)

    nums = [v for v in vals if v is not None]
    if len(nums) < 2:
        return []

    import math as _math
    import statistics as _stats

    # Robust approach: modified z-score using median and MAD
    med = _stats.median(nums)
    abs_dev = [abs(v - med) for v in nums]
    try:
        mad = _stats.median(abs_dev)
    except Exception:
        mad = 0

    outlier_indices: List[int] = []
    if mad and mad != 0:
        # constant 0.6745 scales MAD to be comparable to std dev for normal data
        for i, v in enumerate(vals):
            if v is None:
                continue
            mod_z = 0.6745 * (v - med) / mad
            if abs(mod_z) >= z_thresh:
                outlier_indices.append(i)
        return outlier_indices

    # Fallback to simple z-score
    mean = _stats.mean(nums)
    try:
        stdev = _stats.pstdev(nums)
    except Exception:
        stdev = 0
    if not stdev or _math.isclose(stdev, 0.0):
        return []
    for i, v in enumerate(vals):
        if v is None:
            continue
        z = abs((v - mean) / stdev)
        if z >= z_thresh:
            outlier_indices.append(i)
    return outlier_indices


# Backwards-compatible wrappers expected by tests
def check_missing_values(record: Dict, required_fields: List[str]) -> List[str]:
    return detect_missing_values(record, required_fields)


def validate_record_types(record: Dict) -> List[str]:
    """Simple record-level validator used by unit tests.

    Returns a list of human-readable error strings (empty on success).
    """
    errs: List[str] = []
    # check date
    if "game_date" in record:
        gd = record.get("game_date")
        if gd is None:
            errs.append("game_date missing")
        else:
            try:
                import datetime as _dt

                if not isinstance(gd, _dt.datetime):
                    from dateutil import parser as _parser

                    _parser.parse(str(gd))
            except Exception:
                errs.append("game_date not parseable")
    # check numeric scores
    for sc in ("home_score", "away_score", "value"):
        if sc in record and record.get(sc) is not None:
            try:
                float(record.get(sc))
            except Exception:
                errs.append(f"{sc} not numeric")
    return errs


def detect_outlier_values(
    records: List[Dict], field: str = "value", z_thresh: float = 3.0
) -> List[int]:
    return detect_outliers(records, field=field, z_thresh=z_thresh)


def validate_batch(records: List[Dict]) -> Dict:
    """Run batch validations and return a summary dict.

    Keys: missing -> list of (index, missing_fields)
          type_errors -> list of (index, [errors])
          outliers -> list of indices
    """
    missing = []
    type_errors = []
    for i, r in enumerate(records):
        # require configurable critical fields for ingestion
        miss = detect_missing_values(r, CRITICAL_FIELDS)
        if miss:
            missing.append((i, miss))
        errs = validate_record_types(r)
        if errs:
            type_errors.append((i, errs))

    outlier_idxs = detect_outliers(records, field="value", z_thresh=3.0)
    return {"missing": missing, "type_errors": type_errors, "outliers": outlier_idxs}


def ingest_games(normalized_games: List[Dict]) -> None:
    """Best-effort ingestion helper that persists normalized game rows

    For now this function focuses on calling cache invalidation for the
    players present in `normalized_games`. It expects each game record to
    include a `player` or `player_name` field (best-effort mapping).
    """
    if not normalized_games:
        return

    # Extract player names from the normalized payloads
    players = set()
    for g in normalized_games:
        name = g.get("player") or g.get("player_name") or g.get("name")
        if name:
            players.add(name)

    if not players:
        # nothing to invalidate
        return

    try:
        invalidate_player_contexts(list(players))
    except Exception:
        logger.exception("ingest_games: failed to invalidate player contexts")


def update_player_stats(normalized_games: List[Dict]) -> int:
    """Placeholder: persist normalized per-player stats.

    Returns number of rows updated (0 by default until implemented).
    """
    logger.info("update_player_stats called with %d records", len(normalized_games))
    if not normalized_games:
        return 0

    # Build a sync SQLAlchemy engine from DATABASE_URL (strip async driver)
    raw_db = os.environ.get("DATABASE_URL")
    if raw_db and "${" in raw_db:
        raw_db = None
    sync = raw_db or "sqlite:///./dev.db"
    sync = sync.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")

    try:
        from datetime import datetime

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool

        from backend.models import Game, Player, PlayerStat

        engine = create_engine(sync, future=True, poolclass=NullPool)
        Session = sessionmaker(bind=engine)
        session = Session()
        # Ensure models are imported and tables exist on this engine. Some tests
        # create the DB file but don't import model modules, so create_all
        # here to guarantee tables exist for the sync engine used below.
        try:
            # importing backend.models registers model classes with Base
            import backend.models  # noqa: F401
            from backend.db import Base

            # Avoid creating tables during Alembic runs (avoids duplicate DDL)
            if not os.environ.get("ALEMBIC_RUNNING"):
                Base.metadata.create_all(engine)
            else:
                logger.debug(
                    "Skipping metadata.create_all on sync engine because ALEMBIC_RUNNING is set"
                )
        except Exception:
            # If this fails, we'll proceed and let subsequent DB ops raise
            # a clear error which will be logged.
            logger.debug(
                "Could not ensure metadata.create_all on sync engine", exc_info=True
            )
    except Exception:
        logger.exception("Failed to create sync DB session for ingestion")
        return 0

    inserted = 0
    skipped = 0
    skipped_samples = []
    try:
        for rec in normalized_games:
            pname = rec.get("player_name") or rec.get("player") or rec.get("name")
            stat_type = rec.get("stat_type")
            value = rec.get("value")
            gdate = rec.get("game_date")

            # Allow records that lack a player name when `player_nba_id` is present.
            rec.get("player_nba_id") is not None or rec.get(
                "Player_ID"
            ) is not None or rec.get("player_id") is not None
            if stat_type is None or value is None or not gdate:
                # log reason for skipping first several records to aid debugging
                logger.debug(
                    "Skipping record due to missing critical field(s): stat_type=%s value=%s gdate=%s keys=%s",
                    stat_type,
                    value,
                    gdate,
                    list(rec.keys()),
                )
                skipped += 1
                if len(skipped_samples) < 10:
                    skipped_samples.append(
                        {
                            "reason": "missing_critical_fields",
                            "player_name": pname,
                            "player_nba_id": rec.get("player_nba_id")
                            or rec.get("Player_ID"),
                            "stat_type": stat_type,
                            "value": value,
                            "game_date": gdate,
                        }
                    )
                continue

            # parse game_date if string
            try:
                if isinstance(gdate, str):
                    # try ISO format
                    gd = datetime.fromisoformat(gdate)
                else:
                    gd = gdate
            except Exception:
                try:
                    # fallback: parse common format
                    from dateutil import parser as _parser

                    gd = _parser.parse(gdate)
                except Exception:
                    logger.debug("Skipping record with invalid game_date: %s", gdate)
                    continue

            # find or create player
            player = None
            nba_pid = rec.get("player_nba_id")
            try:
                if nba_pid is not None:
                    # prefer lookup by nba_player_id when available
                    player = (
                        session.query(Player).filter_by(nba_player_id=nba_pid).first()
                    )
            except Exception:
                player = None

            if player is None and pname:
                # fallback to name lookup
                try:
                    player = session.query(Player).filter_by(name=pname).first()
                except Exception:
                    player = None

            if player is None:
                # create a new player record; prefer name when present
                player = Player(
                    name=pname or f"player_{nba_pid}", nba_player_id=nba_pid
                )
                session.add(player)
                session.flush()
            else:
                # backfill nba_player_id if missing on existing player
                try:
                    if (
                        getattr(player, "nba_player_id", None) is None
                        and nba_pid is not None
                    ):
                        player.nba_player_id = nba_pid
                        session.add(player)
                        session.flush()
                except Exception:
                    pass

            # find or create game (match on date only)
            game = session.query(Game).filter_by(game_date=gd).first()
            if game is None:
                home = rec.get("home_team") or "UNKNOWN"
                away = rec.get("away_team") or "UNKNOWN"
                game = Game(game_date=gd, home_team=home, away_team=away)
                session.add(game)
                session.flush()

            # insert player stat
            try:
                ps = PlayerStat(
                    player_id=player.id,
                    game_id=game.id,
                    stat_type=str(stat_type),
                    value=float(value),
                )
                session.add(ps)
                inserted += 1
            except Exception:
                logger.exception("Failed to add PlayerStat for %s", pname)
                skipped += 1
                if len(skipped_samples) < 10:
                    skipped_samples.append(
                        {
                            "reason": "insert_error",
                            "player_name": pname,
                            "player_nba_id": rec.get("player_nba_id")
                            or rec.get("Player_ID"),
                            "stat_type": stat_type,
                            "value": value,
                            "game_date": str(gd),
                        }
                    )

        session.commit()
    except Exception:
        logger.exception("Error while ingesting player stats")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        try:
            session.close()
        except Exception:
            pass
        try:
            engine.dispose()
        except Exception:
            pass

    logger.info("Inserted %d player_stat rows", inserted)
    if skipped:
        logger.info("Skipped %d player_stat records during ingestion", skipped)
        logger.debug("Sample skipped records: %s", skipped_samples)
    return inserted


def update_team_stats(normalized_games: List[Dict]) -> int:
    """Placeholder: persist normalized per-team stats.

    Returns number of rows updated (0 by default until implemented).
    """
    logger.info("update_team_stats called with %d records", len(normalized_games))
    if not normalized_games:
        return 0

    # Build a sync SQLAlchemy engine from DATABASE_URL (strip async driver)
    raw_db = os.environ.get("DATABASE_URL")
    if raw_db and "${" in raw_db:
        raw_db = None
    sync = raw_db or "sqlite:///./dev.db"
    sync = sync.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")

    try:
        from datetime import datetime

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import NullPool

        from backend.models import Game

        engine = create_engine(sync, future=True, poolclass=NullPool)
        Session = sessionmaker(bind=engine)
        session = Session()
        # Ensure models are imported and tables exist on this engine. Tests may
        # not have imported model modules before creating the DB file, so make
        # sure metadata is present for our sync engine.
        try:
            import backend.models  # noqa: F401
            from backend.db import Base

            # Avoid creating tables during Alembic runs (avoids duplicate DDL)
            if not os.environ.get("ALEMBIC_RUNNING"):
                Base.metadata.create_all(engine)
            else:
                logger.debug(
                    "Skipping metadata.create_all on sync engine for team stats because ALEMBIC_RUNNING is set"
                )
        except Exception:
            logger.debug(
                "Could not ensure metadata.create_all on sync engine for team stats",
                exc_info=True,
            )
    except Exception:
        logger.exception("Failed to create sync DB session for team ingestion")
        return 0

    updated = 0
    # collect team names seen/created in this batch (after substituting defaults)
    teams_in_batch = set()
    try:
        for rec in normalized_games:
            gdate = rec.get("game_date")
            home = rec.get("home_team")
            away = rec.get("away_team")
            home_score = rec.get("home_score")
            away_score = rec.get("away_score")

            if not gdate:
                continue

            # allow partial records: default missing teams to 'UNKNOWN'
            if not home:
                home = "UNKNOWN"
            if not away:
                away = "UNKNOWN"

            # record the teams we saw (useful for downstream aggregation)
            teams_in_batch.add(home)
            teams_in_batch.add(away)

            # parse game_date if string
            try:
                if isinstance(gdate, str):
                    gd = datetime.fromisoformat(gdate)
                else:
                    gd = gdate
            except Exception:
                try:
                    from dateutil import parser as _parser

                    gd = _parser.parse(gdate)
                except Exception:
                    logger.debug(
                        "Skipping team record with invalid game_date: %s", gdate
                    )
                    continue

            # find existing game by date and teams
            game = (
                session.query(Game)
                .filter_by(game_date=gd, home_team=home, away_team=away)
                .first()
            )
            if game is None:
                game = session.query(Game).filter_by(game_date=gd).first()

            if game is None:
                # create new game row
                game = Game(
                    game_date=gd,
                    home_team=home,
                    away_team=away,
                    home_score=home_score,
                    away_score=away_score,
                )
                session.add(game)
                session.flush()
                updated += 1
            else:
                changed = False
                try:
                    if home_score is not None and game.home_score != int(home_score):
                        game.home_score = int(home_score)
                        changed = True
                except Exception:
                    pass
                try:
                    if away_score is not None and game.away_score != int(away_score):
                        game.away_score = int(away_score)
                        changed = True
                except Exception:
                    pass
                if changed:
                    session.add(game)
                    updated += 1

        session.commit()
    except Exception:
        logger.exception("Error while ingesting team stats")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        try:
            session.close()
        except Exception:
            pass
        try:
            engine.dispose()
        except Exception:
            pass

    logger.info("Inserted/updated %d game rows", updated)
    # After updating games, compute derived team metrics for teams seen in this batch
    try:
        # compute per-team aggregates by season (year)
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker
        from sqlalchemy.pool import NullPool as _NullPool

        from backend.models import Game, TeamStat

        # Use a fresh sync engine/session for aggregation and ensure disposal
        engine2 = _create_engine(sync, future=True, poolclass=_NullPool)
        try:
            Session2 = _sessionmaker(bind=engine2)
            session2 = Session2()
            # Use the set of teams discovered while processing the batch.
            teams = set(teams_in_batch)

            for team in teams:
                # aggregate over games where team was home or away
                q = session2.query(Game).filter(
                    (Game.home_team == team) | (Game.away_team == team)
                )
                rows = q.all()
                if not rows:
                    continue
                seasons = set()
                for g in rows:
                    seasons.add(str(getattr(g.game_date, "year", "") or ""))

                # compute season-level stats for each season represented
                for season in seasons:
                    # filter rows for this season
                    season_rows = [
                        g
                        for g in rows
                        if str(getattr(g.game_date, "year", "")) == season
                    ]
                    if not season_rows:
                        continue
                    pf = []
                    pa = []
                    for g in season_rows:
                        if g.home_team == team:
                            if g.home_score is not None:
                                pf.append(g.home_score)
                            if g.away_score is not None:
                                pa.append(g.away_score)
                        else:
                            if g.away_score is not None:
                                pf.append(g.away_score)
                            if g.home_score is not None:
                                pa.append(g.home_score)

                    games_count = len(season_rows)
                    pts_for_avg = float(sum(pf) / len(pf)) if pf else None
                    pts_against_avg = float(sum(pa) / len(pa)) if pa else None

                    # upsert TeamStat by team+season
                    existing = (
                        session2.query(TeamStat)
                        .filter_by(team=team, season=season)
                        .first()
                    )
                    if existing is None:
                        ts = TeamStat(
                            team=team,
                            season=season,
                            games_count=games_count,
                            pts_for_avg=pts_for_avg,
                            pts_against_avg=pts_against_avg,
                        )
                        session2.add(ts)
                    else:
                        existing.games_count = games_count
                        existing.pts_for_avg = pts_for_avg
                        existing.pts_against_avg = pts_against_avg
                        session2.add(existing)

            session2.commit()
        finally:
            try:
                session2.close()
            except Exception:
                pass
            try:
                engine2.dispose()
            except Exception:
                pass
    except Exception:
        logger.exception("Failed to compute/persist TeamStat aggregates")

    return updated


def _process_and_ingest(
    raw: List[Dict], when: date | None = None, dry_run: bool = False
) -> Dict:
    """Process raw fetched rows synchronously: save, normalize, validate, ingest.

    If `dry_run` is True the function will perform normalization and validation
    but will not persist audit files, send alerts, or write to the DB. The
    returned dict contains `dry_run: True` when applicable to aid callers and
    CI smoke tests.
    """
    normalized = [normalize_raw_game(r) for r in raw]

    try:
        validation = validate_batch(normalized)
    except Exception:
        validation = {"missing": [], "type_errors": [], "outliers": []}

    bad_idxs = {i for i, _ in validation.get("missing", [])}
    filtered = [r for idx, r in enumerate(normalized) if idx not in bad_idxs]

    # Always persist raw batches to audit storage so dry-runs also produce
    # a complete audit history. Persistence for alerts and DB writes is still
    # controlled by `dry_run` below.
    audit_path = save_raw_games(raw, when=when)

    try:
        if not dry_run and (validation.get("missing") or validation.get("type_errors")):
            msg = {
                "when": str(when or date.today()),
                "missing_count": len(validation.get("missing", [])),
                "type_error_count": len(validation.get("type_errors", [])),
                "outlier_count": len(validation.get("outliers", [])),
            }
            send_alert(json.dumps(msg))
    except Exception:
        logger.exception("run_daily_sync: failed sending validation alert")

    player_rows = 0
    team_rows = 0
    if not dry_run:
        player_rows = update_player_stats(filtered)
        team_rows = update_team_stats(filtered)

    result = {
        "audit_path": audit_path,
        "player_rows": player_rows,
        "team_rows": team_rows,
        "validation": validation,
        "filtered_out_count": len(normalized) - len(filtered),
    }
    if dry_run:
        result["dry_run"] = True
    return result


async def run_daily_sync_async(when: date | None = None, dry_run: bool = False) -> Dict:
    """Async variant: await provider fetch then delegate to sync processing."""
    raw = []
    # Prefer a sync provider helper when present (tests often inject a sync stub).
    try:
        import sys

        mod = sys.modules.get("backend.services.nba_stats_client")
        if mod and hasattr(mod, "fetch_yesterday_games"):
            raw = mod.fetch_yesterday_games()
            return _process_and_ingest(raw, when=when, dry_run=dry_run)
    except Exception:
        # ignore and try the async fetch
        pass

    try:
        raw = await fetch_yesterday_game_results()
    except Exception:
        logger.debug(
            "run_daily_sync_async: async fetch failed, falling back to empty list",
            exc_info=True,
        )
        raw = []
    return _process_and_ingest(raw, when=when, dry_run=dry_run)


def run_daily_sync(when: date | None = None, dry_run: bool = False) -> Dict:
    """Run a single daily sync from sync-friendly callers.

    This wrapper will invoke the async variant using `asyncio.run()` and
    falls back to a sync provider helper when already inside an event loop.
    """
    try:
        import asyncio

        return asyncio.run(run_daily_sync_async(when=when, dry_run=dry_run))
    except RuntimeError:
        # We're likely inside an existing event loop (e.g., tests). Fall back
        # to a synchronous provider if available and then process normally.
        raw = []
        try:
            import sys

            mod = sys.modules.get("backend.services.nba_stats_client")
            if mod and hasattr(mod, "fetch_yesterday_games"):
                raw = mod.fetch_yesterday_games()
        except Exception:
            logger.debug(
                "run_daily_sync: sync provider fetch failed in running-loop fallback",
                exc_info=True,
            )
            raw = []
        return _process_and_ingest(raw, when=when, dry_run=dry_run)


def send_alert(payload: str) -> None:
    """Best-effort alert sender. If `INGEST_ALERT_WEBHOOK` is set, POST JSON payload to it.

    Uses `requests` with urllib3 Retry-backed adapter for robust retries/backoff.
    Falls back to logging when network fails or webhook not configured.
    """
    webhook = os.environ.get("INGEST_ALERT_WEBHOOK")
    if not webhook:
        # Use root-level logging here so test harnesses (caplog) reliably
        # capture this warning even if module logger configuration varies.
        logging.warning("Alert (no webhook configured): %s", payload)
        return

    secret = os.environ.get("INGEST_ALERT_SECRET")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Ingest-Secret"] = secret

    max_retries = int(os.environ.get("INGEST_ALERT_RETRIES", "3"))
    backoff = float(os.environ.get("INGEST_ALERT_BACKOFF", "0.5"))

    # Configure urllib3 Retry on requests adapter
    retry = Retry(
        total=max_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("POST",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Try to send JSON if payload is JSON, otherwise send raw body
    try:
        body_bytes = None
        try:
            payload_json = json.loads(payload)
            # body_bytes used for signature below
            body_bytes = json.dumps(payload_json, separators=(",", ":")).encode("utf-8")
            resp = session.post(webhook, json=payload_json, headers=headers, timeout=5)
        except Exception:
            body_bytes = payload.encode("utf-8")
            resp = session.post(webhook, data=body_bytes, headers=headers, timeout=5)

        # If HMAC secret configured, compute and attach signature header (sha256)
        hmac_secret = os.environ.get("INGEST_ALERT_HMAC_SECRET")
        if hmac_secret and body_bytes is not None:
            try:
                sig = hmac.new(
                    hmac_secret.encode("utf-8"), body_bytes, hashlib.sha256
                ).hexdigest()
                # Add signature header for receiver verification
                # Note: some servers do require signature present on the wire; add header and resend if necessary.
                headers_sig = dict(headers)
                headers_sig["X-Ingest-Signature"] = f"sha256={sig}"
                # send a final POST with signature header (most endpoints accept same body twice; adapter/retry will be used)
                resp = session.post(
                    webhook, data=body_bytes, headers=headers_sig, timeout=5
                )
            except Exception:
                logger.exception(
                    "Failed to compute/send HMAC signature for ingest alert"
                )

        # Raise for non-2xx/3xx responses
        resp.raise_for_status()
        logger.info("Sent ingest alert, response=%s", resp.status_code)
    except Exception:
        logger.exception("Failed to post ingest alert to %s", webhook)
