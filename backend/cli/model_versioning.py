"""Model versioning CLI for basic model management tasks.

Commands:
  - list: list model files in `models_store`
  - show <player>: show model file path and existence
  - metadata <player>: show rows from `model_metadata` table for player
  - promote <player>: copy model to a production filename `<player>_production.pkl`
  - archive <player>: move model file to `models_store/archive/`

This CLI is intentionally lightweight and operates against on-disk artifacts and the
`model_metadata` table via a short-lived sync SQLAlchemy engine when DATABASE_URL is set.
"""
from __future__ import annotations

import argparse
import os
import shutil
import logging
from typing import Optional
from sqlalchemy import create_engine, select
from datetime import datetime

from backend.services.model_registry import ModelRegistry, _sync_db_url

logger = logging.getLogger("model_versioning_cli")


def _safe_player(player: str) -> str:
    return player.strip()


def _print_file_info(path: str) -> None:
    try:
        st = os.stat(path)
        size = st.st_size
        mtime = datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z"
        print(f"  size={size} bytes  mtime={mtime}")
    except Exception:
        pass


def list_models(reg: ModelRegistry):
    names = reg.list_models()
    if not names:
        print("No model files found in models_store")
        return
    for f in names:
        print(f)
        _print_file_info(os.path.join(reg.model_dir, f))


def show_model(reg: ModelRegistry, player: str):
    player = _safe_player(player)
    path = reg._model_path(player)
    exists = os.path.exists(path)
    print(f"Model path: {path}")
    print(f"Exists: {exists}")
    if exists:
        _print_file_info(path)


def _insert_metadata_row(player: str, version: Optional[str], path: str, notes: Optional[str]):
    try:
        from backend.models.model_metadata import ModelMetadata

        sync_url = _sync_db_url(os.environ.get("DATABASE_URL"))
        engine = create_engine(sync_url, future=True)
        with engine.begin() as conn:
            ins = ModelMetadata.__table__.insert().values(
                name=player,
                version=version,
                path=os.path.abspath(path),
                notes=notes,
            )
            conn.execute(ins)
        print(f"Inserted metadata row for {player} (version={version})")
    except Exception as e:
        print("Warning: could not insert metadata row:", e)


def promote_model(reg: ModelRegistry, player: str, tag: str = "production", force: bool = False):
    player = _safe_player(player)
    src = reg._model_path(player)
    if not os.path.exists(src):
        print(f"Source model not found: {src}")
        return
    safe = player.replace(" ", "_")
    dst = os.path.join(reg.model_dir, f"{safe}_{tag}.pkl")
    if os.path.exists(dst) and not force:
        print(f"Destination already exists: {dst} (use --force to overwrite)")
        return
    shutil.copy2(src, dst)
    print(f"Promoted {src} -> {dst}")
    # attempt to record metadata for the promoted artifact
    try:
        _insert_metadata_row(player, version=tag, path=dst, notes=f"promoted at {datetime.utcnow().isoformat()}Z")
    except Exception:
        pass


def archive_model(reg: ModelRegistry, player: str, force: bool = False):
    player = _safe_player(player)
    src = reg._model_path(player)
    if not os.path.exists(src):
        print(f"Source model not found: {src}")
        return
    archive_dir = os.path.join(reg.model_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    dst = os.path.join(archive_dir, os.path.basename(src))
    if os.path.exists(dst) and not force:
        print(f"Archive already contains {dst} (use --force to overwrite)")
        return
    shutil.move(src, dst)
    print(f"Archived {src} -> {dst}")


def show_metadata(player: str, db_url: Optional[str] = None):
    try:
        from backend.models.model_metadata import ModelMetadata
    except Exception as e:
        print("Could not import ModelMetadata:", e)
        return

    sync_url = _sync_db_url(os.environ.get("DATABASE_URL") or db_url)
    engine = create_engine(sync_url, future=True)
    with engine.begin() as conn:
        stmt = select(ModelMetadata).where(ModelMetadata.name == player)
        res = conn.execute(stmt).scalars().all()
        if not res:
            print(f"No metadata rows found for player: {player}")
            return
        for row in res:
            print(f"id={row.id} name={row.name} version={row.version} path={row.path} created_at={row.created_at} notes={row.notes}")


def main(argv: Optional[list] = None):
    p = argparse.ArgumentParser(prog="model_versioning")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List model files in models_store")

    sp = sub.add_parser("show", help="Show model path and existence for player")
    sp.add_argument("player")

    sp2 = sub.add_parser("metadata", help="Show model_metadata rows for player")
    sp2.add_argument("player")

    sp3 = sub.add_parser("promote", help="Promote model to tagged production copy")
    sp3.add_argument("player")
    sp3.add_argument("--tag", default="production", help="Tag to append to promoted filename (default: production)")
    sp3.add_argument("--force", action="store_true", help="Overwrite destination if exists")

    sp4 = sub.add_parser("archive", help="Archive model file to models_store/archive/")
    sp4.add_argument("player")
    sp4.add_argument("--force", action="store_true", help="Overwrite archived file if exists")

    args = p.parse_args(argv)

    reg = ModelRegistry()

    if args.cmd == "list":
        list_models(reg)
    elif args.cmd == "show":
        show_model(reg, args.player)
    elif args.cmd == "promote":
        promote_model(reg, args.player, tag=args.tag, force=args.force)
    elif args.cmd == "archive":
        archive_model(reg, args.player, force=args.force)
    elif args.cmd == "metadata":
        show_metadata(args.player)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
