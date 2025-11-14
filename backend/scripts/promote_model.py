#!/usr/bin/env python3
"""CLI helper to promote a saved player model to production.

Usage:
    python backend/scripts/promote_model.py --player "LeBron James" --version <ver> --by alice --notes "promote for prod" --write-legacy
"""
import argparse
from backend.services.model_registry import PlayerModelRegistry


def _cli(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--player", required=True)
    p.add_argument("--version", required=False)
    p.add_argument("--by", dest="by", required=False)
    p.add_argument("--notes", required=False)
    p.add_argument("--write-legacy", action="store_true")
    p.add_argument("--store-dir", default="backend/models_store")
    args = p.parse_args(argv)

    reg = PlayerModelRegistry(args.store_dir)
    meta = reg.promote_model(args.player, version=args.version, promoted_by=args.by, notes=args.notes, write_legacy_pkl=args.write_legacy)
    if meta is None:
        print(f"Failed to promote model for {args.player} (version={args.version})")
        return 2
    print("Promotion successful:")
    for k, v in meta.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
