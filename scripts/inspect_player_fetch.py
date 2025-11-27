#!/usr/bin/env python3
"""Fetch sample players' multi-season games and print first 3 normalized records."""
PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Kevin Durant",
    "Giannis Antetokounmpo",
    "Luka Doncic",
]
SEASONS = ["2024-25", "2023-24", "2022-23"]


def main():
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
        games = client.fetch_recent_games_multi(
            pid, seasons=SEASONS, limit_per_season=82
        )
        print(f"Fetched {len(games)} games for {name}")
        sample = []
        for g in games[:10]:
            rec = {}
            rec["raw"] = g
            # map known keys (as fetch_and_ingest_players does)
            gd = (
                g.get("GAME_DATE")
                or g.get("gameDate")
                or g.get("GAME_DATE_RAW")
                or g.get("GAME_DATE_EST")
            )
            rec["game_date"] = gd
            rec["home_team"] = (
                g.get("TEAM_ABBREVIATION")
                or g.get("TEAM")
                or g.get("team")
                or "UNKNOWN"
            )
            rec["away_team"] = (
                g.get("OPP_TEAM_ABBREVIATION")
                or g.get("OPP_TEAM")
                or g.get("opponent")
                or "UNKNOWN"
            )
            val = None
            for k in ("PTS", "PTS_PLAYER", "PLAYER_PTS", "PTS_HOME", "PTS_AWAY"):
                if k in g:
                    val = g.get(k)
                    break
            if val is None:
                for kk, vv in g.items():
                    if kk.upper() == "PTS":
                        val = vv
                        break
            rec["stat_type"] = "points" if val is not None else None
            rec["value"] = val
            rec["player_name"] = name
            rec["player_nba_id"] = pid
            sample.append(rec)
        print(f"Sample normalized records for {name} (up to 3):")
        import pprint

        pprint.pprint(sample[:3])
        all_records.extend(sample)

    print("\nTotal sample records collected:", len(all_records))


if __name__ == "__main__":
    main()
