#!/usr/bin/env python3
"""Load cached game logs from backend/data/cached_game_logs and run ingestion."""
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(__file__))
CACHED_DIR = os.path.join(ROOT, "backend", "data", "cached_game_logs")

all_records = []
if os.path.exists(CACHED_DIR):
    for fname in os.listdir(CACHED_DIR):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(CACHED_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    # Normalize team-level cached logs into minimal game records
                    for rec in data:
                        # Try to normalize common keys to our expected schema
                        out = {}
                        # date
                        if "GAME_DATE" in rec:
                            out["game_date"] = rec.get("GAME_DATE")
                        elif "game_date" in rec:
                            out["game_date"] = rec.get("game_date")
                        # scores
                        if "PTS" in rec:
                            out["home_score"] = rec.get("PTS")
                        if "OPP_PTS" in rec:
                            out["away_score"] = rec.get("OPP_PTS")
                        # ensure required team fields exist: attempt to infer from filename
                        # filename pattern: team_<teamid>_<season>.json
                        parts = fname.split("_")
                        team_abbr = None
                        try:
                            if (
                                parts[0].lower().startswith("team")
                                and parts[1].isdigit()
                            ):
                                tid = parts[1]
                                # common mapping for GSW
                                if tid == "1610612744":
                                    team_abbr = "GSW"
                                else:
                                    team_abbr = f"TEAM_{tid}"
                        except Exception:
                            team_abbr = None

                        out["home_team"] = team_abbr or "UNKNOWN"
                        out["away_team"] = "UNKNOWN"
                        all_records.append(out)
                elif isinstance(data, dict):
                    # some files are dict with key 'games' or similar
                    if "games" in data and isinstance(data["games"], list):
                        all_records.extend(data["games"])
                    else:
                        # try to extract list values
                        for v in data.values():
                            if isinstance(v, list):
                                all_records.extend(v)
        except Exception as e:
            print(f"Failed to read {path}: {e}")

print(f"Loaded {len(all_records)} raw records from {CACHED_DIR}")

if not all_records:
    print("No cached records to ingest.")
    raise SystemExit(0)

try:
    from backend.services.data_ingestion_service import _process_and_ingest
except Exception as e:
    print("Failed to import ingestion helper:", e)
    raise

res = _process_and_ingest(all_records, when=date.today(), dry_run=False)
print("Ingestion result:", res)
