"""Player tracking data helper (clean single implementation).

Provides a minimal, file-backed loader that looks for JSON tracking
files named after the sanitized player name (spaces -> underscores).
The function `features_for_player` returns per-game aggregates or None
when tracking data is not available. This is lightweight and safe for
dev/test environments.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import json
import os
import csv
from statistics import mean


def _sanitize_name(name: str) -> str:
    # replace spaces with underscore first, then keep alnum/_/- characters
    base = (name or "").strip().lower().replace(' ', '_')
    return "".join(c for c in base if c.isalnum() or c in ('_', '-'))


def _default_data_dir() -> str:
    base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "data", "tracking")


def _load_tracking_file(player_name: str, data_dir: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    data_dir = data_dir or _default_data_dir()
    name = _sanitize_name(player_name)
    candidates = [f"{name}.json", f"{name}.csv", f"{name}.parquet"]
    for c in candidates:
        path = os.path.join(data_dir, c)
        if os.path.exists(path):
            try:
                if path.endswith('.json'):
                    with open(path, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                        if isinstance(data, list):
                            return data
                        if isinstance(data, dict):
                            # find first list value in wrapper
                            for v in data.values():
                                if isinstance(v, list):
                                    return v
                # CSV reading: prefer pandas if available, else fall back to csv.DictReader
                if path.endswith('.csv'):
                    try:
                        import pandas as _pd

                        df = _pd.read_csv(path)
                        # convert NaNs to None and return list of dicts
                        df = df.where(_pd.notnull(df), None) if hasattr(df, 'where') else df
                        return df.to_dict(orient='records')
                    except Exception:
                        # pandas not available or read failed; fallback
                        try:
                            rows = []
                            with open(path, 'r', encoding='utf-8') as fh:
                                reader = csv.DictReader(fh)
                                for r in reader:
                                    # convert empty strings to None
                                    row = {k: (v if v != '' else None) for k, v in r.items()}
                                    rows.append(row)
                            return rows
                        except Exception:
                            return None

                # Parquet reading: use pandas if available
                if path.endswith('.parquet'):
                    try:
                        import pandas as _pd

                        df = _pd.read_parquet(path)
                        df = df.where(_pd.notnull(df), None) if hasattr(df, 'where') else df
                        return df.to_dict(orient='records')
                    except Exception:
                        return None
            except Exception:
                return None
    return None


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    try:
        return float(mean(values))
    except Exception:
        return None


def _parse_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "":
            return None
        # handle percentage like '52%'
        if s.endswith('%'):
            s = s[:-1]
        fv = float(s)
        return fv
    except Exception:
        return None


def _normalize_pct(value: Optional[float]) -> Optional[float]:
    """Normalize a percentage value to 0-1 range if needed."""
    if value is None:
        return None
    try:
        v = float(value)
        if v > 1.0:
            # assume percent like 52 -> 0.52
            return v / 100.0
        return v
    except Exception:
        return None


def features_for_player(player_name: str, seasons: Optional[List[str]] = None, data_dir: Optional[str] = None) -> Dict[str, Optional[float]]:
    """Compute tracking-derived features for a player from JSON rows.

    Recognized keys per-row (best-effort):
      - avg_speed_mph, avg_speed_mps, avg_speed
      - distance_m (meters), distance_miles
      - touches
      - time_of_possession_sec
      - exp_fg_pct, expected_fg_pct, xg

    Returns None for each field if tracking data is not available.
    """
    games = _load_tracking_file(player_name, data_dir=data_dir)
    if not games:
        # include legacy keys for compatibility
        return {
            "avg_speed": None,
            "distance_per_game": None,
            "touches_per_game": None,
            "time_of_possession": None,
            "shot_quality": None,
            "avg_speed_mph": None,
            "distance_miles_per_game": None,
            "time_possession_sec_per_game": None,
            "exp_fg_pct": None,
        }

    speeds: List[float] = []
    distances: List[float] = []
    touches: List[float] = []
    time_poss: List[float] = []
    exp_fg: List[float] = []

    for g in games:
        # speed conversions - accept multiple common column names
        s = None
        speed_keys_mph = ('avg_speed_mph', 'speed_mph', 'spd_mph')
        speed_keys_mps = ('avg_speed_mps', 'speed_mps', 'spd_mps')
        speed_keys_raw = ('avg_speed', 'speed')
        for k in speed_keys_mph:
            val = _parse_float(g.get(k))
            if val is not None:
                s = val
                break
        if s is None:
            for k in speed_keys_mps:
                val = _parse_float(g.get(k))
                if val is not None:
                    s = val * 2.2369362920544
                    break
        if s is None:
            for k in speed_keys_raw:
                val = _parse_float(g.get(k))
                if val is not None:
                    s = val
                    break
        if s is not None:
            speeds.append(s)

        # distance - accept meters or miles
        d = None
        dist_keys_m = ('distance_m', 'distance_meters', 'distanceMeters', 'dist_m')
        dist_keys_miles = ('distance_miles', 'distance_mile', 'distance_mi', 'dist_miles')
        for k in dist_keys_m:
            val = _parse_float(g.get(k))
            if val is not None:
                d = val / 1609.344
                break
        if d is None:
            for k in dist_keys_miles:
                val = _parse_float(g.get(k))
                if val is not None:
                    d = val
                    break
        if d is not None:
            distances.append(d)

        # touches per game - accept several column names
        touch_keys = ('touches', 'touch_count', 'touches_count', 'touches_per_game', 'touches_pg')
        for k in touch_keys:
            val = _parse_float(g.get(k))
            if val is not None:
                touches.append(val)
                break

        # time of possession (seconds)
        time_keys = ('time_of_possession_sec', 'possession_sec', 'time_poss_sec', 'time_poss', 'possession_time_sec')
        for k in time_keys:
            val = _parse_float(g.get(k))
            if val is not None:
                time_poss.append(val)
                break

        # expected FG% / shot quality — accept many keys and normalize to 0-1
        exp_keys = (
            'exp_fg_pct', 'expected_fg_pct', 'expected_fg', 'exp_fg', 'xg', 'exp_fg_percent', 'expected_fg_percent', 'exp_fg_perc'
        )
        for k in exp_keys:
            val = _parse_float(g.get(k))
            if val is not None:
                norm = _normalize_pct(val)
                if norm is not None:
                    exp_fg.append(norm)
                break

    return {
        "avg_speed_mph": _safe_mean(speeds),
        "distance_miles_per_game": _safe_mean(distances),
        "touches_per_game": _safe_mean(touches),
        "time_possession_sec_per_game": _safe_mean(time_poss),
        "exp_fg_pct": _safe_mean(exp_fg),
    }
    # Provide legacy keys for compatibility with older callers/tests
    result = {
        "avg_speed": _safe_mean(speeds),
        "distance_per_game": _safe_mean(distances),
        "touches_per_game": _safe_mean(touches),
        "time_of_possession": _safe_mean(time_poss),
        "shot_quality": _safe_mean(exp_fg),
    }
    # merge canonical keys as well
    result.update({
        "avg_speed_mph": _safe_mean(speeds),
        "distance_miles_per_game": _safe_mean(distances),
        "touches_per_game": _safe_mean(touches),
        "time_possession_sec_per_game": _safe_mean(time_poss),
        "exp_fg_pct": _safe_mean(exp_fg),
    })
    return result


def create_default_service():
    class S:
        @staticmethod
        def features_for_player(name: str, seasons=None, data_dir: Optional[str] = None):
            return features_for_player(name, seasons=seasons, data_dir=data_dir)

    return S()
