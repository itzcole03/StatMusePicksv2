import argparse
import json
import os
import subprocess
from pathlib import Path

import pandas as pd


def build_alias_table(mismatch_csv: Path, alias_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(mismatch_csv)
    df = df.dropna(subset=["resolved_player_id"])  # keep only resolved
    df["resolved_player_id"] = df["resolved_player_id"].astype(str).str.strip()
    df = df[df["resolved_player_id"] != ""]
    df.to_csv(alias_csv, index=False)
    return df


def filter_manifest_for_players(manifest_path: Path, player_ids, out_dir: Path) -> Path:
    manifest = json.loads(manifest_path.read_text())
    parts = manifest.get("parts", {})
    out_dir.mkdir(parents=True, exist_ok=True)
    new_manifest = dict(manifest)
    new_manifest["name"] = manifest.get("name", "subset") + "_alias_subset"
    new_manifest["uid"] = new_manifest.get("uid", "") + "_alias"
    new_manifest["parts"] = {}

    for split, info in parts.items():
        files = info.get("files", {})
        feat_rel = files.get("features")
        if not feat_rel:
            continue
        # Resolve feature file path robustly: handle absolute paths, paths
        # already rooted at manifest parent, and relative paths.
        feat_candidate = Path(feat_rel)
        if feat_candidate.is_absolute():
            feat_path = feat_candidate
        else:
            # If feat_rel already starts with the manifest parent path, avoid duplicating
            parent_str = str(manifest_path.parent).replace("\\", "/")
            rel_str = str(feat_rel).replace("\\", "/")
            if rel_str.startswith(parent_str) or rel_str.startswith(
                str(manifest_path.parent)
            ):
                feat_path = Path(rel_str)
            else:
                feat_path = manifest_path.parent / feat_rel
        feat_path = feat_path.resolve()
        df = pd.read_parquet(feat_path)
        if "player_id" not in df.columns:
            raise RuntimeError("features file missing 'player_id' column")

        # Normalize alias player_ids into integer set (handle floats like '1631210.0')
        resolved_ints = set()
        for x in player_ids:
            try:
                resolved_ints.add(int(float(x)))
            except Exception:
                continue

        # Coerce df player_id to numeric and match against resolved ints
        df_player_num = pd.to_numeric(df["player_id"], errors="coerce")
        if df_player_num.isna().all():
            # no numeric player ids present
            raise RuntimeError(
                f"features file {feat_path} has no numeric player_id values"
            )

        mask = df_player_num.fillna(-1).astype(int).isin(resolved_ints)
        subset = df.loc[mask].copy()

        # Ensure player_id dtype is integer in exported parquet
        subset["player_id"] = pd.to_numeric(
            subset["player_id"], errors="coerce"
        ).astype("Int64")

        out_feat = out_dir / f"{split}_features.parquet"
        subset.to_parquet(out_feat, index=False)

        print(f"Wrote {len(subset)} rows to {out_feat} (split={split})")

        new_manifest["parts"][split] = {
            "columns": list(subset.columns),
            "files": {"features": os.path.relpath(out_feat, out_dir)},
            "rows": len(subset),
        }

    out_manifest_path = out_dir / "dataset_manifest.json"
    out_manifest_path.write_text(json.dumps(new_manifest, indent=2))
    return out_manifest_path


def run_orchestrator(manifest_path: Path, out_dir: Path, report_csv: Path):
    cmd = [
        "python",
        str(Path("backend/scripts/train_orchestrator_roster.py")),
        "--manifest",
        str(manifest_path),
        "--out-dir",
        str(out_dir),
        "--report-csv",
        str(report_csv),
    ]
    subprocess.check_call(cmd)


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mismatch-csv",
        default="backend/models_store/roster_run/roster_mapping_mismatch.csv",
    )
    p.add_argument(
        "--manifest",
        default="backend/data/datasets/points_dataset_v20251121T235153Z_c71436ea/dataset_manifest.json",
    )
    p.add_argument("--alias-csv", default="backend/models_store/roster_alias_table.csv")
    p.add_argument(
        "--out-manifest-dir",
        default="backend/data/datasets/points_dataset_v20251121T235153Z_c71436ea/alias_subset",
    )
    p.add_argument(
        "--out-model-dir", default="backend/models_store/roster_run_alias_subset"
    )
    p.add_argument(
        "--report-csv",
        default="backend/models_store/roster_run_alias_subset_report.csv",
    )
    p.add_argument(
        "--no-run",
        dest="run",
        action="store_false",
        help="Create alias table and manifest but don't run orchestrator",
    )
    args = p.parse_args()

    mismatch = Path(args.mismatch_csv)
    alias_csv = Path(args.alias_csv)
    manifest = Path(args.manifest)
    out_manifest_dir = Path(args.out_manifest_dir)
    out_model_dir = Path(args.out_model_dir)
    report_csv = Path(args.report_csv)

    if not mismatch.exists():
        raise SystemExit(f"Mismatch CSV not found: {mismatch}")

    print(f"Building alias table from {mismatch} -> {alias_csv}")
    alias_df = build_alias_table(mismatch, alias_csv)
    player_ids = alias_df["resolved_player_id"].unique().tolist()
    print(f"Resolved {len(player_ids)} player_ids")

    print("Building filtered manifest and features for alias subset...")
    out_manifest = filter_manifest_for_players(manifest, player_ids, out_manifest_dir)
    print(f"Wrote subset manifest to {out_manifest}")

    if args.run:
        print("Running orchestrator on alias subset (this may take a while)...")
        run_orchestrator(out_manifest, out_model_dir, report_csv)
        print("Orchestrator finished")
    else:
        print("Skipping orchestrator run (--no-run).")


if __name__ == "__main__":
    main()
