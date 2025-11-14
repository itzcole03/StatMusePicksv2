#!/usr/bin/env python
"""Populate dev DB with historical player game rows via `nba_stats_client`.

This script is intentionally conservative:
- By default it writes normalized raw fetches to `backend/ingest_audit`.
- Only when run with `--commit --confirm` will it upsert rows into the database.

Usage (dry-run, write audit files only):
  python backend/scripts/populate_dev_db_from_nba.py --players "LeBron James,Stephen Curry" --max-games 200

Commit to DB (destructive guard enabled):
  python backend/scripts/populate_dev_db_from_nba.py --players "..." --max-games 200 --commit --confirm

"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any
import time

# Optional import for nba_api; guarded at runtime
try:
    from nba_api.stats.static import players as nba_players_static
    from nba_api.stats.endpoints import playergamelog
    HAS_NBA_API = True
except Exception:
    HAS_NBA_API = False

from backend.services import nba_stats_client
from backend import db
from sqlalchemy import text


def safe_name(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_")


async def fetch_player_games(player_name: str, max_games: int = 200, deep: bool = False, target_min_games: int | None = None, seasons_start: int | None = None, seasons_end: int | None = None) -> List[Dict[str, Any]]:
    """Fetch games for a player using `nba_stats_client`.

    Strategy (best-effort):
    1. Try to resolve player id via `find_player_id_by_name` or `find_player_id`.
    2. Use `fetch_recent_games_by_id` / `fetch_recent_games_by_name` to get the newest games.
    3. If `deep` and the results are short of `target_min_games`, attempt additional APIs:
       - `fetch_career_games_by_id(pid)` if available
       - `fetch_games_by_season(pid, season)` across seasons between `seasons_start` and `seasons_end` if available
    4. Deduplicate by game id and return newest-first list.

    Returns an empty list on failure.
    """
    try:
        pid = None
        try:
            pid = nba_stats_client.find_player_id_by_name(player_name)
        except Exception:
            try:
                pid = nba_stats_client.find_player_id(player_name)
            except Exception:
                pid = None
    except Exception:
        pid = None

    games: List[Dict[str, Any]] = []
    try:
        if pid:
            if hasattr(nba_stats_client, "fetch_recent_games_by_id"):
                games = (nba_stats_client.fetch_recent_games_by_id(pid, limit=max_games) or [])
        else:
            if hasattr(nba_stats_client, "fetch_recent_games_by_name"):
                games = (nba_stats_client.fetch_recent_games_by_name(player_name, limit=max_games) or [])
    except Exception:
        games = []

    # If not deep mode, return what we have (possibly empty)
    if not deep:
        return games or []

    # Deep mode: try to accumulate more historical games if below target
    seen_ids = {g.get("gameId") or g.get("id") or g.get("game_id") for g in (games or [])}
    aggregated = list(games or [])

    def add_new_rows(rows: List[Dict[str, Any]]):
        for r in rows or []:
            gid = (
                r.get("gameId")
                or r.get("GAME_ID")
                or r.get("Game_ID")
                or r.get("id")
                or r.get("game_id")
            )
            if not gid:
                continue
            if gid in seen_ids:
                continue
            seen_ids.add(gid)
            aggregated.append(r)

    # Try a career fetch
    if hasattr(nba_stats_client, "fetch_career_games_by_id") and pid:
        try:
            career = nba_stats_client.fetch_career_games_by_id(pid)
            add_new_rows(career or [])
        except Exception:
            pass

    # Try season-by-season fetch if available
    if hasattr(nba_stats_client, "fetch_games_by_season") and pid:
        start = seasons_start or 2000
        end = seasons_end or 2025
        for season in range(end, start - 1, -1):
            if target_min_games and len(aggregated) >= target_min_games:
                break
            try:
                # normalize season into the 'YYYY-YY' string expected by nba_api helpers
                season_str = f"{season-1}-{str(season)[-2:]}" if season >= 2001 else f"{season}-{str(season+1)[-2:]}"
                rows = nba_stats_client.fetch_games_by_season(pid, season_str)
                add_new_rows(rows or [])
            except Exception:
                # stop if the client doesn't support this season or errors
                continue

    # Trim to max_games if specified
    if max_games and len(aggregated) > max_games:
        aggregated = aggregated[:max_games]

    # Sort newest-first if possible by a date field
    try:
        aggregated.sort(key=lambda r: r.get("gameDate") or r.get("date") or r.get("game_date") or "", reverse=True)
    except Exception:
        pass

    return aggregated


def normalize_game_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Map a few canonical fields used in ingestion/pipeline
    return {
        "game_id": raw.get("gameId") or raw.get("GAME_ID") or raw.get("Game_ID") or raw.get("id") or raw.get("game_id"),
        "date": raw.get("gameDate") or raw.get("GAME_DATE") or raw.get("date") or raw.get("game_date"),
        "home_team": raw.get("homeTeam") or raw.get("home_team") or raw.get("home") or raw.get("HOME_TEAM") or raw.get("HomeTeam"),
        "away_team": raw.get("awayTeam") or raw.get("away_team") or raw.get("away") or raw.get("AWAY_TEAM") or raw.get("AwayTeam"),
        "statValue": raw.get("statValue") or raw.get("PTS") or raw.get("Pts") or raw.get("points") or raw.get("stat_value"),
        "opponentTeamId": raw.get("opponentTeamId") or raw.get("opponent") or raw.get("opponentAbbrev") or raw.get("OPPONENT_TEAM_ID"),
        "opponentDefRating": raw.get("opponentDefRating") or raw.get("opponentDef") or None,
    }


def fetch_via_nba_api(player_name: str, seasons_start: int | None, seasons_end: int | None, per_season_limit: int | None = None, rate_limit_s: float = 0.6) -> List[Dict[str, Any]]:
    """Fetch season-by-season game logs via `nba_api`.

    Returns rows normalized similar to other fetchers. Rate-limited to avoid hammering the API.
    """
    if not HAS_NBA_API:
        print("nba_api not available in this environment; skipping nba_api fetch")
        return []

    # robust player id resolution with retries and fuzzy matching
    pid = None
    try:
        # try direct exact full-name lookup
        try:
            matches = nba_players_static.find_players_by_full_name(player_name)
        except Exception:
            matches = []

        if matches:
            # matches are dicts with 'id' and 'full_name'
            m = matches[0]
            pid = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)

        # fallback: iterate get_players and fuzzy match
        if not pid:
            try:
                candidates = nba_players_static.get_players()
            except Exception:
                candidates = []
            lname = player_name.lower()
            for p in candidates:
                full = p.get("full_name", "").lower()
                if full == lname or lname in full or full in lname:
                    pid = p.get("id")
                    break
    except Exception:
        pid = None

    if not pid:
        print(f"nba_api: could not resolve player id for '{player_name}'")
        return []

    rows: List[Dict[str, Any]] = []
    start = seasons_start or 2000
    end = seasons_end or 2025

    # iterate seasons newest->oldest, build season code like '2024-25'
    for season in range(end, start - 1, -1):
        # season -> season string expected by nba_api e.g., '2024-25'
        season_str = f"{season-1}-{str(season)[-2:]}" if season >= 2001 else f"{season}-{str(season+1)[-2:]}"
        attempt = 0
        while attempt < 3:
            attempt += 1
            try:
                pgl = playergamelog.PlayerGameLog(player_id=pid, season=season_str)
                dfs = pgl.get_data_frames()
                if not dfs:
                    break
                df = dfs[0]
                for _, r in df.iterrows():
                    rows.append({
                        "gameId": r.get("GAME_ID") or r.get("game_id"),
                        "gameDate": r.get("GAME_DATE"),
                        "PTS": r.get("PTS"),
                        "homeTeam": r.get("MATCHUP") or r.get("MATCHUP"),
                        "statType": "points",
                    })
                break
            except Exception as e:
                # log and retry with backoff
                print(f"nba_api: PlayerGameLog failed for {player_name} season {season_str} (attempt {attempt}): {e}")
                time.sleep(rate_limit_s * attempt)
                continue

        if per_season_limit and len(rows) >= per_season_limit:
            break
        # polite rate limit between seasons
        time.sleep(rate_limit_s)

    if not rows:
        print(f"nba_api: no rows returned for {player_name}")

    # newest-first ordering
    try:
        rows.sort(key=lambda r: r.get("gameDate") or "", reverse=True)
    except Exception:
        pass
    return rows


async def write_audit_file(out_dir: Path, player: str, rows: List[Dict[str, Any]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"raw_fetch_{safe_name(player)}.json"
    with open(fname, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    return fname


async def upsert_into_db(player: str, rows: List[Dict[str, Any]]):
    """Upsert players, games, and player_stats into the DB.

    This uses simple SQL with a sqlite-friendly fallback. Designed for dev only.
    """
    db._ensure_engine_and_session()
    async with db.engine.begin() as conn:
        # insert player if not exists
        # try sqlite syntax first (INSERT OR IGNORE)
        player_team = None
        player_position = None
        name = player
        if db.DATABASE_URL.startswith("sqlite"):
            await conn.execute(text("INSERT OR IGNORE INTO players (name, team, position) VALUES (:name, :team, :pos)"), {"name": name, "team": player_team, "pos": player_position})
            res = await conn.execute(text("SELECT id FROM players WHERE name = :name"), {"name": name})
            row = res.first()
            player_id = row[0] if row else None
        else:
            # Postgres: use ON CONFLICT DO NOTHING
            try:
                await conn.execute(text("INSERT INTO players (name, team, position) VALUES (:name, :team, :pos) ON CONFLICT (name) DO NOTHING"), {"name": name, "team": player_team, "pos": player_position})
            except Exception:
                # fallback: try simple insert (may raise)
                try:
                    await conn.execute(text("INSERT INTO players (name, team, position) VALUES (:name, :team, :pos)"), {"name": name, "team": player_team, "pos": player_position})
                except Exception:
                    pass
            res = await conn.execute(text("SELECT id FROM players WHERE name = :name"), {"name": name})
            row = res.first()
            player_id = row[0] if row else None

        if player_id is None:
            print(f"WARNING: couldn't resolve player id for {player}; skipping DB upsert")
            return

        # Upsert games and player_stats
        for r in rows:
            gid = r.get("gameId") or r.get("game_id") or r.get("game_id")
            game_date = r.get("gameDate") or r.get("date") or r.get("game_date")
            home = r.get("homeTeam") or r.get("home_team")
            away = r.get("awayTeam") or r.get("away_team")
            stat_value = r.get("statValue") or r.get("stat_value")

            # insert game if not exists
            if db.DATABASE_URL.startswith("sqlite"):
                await conn.execute(text("INSERT OR IGNORE INTO games (id, game_date, home_team, away_team) VALUES (:id, :gd, :home, :away)"), {"id": gid, "gd": game_date, "home": home, "away": away})
            else:
                try:
                    await conn.execute(text("INSERT INTO games (id, game_date, home_team, away_team) VALUES (:id, :gd, :home, :away) ON CONFLICT (id) DO NOTHING"), {"id": gid, "gd": game_date, "home": home, "away": away})
                except Exception:
                    try:
                        await conn.execute(text("INSERT INTO games (id, game_date, home_team, away_team) VALUES (:id, :gd, :home, :away)"), {"id": gid, "gd": game_date, "home": home, "away": away})
                    except Exception:
                        pass

            # insert player_stat (avoid duplicates by checking existence)
            try:
                res = await conn.execute(text("SELECT 1 FROM player_stats WHERE player_id = :pid AND game_id = :gid AND stat_type = :st"), {"pid": player_id, "gid": gid, "st": r.get("statType") or "points"})
                exists = res.first()
            except Exception:
                exists = None
            if not exists:
                try:
                    await conn.execute(text("INSERT INTO player_stats (player_id, game_id, stat_type, value) VALUES (:pid, :gid, :st, :val)"), {"pid": player_id, "gid": gid, "st": r.get("statType") or "points", "val": stat_value})
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", default=None, help="comma-separated player names")
    parser.add_argument("--max-games", type=int, default=200)
    parser.add_argument("--deep", action="store_true", help="attempt deeper historical fetch (career/season-by-season)")
    parser.add_argument("--use-nba-api", action="store_true", help="use nba_api to fetch season-by-season game logs (requires nba_api installed)")
    parser.add_argument("--target-min-games", type=int, default=None, help="target minimum games to collect per player when running deep fetch")
    parser.add_argument("--seasons-start", type=int, default=None, help="start season year (e.g., 2000)")
    parser.add_argument("--seasons-end", type=int, default=None, help="end season year (e.g., 2025)")
    parser.add_argument("--out-dir", default="backend/ingest_audit")
    parser.add_argument("--commit", action="store_true", help="upsert fetched rows into the dev DB")
    parser.add_argument("--confirm", action="store_true", help="confirm commit (safety guard)")
    args = parser.parse_args()

    players = [p.strip() for p in (args.players or "").split(",") if p.strip()]
    if not players:
        # default list
        players = [
            "LeBron James",
            "Stephen Curry",
            "Luka Doncic",
            "Giannis Antetokounmpo",
            "Kevin Durant",
            "Jayson Tatum",
            "Nikola Jokic",
            "Joel Embiid",
            "Jimmy Butler",
            "Devin Booker",
        ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_event_loop()
    for player in players:
        print(f"Fetching games for: {player}")
        games = loop.run_until_complete(fetch_player_games(player, max_games=args.max_games, deep=args.deep, target_min_games=args.target_min_games, seasons_start=args.seasons_start, seasons_end=args.seasons_end))
        # optional nba_api deep fetch augmentation
        if args.use_nba_api:
            print(f"Attempting nba_api-backed fetch for {player} (seasons {args.seasons_start}..{args.seasons_end})")
            try:
                from backend.services import nba_api_helper
            except Exception:
                nba_api_helper = None

            try:
                pid = nba_stats_client.find_player_id_by_name(player) or nba_stats_client.find_player_id(player)
            except Exception:
                pid = None

            if pid and nba_api_helper is not None:
                try:
                    nba_rows = nba_api_helper.fetch_career_games_by_id(pid, seasons_start=args.seasons_start or 2000, seasons_end=args.seasons_end or 2025)
                    # combine with existing `games`, dedupe by GAME_ID or gameId
                    combined = []
                    seen = set()
                    for r in (nba_rows or []) + (games or []):
                        # accept common casing variants returned by different helpers
                        gid = (
                            r.get("GAME_ID")
                            or r.get("Game_ID")
                            or r.get("gameId")
                            or r.get("GameId")
                            or r.get("game_id")
                            or r.get("id")
                        )
                        if not gid:
                            continue
                        if gid in seen:
                            continue
                        seen.add(gid)
                        combined.append(r)
                    games = combined
                except Exception:
                    print(f"nba_api_helper failed for {player}; skipping nba_api augmentation")
            else:
                print(f"nba_api: helper or player id unavailable for {player}; skipping nba_api augmentation")
        normalized = [normalize_game_row(g) for g in games]
        if not normalized:
            print(f"No games found for {player}; skipping")
            continue
        fname = loop.run_until_complete(write_audit_file(out_dir, player, normalized))
        print(f"Wrote audit file: {fname}")
        if args.commit:
            if not args.confirm:
                print("Skipping DB commit because --confirm not provided")
            else:
                print(f"Upserting {len(normalized)} rows for {player} into DB (dev)...")
                loop.run_until_complete(upsert_into_db(player, games))


if __name__ == "__main__":
    main()
