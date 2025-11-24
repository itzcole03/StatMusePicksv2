"""Small dataset management CLI helpers.

Functions:
 - list_datasets(output_dir)
 - delete_old_versions(name, keep=1, output_dir='datasets', dry_run=True)

This module is intentionally minimal and safe; deletion is explicit and
only removes directories that look like dataset version folders produced
by `training_data_service.export_dataset_with_version`.
"""
from pathlib import Path
import shutil
from typing import List, Optional

from backend.services import training_data_service as tds


def list_datasets(output_dir: str = 'datasets') -> List[dict]:
    return tds.list_datasets(output_dir=output_dir)


def delete_old_versions(name: str, keep: int = 1, output_dir: str = 'datasets', dry_run: bool = True) -> List[str]:
    """Delete older dataset versions for `name`, keeping the newest `keep`.

    Returns a list of deleted paths. If `dry_run` is True, no deletion is performed.
    """
    manifests = tds.list_datasets(output_dir=output_dir)
    # filter by name
    filtered = [m for m in manifests if m.get('name') == name]
    if not filtered:
        return []
    # assume manifests sorted oldest -> newest
    to_delete = filtered[:-keep] if keep > 0 else filtered
    deleted = []
    for m in to_delete:
        mp = m.get('_manifest_path')
        if not mp:
            continue
        p = Path(mp).parent
        if not p.exists():
            continue
        if dry_run:
            deleted.append(str(p))
            continue
        try:
            shutil.rmtree(p)
            deleted.append(str(p))
        except Exception:
            continue
    return deleted


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Dataset registry utilities')
    sub = parser.add_subparsers(dest='cmd')

    p_list = sub.add_parser('list')
    p_list.add_argument('--output-dir', default='datasets')

    p_prune = sub.add_parser('prune')
    p_prune.add_argument('name')
    p_prune.add_argument('--keep', type=int, default=1)
    p_prune.add_argument('--output-dir', default='datasets')
    p_prune.add_argument('--yes', action='store_true', help='Perform deletion (otherwise dry-run)')

    args = parser.parse_args()
    if args.cmd == 'list':
        for m in list_datasets(output_dir=args.output_dir):
            print(m.get('name'), m.get('version'), m.get('uid'))
    elif args.cmd == 'prune':
        deleted = delete_old_versions(args.name, keep=args.keep, output_dir=args.output_dir, dry_run=not args.yes)
        if deleted:
            print('Will delete:' if not args.yes else 'Deleted:')
            for d in deleted:
                print(d)
        else:
            print('No versions to delete')
