"""Simple training orchestrator for small-scale runs.

Reads a dataset manifest produced by `training_data_service.export_dataset_with_version`,
applies a chronological split, trains a model via `training_pipeline.train_player_model`,
and saves the model using `ModelRegistry.save_model`.

This script is intentionally minimal so it can be used in CI smoke runs.
"""
import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd

from backend.services import training_data_service as tds
from backend.services import training_pipeline as tp
from backend.services.model_registry import ModelRegistry


def run_from_manifest(manifest_path: str, player_name: str, model_dir: str = None, train_frac: float = 0.7, val_frac: float = 0.15, test_frac: float = 0.15):
    m = tds.read_manifest(manifest_path)
    if not m:
        raise FileNotFoundError(f"manifest not found or invalid: {manifest_path}")

    files = m.get('files') or {}
    feat_path = files.get('features')
    labels_path = files.get('labels')
    if not feat_path or not os.path.exists(feat_path):
        raise FileNotFoundError('features file missing in manifest')

    # read features
    if feat_path.endswith('.parquet'):
        df = pd.read_parquet(feat_path)
    else:
        df = pd.read_csv(feat_path, compression='gzip')

    # if labels present, merge
    if labels_path and os.path.exists(labels_path):
        if labels_path.endswith('.parquet'):
            y = pd.read_parquet(labels_path)
        else:
            y = pd.read_csv(labels_path, compression='gzip')
        # if labels are a single column frame, convert
        if 'label' in y.columns and len(y.columns) == 1:
            df['target'] = y['label'].values
        else:
            # try to coerce first column
            df['target'] = y.iloc[:, 0].values
    else:
        # expect target column present
        if 'target' not in df.columns:
            raise ValueError('no labels provided and no target column present')

    # Ensure date column exists for chronological split
    date_col = 'game_date' if 'game_date' in df.columns else None
    train_df, val_df, test_df = tds.chronological_split_by_ratio(df, date_col=date_col or 'game_date', train_frac=train_frac, val_frac=val_frac, test_frac=test_frac)

    # Train on train_df (could include val for final model; keep simple)
    model = tp.train_player_model(train_df, target_col='target')

    # Save model via ModelRegistry
    registry = ModelRegistry(model_dir=model_dir) if model_dir else ModelRegistry()
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    version = f"auto-{ts}"
    registry.save_model(player_name, model, version=version, notes=json.dumps({'manifest': manifest_path}))

    report = {
        'player': player_name,
        'version': version,
        'saved_to': registry._model_path(player_name),
        'trained_rows': int(len(train_df)),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description='Train model from dataset manifest')
    parser.add_argument('--manifest', required=True, help='Path to manifest.json')
    parser.add_argument('--player', required=True, help='Player name to label saved model')
    parser.add_argument('--model-dir', default=None, help='Optional model store dir')
    args = parser.parse_args()

    r = run_from_manifest(args.manifest, args.player, model_dir=args.model_dir)
    print('Trained and saved model:', r)


if __name__ == '__main__':
    main()
