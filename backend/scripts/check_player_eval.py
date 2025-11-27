"""Check evaluation for a single player using existing eval helpers.

Usage: python backend/scripts/check_player_eval.py manifest.json "Stephen Curry" models_dir
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.eval_report import evaluate_model_on_df, load_model_if_exists

if len(sys.argv) < 4:
    print("Usage: check_player_eval.py manifest player_name models_dir")
    sys.exit(2)

manifest = Path(sys.argv[1])
player = sys.argv[2]
models_dir = Path(sys.argv[3])

m = json.loads(manifest.read_text(encoding="utf8"))
test_p = Path(m["parts"]["test"]["files"]["features"])
df_test = pd.read_parquet(test_p)
player_df = df_test[df_test["player"] == player].copy()
print("Rows for player:", player_df.shape[0])
if player_df.shape[0] == 0:
    sys.exit(0)

# infer features
exclude = set(["game_date", "player", "target"])
feature_cols = [c for c in player_df.columns if c not in exclude]
print("Inferred feature cols count:", len(feature_cols))

# find model
candidates = list(models_dir.glob(f"{player}*.pkl")) + list(
    models_dir.glob(f"{player.replace(' ', '_')}*.pkl")
)
print("Candidates:", [str(p.name) for p in candidates])

# try load common names
for p in candidates:
    print("Trying model", p)
    model = load_model_if_exists(str(p))
    if model is None:
        print("load failed")
        continue
    res = evaluate_model_on_df(model, player_df, feature_cols)
    print("Result:", res)
    break
