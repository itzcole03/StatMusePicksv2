import json
import os

from backend.services.data_ingestion_service import detect_outlier_values

p = os.path.join("backend", "ingest_audit", "games_raw_2025-11-18_repaired.json")
recs = []
with open(p, "r", encoding="utf-8") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln:
            recs.append(json.loads(ln))
outs = detect_outlier_values(recs, field="value", z_thresh=3.0)
miss = [i for i in outs if not recs[i].get("player_name")]
print("outliers:", len(outs), "missing_name:", len(miss))
if miss:
    print(
        "examples:",
        [
            (i, recs[i].get("player_nba_id"), recs[i].get("player_name"))
            for i in miss[:10]
        ],
    )
