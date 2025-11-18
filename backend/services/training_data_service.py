import datetime
from typing import List, Optional, Tuple
import os
import logging
import json
import uuid
from pathlib import Path
import tempfile

import pandas as pd

from . import nba_stats_client

logger = logging.getLogger(__name__)

STAT_MAP = {
    'points': ['PTS', 'points', 'statValue'],
    'assists': ['AST', 'ast', 'statValue'],
    'rebounds': ['REB', 'reb', 'statValue'],
}


def _extract_stat_from_game(g: dict, stat_field: str):
    for key in (stat_field, stat_field.upper()):
        if key in g and g.get(key) is not None:
            return g.get(key)
    # common aliases
    for alt in ('PTS', 'AST', 'REB', 'points', 'statValue'):
        if alt in g and g.get(alt) is not None:
            return g.get(alt)
    return None


def _parse_date(dstr: str) -> Optional[datetime.date]:
    if not dstr:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.datetime.strptime(dstr, fmt).date()
        except Exception:
            continue
    try:
        return datetime.date.fromisoformat(dstr.split('T')[0])
    except Exception:
        return None


def generate_training_data(player_name: str, stat: str = 'points', min_games: int = 20, fetch_limit: int = 500, season: Optional[str] = None, seasons: Optional[List[str]] = None) -> pd.DataFrame:
    """Generate a simple sliding-window training DataFrame for a player.

    The function fetches up to `fetch_limit` historical games for the player,
    computes rolling features (last 3/5/10 game averages, std, days_rest,
    is_home, opponent defensive rating) and returns a DataFrame where each
    row corresponds to a future game and the target is the stat value for
    that game.
    """
    pid = nba_stats_client.find_player_id_by_name(player_name)
    if not pid:
        raise ValueError(f'could not resolve player id for {player_name}')

    # Support multi-season fetch when `seasons` is provided. Otherwise fall
    # back to the single-season `season` parameter used previously.
    if seasons:
        games = nba_stats_client.fetch_recent_games_multi(pid, seasons=seasons, limit_per_season=fetch_limit)
    else:
        games = nba_stats_client.fetch_recent_games(pid, limit=fetch_limit, season=season)

    # Retrieve aggregated advanced metrics and per-season stats when multi-season
    adv_multi = {}
    season_stats_multi = {}
    if seasons:
        try:
            adv_multi = nba_stats_client.get_advanced_player_stats_multi(pid, seasons) or {}
        except Exception:
            adv_multi = {}
        try:
            season_stats_multi = nba_stats_client.get_player_season_stats_multi(pid, seasons) or {}
        except Exception:
            season_stats_multi = {}

    if not games or len(games) < min_games:
        raise ValueError(f'not enough games for player {player_name} (found {len(games) if games else 0})')

    # Normalize and sort oldest -> newest
    norm = []
    for g in games:
        # support keys used by different clients
        date = g.get('GAME_DATE') or g.get('gameDate') or g.get('date') or g.get('GAME_DATE_EST')
        stat_val = _extract_stat_from_game(g, STAT_MAP.get(stat, ['PTS'])[0])
        matchup = g.get('MATCHUP') or g.get('matchup') or g.get('opponent')
        opp_def = g.get('opponentDefRating') or g.get('opponentDef') or g.get('opponentDefRating')
        is_home = None
        if isinstance(matchup, str):
            # NBA matchup format like 'LAL vs BOS' (home) or 'LAL @ BOS' (away)
            is_home = int(' vs ' in matchup or ' vs. ' in matchup)

        norm.append({'date': date, 'stat': stat_val, 'is_home': is_home, 'opp_def': opp_def})

    # parse dates and filter
    for r in norm:
        r['date_parsed'] = _parse_date(r['date'])
    norm = [r for r in norm if r['date_parsed'] is not None]
    norm.sort(key=lambda x: x['date_parsed'])

    # Build sliding windows
    rows = []
    n = len(norm)
    for i in range(n):
        # need at least one prior game to compute features and a target at i
        if i < 1:
            continue
        # target is stat at i
        target = norm[i]['stat']
        if target is None:
            continue

        # build history up to i-1
        history = norm[max(0, i - 10):i]
        hist_stats = [h['stat'] for h in history if h['stat'] is not None]
        if not hist_stats:
            continue

        def avg_last(k):
            vals = hist_stats[-k:] if len(hist_stats) >= k else hist_stats
            return sum(vals) / len(vals) if vals else None

        last_3 = avg_last(3)
        last_5 = avg_last(5)
        last_10 = avg_last(10)
        import statistics
        last_3_std = None
        try:
            last_3_std = statistics.pstdev(hist_stats[-3:]) if len(hist_stats) >= 3 else None
        except Exception:
            last_3_std = None

        # days_rest between previous game and current
        days_rest = None
        try:
            days_rest = (norm[i]['date_parsed'] - history[-1]['date_parsed']).days - 1
            days_rest = max(0, days_rest)
        except Exception:
            days_rest = None

        row = {
            'player': player_name,
            'game_date': norm[i]['date_parsed'],
            'target': float(target),
            'last_3_avg': last_3,
            'last_5_avg': last_5,
            'last_10_avg': last_10,
            'last_3_std': last_3_std,
            'days_rest': days_rest,
            'is_home': norm[i].get('is_home'),
            'opp_def': norm[i].get('opp_def'),
        }
        # attach aggregated multi-season features (same for all rows)
        try:
            adv_agg = adv_multi.get('aggregated', {}) if isinstance(adv_multi, dict) else {}
            row['multi_PER'] = float(adv_agg.get('PER') or 0.0)
            row['multi_TS_PCT'] = float(adv_agg.get('TS_PCT') or 0.0)
        except Exception:
            row['multi_PER'] = 0.0
            row['multi_TS_PCT'] = 0.0

        try:
            # compute simple mean PTS across provided seasons
            ssum = 0.0
            scnt = 0
            for s, st in (season_stats_multi or {}).items():
                if isinstance(st, dict) and 'PTS' in st:
                    try:
                        ssum += float(st.get('PTS'))
                        scnt += 1
                    except Exception:
                        continue
            row['multi_season_PTS_avg'] = float(ssum / scnt) if scnt > 0 else 0.0
        except Exception:
            row['multi_season_PTS_avg'] = 0.0
        rows.append(row)

    if not rows:
        raise ValueError('no training rows generated')

    df = pd.DataFrame(rows)
    # simple imputation
    df['last_3_avg'] = df['last_3_avg'].astype(float)
    df['last_5_avg'] = df['last_5_avg'].astype(float)
    df['last_10_avg'] = df['last_10_avg'].astype(float)
    df['last_3_std'] = df['last_3_std'].fillna(0.0).astype(float)
    df['days_rest'] = df['days_rest'].fillna(2).astype(float)
    df['is_home'] = df['is_home'].fillna(0).astype(int)
    df['opp_def'] = df['opp_def'].fillna(df['opp_def'].mean() if not df['opp_def'].isnull().all() else 100.0).astype(float)

    return df


