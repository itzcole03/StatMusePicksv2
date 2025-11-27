import json
from pathlib import Path

p = Path("backend/models_store/dataset_generation_progress.json")
print("progress exists:", p.exists())
if p.exists():
    data = json.loads(p.read_text())
    processed = data.get("processed", [])
    print("processed count:", len(processed))
    print("last 10 processed:", processed[-10:])

print("\nRecent dataset manifests:")
for f in sorted(
    Path("backend/data/datasets").rglob("dataset_manifest.json"),
    key=lambda x: x.stat().st_mtime,
    reverse=True,
)[:5]:
    print(f)

from backend.services import training_data_service as tds

# quick test for a known player
from backend.services.nba_stats_client import find_player_id_by_name

name = "Trae Young"
try:
    pid = find_player_id_by_name(name)
    print("\nResolved", name, "->", pid)
    df = tds.generate_training_data(
        name,
        stat="points",
        min_games=1,
        fetch_limit=10,
        seasons=["2024-25"],
        pid=int(pid),
    )
    print("Generated rows for", name, ":", 0 if df is None else len(df))
    if df is not None:
        print(df.head().to_dict())
except Exception as e:
    print("Error during test:", e)
