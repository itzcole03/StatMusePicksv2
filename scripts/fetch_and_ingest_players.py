#!/usr/bin/env python3
"""Fetch multi-season player logs for selected players via nba_stats_client and ingest."""
from datetime import date

PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Kevin Durant",
    "Giannis Antetokounmpo",
    "Luka Doncic",
]
SEASONS = ["2024-25", "2023-24", "2022-23"]

try:
    from backend.services import nba_stats_client as client
except Exception as e:
    print("nba_stats_client import failed:", e)
    raise

all_records = []
for name in PLAYERS:
    pid = client.find_player_id_by_name(name)
    print(f"Player {name} -> id {pid}")
    if not pid:
        continue
    games = client.fetch_recent_games_multi(pid, seasons=SEASONS, limit_per_season=82)
    print(f"Fetched {len(games)} games for {name}")
    for g in games:
        rec = {}
        # map known keys
        # prefer GAME_DATE or gameDate
        gd = g.get("GAME_DATE") or g.get("gameDate") or g.get("GAME_DATE_RAW")
        rec["game_date"] = gd
        # teams attempt
        rec["home_team"] = (
            g.get("TEAM_ABBREVIATION") or g.get("TEAM") or g.get("team") or "UNKNOWN"
        )
        rec["away_team"] = (
            g.get("OPP_TEAM_ABBREVIATION")
            or g.get("OPP_TEAM")
            or g.get("opponent")
            or "UNKNOWN"
        )
        # stat: points
        # many variants: PTS, PTS_PLAYER
        val = None
        for k in ("PTS", "PTS_PLAYER", "PLAYER_PTS", "PTS_HOME", "PTS_AWAY"):
            if k in g:
                val = g.get(k)
                break
        if val is None:
            # try 'PTS' case-insensitive
            for kk, vv in g.items():
                if kk.upper() == "PTS":
                    val = vv
                    break
        if val is None:
            # skip if no points field
            continue
        rec["player_name"] = name
        rec["player_nba_id"] = pid
        rec["stat_type"] = "points"
        rec["value"] = val
        all_records.append(rec)

print(f"Total player records to ingest: {len(all_records)}")
if not all_records:
    print("No player records fetched; aborting.")
    raise SystemExit(0)

# call ingestion helper
try:
    from backend.services.data_ingestion_service import _process_and_ingest
except Exception as e:
    print("Failed to import ingestion helper:", e)
    raise

res = _process_and_ingest(all_records, when=date.today(), dry_run=False)
print("Ingestion result:", res)