def build_training_sample(player: str, stat: str, game_date: str, season: Optional[str] = None) -> dict:
    """Build a single training sample (features + raw_context) for a player/game.

    Uses `nba_service.get_player_context_for_training` when available to obtain
    recent games and season stats. Returns a dict with keys: `player`,
    `game_date`, `features`, `raw_context`.
    """
    try:
        from . import nba_service
        ctx = nba_service.get_player_context_for_training(player=player, stat=stat, game_date=game_date, season=season)
    except Exception:
        # Best-effort: attempt to use low-level client to fetch recent games
        try:
            pid = nba_stats_client.find_player_id_by_name(player)
            recent = nba_stats_client.fetch_recent_games(pid, limit=10, season=season)
            ctx = {'playerId': pid, 'recentGamesRaw': recent, 'seasonStats': {}}
        except Exception:
            ctx = {'playerId': None, 'recentGamesRaw': [], 'seasonStats': {}}

    # Derive simple features: recent mean and std of statValue/PTS
    recent = ctx.get('recentGamesRaw', []) or []
    vals = []
    for g in recent:
        v = None
        for k in ('statValue', 'PTS', 'points'):
            if k in g and g.get(k) is not None:
                try:
                    v = float(g.get(k))
                    break
                except Exception:
                    continue
        if v is not None:
            vals.append(v)

    import statistics
    features = {}
    if vals:
        try:
            features['recent_mean'] = float(statistics.mean(vals))
        except Exception:
            features['recent_mean'] = float(sum(vals) / len(vals))
        try:
            features['recent_std'] = float(statistics.pstdev(vals))
        except Exception:
            features['recent_std'] = 0.0
    else:
        features['recent_mean'] = None
        features['recent_std'] = None

    # Integrate advanced aggregated metrics when available from nba_service context
    try:
        adv = ctx.get('advancedStats') or {}
        adv_multi = ctx.get('advancedStatsMulti', {}) or {}
        adv_multi_agg = adv_multi.get('aggregated', {}) if isinstance(adv_multi, dict) else {}
        season_multi = ctx.get('seasonStatsMulti', {}) or {}
        # single-season advanced
        features['adv_PER'] = float(adv.get('PER') or 0.0)
        features['adv_TS_PCT'] = float(adv.get('TS_PCT') or 0.0)
        # multi-season aggregated
        features['multi_PER'] = float(adv_multi_agg.get('PER') or 0.0)
        features['multi_TS_PCT'] = float(adv_multi_agg.get('TS_PCT') or 0.0)
        # aggregated season-level stat (e.g., PTS)
        try:
            sums = 0.0
            cnt = 0
            for s, st in (season_multi or {}).items():
                if isinstance(st, dict) and 'PTS' in st:
                    try:
                        sums += float(st.get('PTS'))
                        cnt += 1
                    except Exception:
                        continue
            features['multi_season_PTS_avg'] = float(sums / cnt) if cnt > 0 else 0.0
        except Exception:
            features['multi_season_PTS_avg'] = 0.0
    except Exception:
        features['adv_PER'] = 0.0
        features['adv_TS_PCT'] = 0.0
        features['multi_PER'] = 0.0
        features['multi_TS_PCT'] = 0.0
        features['multi_season_PTS_avg'] = 0.0

    return {'player': player, 'game_date': game_date, 'features': features, 'raw_context': ctx}


