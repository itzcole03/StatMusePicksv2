"""Normalize/canonicalize NBA fetch rows from different clients/sources.

Provide a small, dependency-free helper to map variant key names and types
returned by `nba_api`, internal clients, or other upstreams into a stable
canonical dict used by ingestion and training-data steps.

Functions:
- `canonicalize_row(raw)` -> dict: returns a canonical mapping with keys like
  `game_id`, `game_date` (ISO YYYY-MM-DD), `player_id`, `season_id`, `pts`,
  etc. Original raw row is included under `raw`.
- `canonicalize_rows(rows)` -> list[dict]: canonicalizes and deduplicates a
  sequence of rows (dedupe by `game_id`+`player_id` when available).

This file is intentionally small and avoids external deps so it can be used
in tests and scripts without installing extras.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def _get_any(d: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _parse_date(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    if not s:
        return None
    # Try ISO first
    try:
        return datetime.fromisoformat(s).date().isoformat()
    except Exception:
        pass
    # Common formats
    fmts = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y%m%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except Exception:
            continue
    # If it's numeric epoch seconds/milliseconds
    if s.isdigit():
        try:
            ival = int(s)
            # Heuristic: if value is > 1e10 treat as milliseconds
            if ival > 10_000_000_000:
                ival = ival / 1000
            return datetime.utcfromtimestamp(ival).date().isoformat()
        except Exception:
            pass
    return None


def canonicalize_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical dict for a single raw row.

    The returned dict will always include a `raw` key containing the original
    input. Canonical keys that may appear:
    - `game_id` (str)
    - `game_date` (ISO YYYY-MM-DD string)
    - `player_id` (str or int)
    - `season_id` (str)
    - `team_id` / `opponent_team_id`
    - common stat fields like `pts`, `reb`, `ast` when present
    - `stat_type` / `stat_value` (optional helpers for pipelines that expect
      a single stat/value pair)
    """
    # Key candidate lists for common fields returned by various fetchers
    candidates = {
        "game_id": ["GAME_ID", "game_id", "gameId", "g", "id", "GAMEID"],
        "game_date": ["GAME_DATE", "GAME_DATE_EST", "game_date", "gameDate", "date"],
        "player_id": ["PLAYER_ID", "player_id", "playerId", "person_id"],
        "season_id": ["SEASON_ID", "season", "season_id", "seasonId"],
        "team_id": ["TEAM_ID", "team_id", "teamId", "team"] ,
        "opp_team_id": ["OPPONENT_TEAM_ID", "opp_team_id", "oppTeamId", "opp_team", "MATCHUP_OPP"] ,
    }

    # Preserve original keys at top-level for backward compatibility with
    # callers/tests that expect original column names (e.g., 'PTS'). Also
    # include the original raw payload under the `raw` key.
    try:
        out: Dict[str, Any] = dict(raw) if isinstance(raw, dict) else {"raw": raw}
    except Exception:
        out = {"raw": raw}
    out["raw"] = raw

    # Basic mappings
    for canon, keys in candidates.items():
        val = _get_any(raw, keys)
        if val is not None:
            if canon == "game_date":
                parsed = _parse_date(val)
                out["game_date"] = parsed
            else:
                out[canon if canon != "opp_team_id" else "opponent_team_id"] = val

    # Numeric stats common names
    out_stats: Dict[str, Any] = {}
    stat_map = {
        "pts": ["PTS", "points", "pts"],
        "reb": ["REB", "rebounds", "reb"],
        "ast": ["AST", "assists", "ast"],
        "tov": ["TOV", "turnovers", "tov"],
    }
    for canon, keys in stat_map.items():
        v = _get_any(raw, keys)
        if v is not None:
            try:
                out_stats[canon] = float(v)
            except Exception:
                out_stats[canon] = v

    out.update(out_stats)

    # If the raw row is a single-stat style record (e.g., stat_type/stat_value),
    # canonicalize that too.
    stat_type = _get_any(raw, ["stat", "statType", "STAT_TYPE", "stat_type"]) or _get_any(raw, ["stat_name"])
    stat_value = _get_any(raw, ["value", "statValue", "STAT_VALUE", "stat_value"]) or _get_any(raw, ["value"])
    if stat_type:
        out["stat_type"] = stat_type
    if stat_value is not None:
        try:
            out["stat_value"] = float(stat_value)
        except Exception:
            out["stat_value"] = stat_value

    return out


def canonicalize_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Canonicalize and deduplicate an iterable of raw rows.

    Deduping heuristic: when `game_id` and `player_id` are present use that
    pair as the dedupe key. Otherwise fall back to `(game_date, player_id)`.
    If neither is available all rows are kept but normalized.
    """
    seen: Set[Tuple[Optional[str], Optional[str]]] = set()
    out: List[Dict[str, Any]] = []

    for raw in rows:
        can = canonicalize_row(raw)
        gid = can.get("game_id")
        pid = can.get("player_id")
        date = can.get("game_date")
        key: Tuple[Optional[str], Optional[str]]
        if gid is not None and pid is not None:
            key = (str(gid), str(pid))
        elif date is not None and pid is not None:
            key = (str(date), str(pid))
        else:
            # Use a unique placeholder per-row so it won't dedupe
            key = (None, None)

        if key in seen:
            # duplicate -- skip
            continue
        seen.add(key)
        out.append(can)

    # Optional: sort by game_date when available
    try:
        out.sort(key=lambda r: (r.get("game_date") or "", r.get("game_id") or ""))
    except Exception:
        pass

    return out


__all__ = ["canonicalize_row", "canonicalize_rows"]
