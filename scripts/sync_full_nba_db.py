"""CLI to sync full NBA players/teams history into local DB.

Usage:
  Set `SEASONS` env var as comma-separated list (e.g. '2024-25,2023-24,2022-23')
  Then run: `python scripts/sync_full_nba_db.py`

This script will iterate all players/teams via `nba_stats_client`, fetch
their game logs for the requested seasons, and call the ingestion pipeline
to normalize and persist rows. Use `DRY_RUN=1` to perform validation only.
"""
from __future__ import annotations

import os
import sys
import time
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_seasons(env_val: str) -> List[str]:
    parts = [p.strip() for p in (env_val or '').split(',') if p.strip()]
    return parts


def main():
    repo_root = os.path.dirname(os.path.dirname(__file__))
    # Ensure repo root is on PYTHONPATH
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from backend.services import nba_stats_client, data_ingestion_service
    # bring in team-normalization helper to canonicalize team names/abbrevs
    try:
        from backend.services.data_ingestion_service import _normalize_team_name
    except Exception:
        # fallback: identity
        def _normalize_team_name(x):
            return x

    seasons_env = os.environ.get('SEASONS')
    if not seasons_env:
        # default to last 3 seasons (approx)
        seasons = [
            os.environ.get('DEFAULT_SEASON', '2024-25'),
            os.environ.get('PREV_SEASON', '2023-24'),
            os.environ.get('PREV2_SEASON', '2022-23'),
        ]
    else:
        seasons = _parse_seasons(seasons_env)

    def _parse_bool_env(name: str, default: bool = False) -> bool:
        v = os.environ.get(name)
        if v is None:
            return default
        try:
            s = str(v).strip().lower()
            return s in ("1", "true", "t", "yes", "y")
        except Exception:
            return default

    dry_run = _parse_bool_env('DRY_RUN', False)
    logger.info('Starting full NBA DB sync; seasons=%s dry_run=%s', seasons, dry_run)

    # Bulk-fetch per-season league player game logs to reduce per-player HTTP calls
    total_player_rows = 0
    batch = []
    for season in seasons:
        logger.info('Fetching league player game logs for season=%s', season)
        try:
            season_map = nba_stats_client.fetch_season_league_player_game_logs(season)
        except Exception:
            logger.exception('Failed to fetch league player game logs for %s', season)
            season_map = {}

        # season_map: PLAYER_ID -> [games]
        if not season_map:
            logger.warning('League-level season map empty for %s, falling back to per-player fetch (throttled)', season)
            # Controlled fallback: fetch list of players and retrieve their game logs in bulk
            # Use season-level league player advanced listing as a targeted fallback
            # (fewer irrelevant/retired players than fetch_all_players). Fetch
            # histories concurrently with a small thread pool to reduce elapsed
            # runtime while relying on the client's internal token bucket for
            # global rate-limiting.
            try:
                league_players = nba_stats_client.fetch_league_player_advanced(season) or {}
            except Exception:
                logger.exception('Failed to fetch league player list for fallback')
                league_players = {}

            try:
                fallback_limit = int(os.environ.get('NBA_FALLBACK_LIMIT', '200'))
            except Exception:
                fallback_limit = 200

            pids = list(league_players.keys())[:fallback_limit]
            # If league_players mapping is empty (client/version mismatch),
            # fall back to fetching the players directory and filter for
            # likely-active players to avoid fetching many retired players.
            if not pids:
                try:
                    players_list = nba_stats_client.fetch_all_players() or []
                except Exception:
                    logger.exception('Failed to fetch players list for fallback')
                    players_list = []

                # prefer players with teamId or isActive flag; fall back to first N
                candidates = []
                for p in players_list:
                    try:
                        pid = p.get('id') or p.get('playerId') or p.get('PERSON_ID') or p.get('Player_ID')
                        if not pid:
                            continue
                        is_active = False
                        if isinstance(p.get('isActive'), bool):
                            is_active = p.get('isActive')
                        if p.get('teamId') or p.get('team_id') or p.get('team'):
                            is_active = True
                        candidates.append((int(pid), bool(is_active), p))
                    except Exception:
                        continue

                # sort active players first
                candidates.sort(key=lambda t: (0 if t[1] else 1))
                pids = [c[0] for c in candidates[:fallback_limit]]

            logger.info('Fallback will attempt up to %d league players (concurrent)', len(pids))

            # Use a small thread pool to fetch per-player multi-season logs in parallel
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # Use a conservative worker pool to avoid overwhelming upstream
            # and to reduce token-bucket contention in the client.
            max_workers = min(4, max(1, len(pids)))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = {}
                for pid in pids:
                    try:
                        futures[ex.submit(nba_stats_client.fetch_full_player_history, int(pid), seasons=[season])] = pid
                    except Exception:
                        logger.debug('Failed to submit fetch for pid=%s', pid, exc_info=True)
                for fut in as_completed(futures):
                    pid = futures.get(fut)
                    try:
                        games = fut.result()
                    except Exception:
                        logger.exception('Failed to fetch games for player %s during fallback', pid)
                        try:
                            # record failed fetch for later retry analysis
                            if hasattr(nba_stats_client, '_record_failed_fetch'):
                                nba_stats_client._record_failed_fetch('player', pid, 'fetch_full_player_history_fallback')
                        except Exception:
                            logger.debug('Failed to record failed fetch for %s', pid, exc_info=True)
                        continue
                    if not games:
                        continue
                    # Attempt to derive the display name from league_players mapping
                    name = None
                    try:
                        meta = league_players.get(pid) or {}
                        name = meta.get('PLAYER_NAME') or meta.get('player_name') or meta.get('player')
                    except Exception:
                        name = None

                    for g in games:
                        rec = {}
                        rec['game_date'] = g.get('GAME_DATE') or g.get('gameDate') or g.get('GAME_DATE_RAW') or g.get('DATE')
                        matchup = g.get('MATCHUP') or g.get('matchup')
                        home = None
                        away = None
                        if matchup and isinstance(matchup, str):
                            if ' @ ' in matchup:
                                left, right = [t.strip() for t in matchup.split(' @ ', 1)]
                                home = _normalize_team_name(right)
                                away = _normalize_team_name(left)
                            elif ' vs ' in matchup or ' vs. ' in matchup:
                                parts = matchup.replace('.', '').split(' vs ')
                                if len(parts) == 2:
                                    home = _normalize_team_name(parts[0].strip())
                                    away = _normalize_team_name(parts[1].strip())

                        rec['home_team'] = home or _normalize_team_name(g.get('HOME_TEAM_ABBREVIATION') or g.get('HOME_TEAM') or g.get('home')) or 'UNKNOWN'
                        rec['away_team'] = away or _normalize_team_name(g.get('VISITOR_TEAM_ABBREVIATION') or g.get('VISITOR_TEAM') or g.get('away')) or 'UNKNOWN'
                        rec['player_name'] = name or g.get('PLAYER_NAME') or g.get('PLAYER') or g.get('player')
                        try:
                            rec['player_nba_id'] = int(pid)
                        except Exception:
                            rec['player_nba_id'] = pid
                        val = None
                        for k in ('PTS', 'PTS_PLAYER', 'PLAYER_PTS'):
                            if k in g:
                                val = g.get(k)
                                break
                        if val is None:
                            for kk, vv in g.items():
                                if kk and kk.upper() == 'PTS':
                                    val = vv
                                    break
                        if val is None:
                            continue
                        rec['stat_type'] = 'points'
                        rec['value'] = val
                        batch.append(rec)
            # end concurrent fallback
            # finished fallback for this season
            # proceed to next season
            continue

        for pid, games in season_map.items():
            if not games:
                continue
            # try to get player name from first row
            first = games[0]
            name = first.get('PLAYER_NAME') or first.get('PLAYER') or first.get('player') or None
            for g in games:
                # Normalize into ingestion-friendly per-player record (points stat by default)
                rec = {}
                # game date heuristics
                rec['game_date'] = g.get('GAME_DATE') or g.get('GAME_DATE_EST') or g.get('gameDate') or g.get('DATE') or g.get('date')

                # home/away heuristics
                home = g.get('HOME_TEAM_ABBREVIATION') or g.get('HOME_TEAM') or g.get('home_team')
                away = g.get('VISITOR_TEAM_ABBREVIATION') or g.get('VISITOR_TEAM') or g.get('away_team')
                if not home or not away:
                    # try matchup string like 'LAL @ BOS' or 'LAL vs BOS'
                    matchup = g.get('MATCHUP') or g.get('matchup') or g.get('MATCH')
                    if matchup and isinstance(matchup, str):
                        if ' @ ' in matchup:
                            left, right = [p.strip() for p in matchup.split(' @ ', 1)]
                            home = right
                            away = left
                        elif ' vs ' in matchup:
                            left, right = [p.strip() for p in matchup.split(' vs ', 1)]
                            home = left
                            away = right

                # fallback to TEAM_ABBREVIATION + OPPONENT
                if (not home or not away) and ('TEAM_ABBREVIATION' in g or 'TEAM' in g):
                    team = g.get('TEAM_ABBREVIATION') or g.get('TEAM') or g.get('team')
                    opp = g.get('OPPONENT') or g.get('OPP_TEAM_ABBREVIATION') or g.get('OPP_TEAM') or g.get('OPPONENT_TEAM')
                    if team and opp:
                        # unable to determine home/away reliably; set one side and mark other
                        home = home or team
                        away = away or opp

                rec['home_team'] = home or g.get('HOME_TEAM_ABBREVIATION') or g.get('home') or 'UNKNOWN'
                rec['away_team'] = away or g.get('VISITOR_TEAM_ABBREVIATION') or g.get('away') or 'UNKNOWN'

                # player identity
                rec['player_name'] = name
                try:
                    rec['player_nba_id'] = int(pid)
                except Exception:
                    rec['player_nba_id'] = g.get('PLAYER_ID') or g.get('player_id')

                # extract points value (common key variants)
                val = None
                for k in ('PTS', 'PTS_PLAYER', 'PLAYER_PTS', 'PTS_HOME', 'PTS_AWAY'):
                    if k in g:
                        val = g.get(k)
                        break
                if val is None:
                    for kk, vv in g.items():
                        if kk and kk.upper() == 'PTS':
                            val = vv
                            break

                if val is None:
                    # no points field found; skip this record
                    continue

                rec['stat_type'] = 'points'
                rec['value'] = val
                batch.append(rec)

            # flush in batches
                if len(batch) >= 1000:
                    logger.info('Flushing batch of %d rows to ingestion', len(batch))
                    res = data_ingestion_service._process_and_ingest(batch, when=None, dry_run=dry_run)
                    if isinstance(res, dict):
                        total_player_rows += res.get('player_rows', 0)
                        missing_ct = len(res.get('validation', {}).get('missing', []))
                        type_err_ct = len(res.get('validation', {}).get('type_errors', []))
                        outliers_ct = len(res.get('validation', {}).get('outliers', []))
                        filtered_out = res.get('filtered_out_count', 0)
                        would_insert = max(0, len(batch) - filtered_out)
                        logger.info('Ingest validation: missing=%d type_errors=%d outliers=%d filtered_out=%d would_insert=%d',
                                    missing_ct, type_err_ct, outliers_ct, filtered_out, would_insert)
                    batch = []
        # small throttle between seasons
        time.sleep(0.5)

    if batch:
        logger.info('Flushing final batch of %d rows', len(batch))
        res = data_ingestion_service._process_and_ingest(batch, when=None, dry_run=dry_run)
        if isinstance(res, dict):
            total_player_rows += res.get('player_rows', 0)
            missing_ct = len(res.get('validation', {}).get('missing', []))
            type_err_ct = len(res.get('validation', {}).get('type_errors', []))
            outliers_ct = len(res.get('validation', {}).get('outliers', []))
            filtered_out = res.get('filtered_out_count', 0)
            would_insert = max(0, len(batch) - filtered_out)
            logger.info('Ingest validation: missing=%d type_errors=%d outliers=%d filtered_out=%d would_insert=%d',
                        missing_ct, type_err_ct, outliers_ct, filtered_out, would_insert)

    # Teams
    teams = nba_stats_client.fetch_all_teams()
    logger.info('Discovered %d teams', len(teams))
    team_batch = []
    for t in teams:
        tid = t.get('id') or t.get('teamId') or t.get('TEAM_ID')
        name = t.get('full_name') or t.get('nickname') or t.get('fullName') or t.get('teamName')
        if not tid:
            continue
        try:
            games = nba_stats_client.fetch_full_team_history(int(tid), seasons)
        except Exception:
            logger.exception('Failed to fetch history for team %s (%s)', name, tid)
            continue
        if not games:
            continue
        for g in games:
            # ensure team fields present for normalization
            if 'home_team' not in g and 'HOME_TEAM_ABBREVIATION' in g:
                try:
                    g['home_team'] = g.get('HOME_TEAM_ABBREVIATION')
                except Exception:
                    pass
            if 'away_team' not in g and 'VISITOR_TEAM_ABBREVIATION' in g:
                try:
                    g['away_team'] = g.get('VISITOR_TEAM_ABBREVIATION')
                except Exception:
                    pass
            team_batch.append(g)

            if len(team_batch) >= 1000:
                logger.info('Flushing team batch of %d rows to ingestion', len(team_batch))
                res = data_ingestion_service._process_and_ingest(team_batch, when=None, dry_run=dry_run)
                if isinstance(res, dict):
                    missing_ct = len(res.get('validation', {}).get('missing', []))
                    type_err_ct = len(res.get('validation', {}).get('type_errors', []))
                    outliers_ct = len(res.get('validation', {}).get('outliers', []))
                    filtered_out = res.get('filtered_out_count', 0)
                    would_insert = max(0, len(team_batch) - filtered_out)
                    logger.info('Team ingest validation: missing=%d type_errors=%d outliers=%d filtered_out=%d would_insert=%d',
                                missing_ct, type_err_ct, outliers_ct, filtered_out, would_insert)
                team_batch = []
            time.sleep(0.5)

    if team_batch:
        logger.info('Flushing final team batch of %d rows', len(team_batch))
        res = data_ingestion_service._process_and_ingest(team_batch, when=None, dry_run=dry_run)
        if isinstance(res, dict):
            missing_ct = len(res.get('validation', {}).get('missing', []))
            type_err_ct = len(res.get('validation', {}).get('type_errors', []))
            outliers_ct = len(res.get('validation', {}).get('outliers', []))
            filtered_out = res.get('filtered_out_count', 0)
            would_insert = max(0, len(team_batch) - filtered_out)
            logger.info('Team ingest validation: missing=%d type_errors=%d outliers=%d filtered_out=%d would_insert=%d',
                        missing_ct, type_err_ct, outliers_ct, filtered_out, would_insert)

    logger.info('Sync complete. player_rows=%d', total_player_rows)


if __name__ == '__main__':
    main()