def build_dataset_from_specs(specs: List[dict]):
    """Given a list of spec dicts build feature DataFrame X and label Series y.

    Each spec may include `player`, `stat`, `game_date`, `season` and an
    optional `label` value. When `label` is present it will be used as the
    target; otherwise NaN will be used.
    """
    rows = []
    labels = []
    for s in specs:
        player = s.get('player')
        stat = s.get('stat', 'points')
        game_date = s.get('game_date')
        season = s.get('season')

        sample = build_training_sample(player, stat, game_date, season)
        feat = sample.get('features', {}) or {}
        rows.append(feat)
        lbl = s.get('label')
        labels.append(float(lbl) if lbl is not None else float('nan'))

    df = pd.DataFrame(rows)
    y = pd.Series(labels)
    return df, y


def chronological_split_by_ratio(df: pd.DataFrame, date_col: str = 'game_date', train_frac: float = 0.7, val_frac: float = 0.15, test_frac: float = 0.15) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into train/val/test chronologically by the `date_col`.

    Rows are sorted by `date_col` ascending (oldest -> newest) and then
    split according to the provided fractions. Fractions need not sum to 1.0;
    remaining mass is assigned to test.
    """
    if date_col not in df.columns:
        raise ValueError(f'date_col {date_col} not in DataFrame')

    if not (0.0 <= train_frac <= 1.0 and 0.0 <= val_frac <= 1.0 and 0.0 <= test_frac <= 1.0):
        raise ValueError('fractions must be between 0 and 1')

    total = train_frac + val_frac + test_frac
    if total == 0:
        raise ValueError('at least one fraction must be positive')

    # Normalize fractions if they don't sum to 1
    train_f = train_frac / total
    val_f = val_frac / total
    test_f = test_frac / total

    df_sorted = df.sort_values(by=date_col).reset_index(drop=True)
    n = len(df_sorted)
    if n == 0:
        return df_sorted, df_sorted.copy(), df_sorted.copy()

    train_end = int(round(n * train_f))
    val_end = train_end + int(round(n * val_f))

    train_df = df_sorted.iloc[:train_end].reset_index(drop=True)
    val_df = df_sorted.iloc[train_end:val_end].reset_index(drop=True)
    test_df = df_sorted.iloc[val_end:].reset_index(drop=True)
    return train_df, val_df, test_df


def export_dataset_with_version(df: pd.DataFrame, y: Optional[pd.Series] = None, output_dir: str = 'datasets', name: Optional[str] = None, version: Optional[str] = None, fmt_prefer: str = 'parquet') -> dict:
    """Export DataFrame (and optional labels) to disk with simple versioning.

    The function will create `output_dir/{name}_v{version_timestamp}/` and
    write the features and labels along with a `manifest.json` containing
    metadata (row counts, columns, version, created_at).

    `fmt_prefer` may be `'parquet'` or `'csv'`. Parquet will be used only if
    `pyarrow` or `fastparquet` is available; otherwise falls back to gzipped CSV.
    Returns the manifest dict written.
    """
    outp = Path(output_dir)
    outp.mkdir(parents=True, exist_ok=True)

    name = name or 'dataset'
    version = version or datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    uid = uuid.uuid4().hex[:8]
    dir_name = f"{name}_v{version}_{uid}"
    target = outp / dir_name
    target.mkdir(parents=True, exist_ok=False)

    manifest = {
        'name': name,
        'version': version,
        'uid': uid,
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'rows': int(len(df)),
        'columns': list(df.columns),
    }

    # attempt parquet
    wrote = {}
    try:
        if fmt_prefer == 'parquet':
            try:
                import pyarrow  # type: ignore
                use_parquet = True
            except Exception:
                try:
                    import fastparquet  # type: ignore
                    use_parquet = True
                except Exception:
                    use_parquet = False
            if use_parquet:
                feat_path = target / 'features.parquet'
                df.to_parquet(feat_path)
                wrote['features'] = str(feat_path)
                if y is not None:
                    labels_path = target / 'labels.parquet'
                    y.to_frame(name='label').to_parquet(labels_path)
                    wrote['labels'] = str(labels_path)
            else:
                raise ImportError('no parquet engine available')
        else:
            raise ImportError('parquet not requested')
    except Exception:
        # fallback to gz csv
        feat_path = target / 'features.csv.gz'
        df.to_csv(feat_path, index=False, compression='gzip')
        wrote['features'] = str(feat_path)
        if y is not None:
            labels_path = target / 'labels.csv.gz'
            y.to_frame(name='label').to_csv(labels_path, index=False, compression='gzip')
            wrote['labels'] = str(labels_path)

    manifest.update({'files': wrote})
    manifest_path = target / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, default=str)

    return manifest
