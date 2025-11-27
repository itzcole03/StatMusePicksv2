import importlib.util
import os
import tempfile
from pathlib import Path

import pandas as pd

from backend.services import training_data_service as tds


def _load_module_from_path(path):
    spec = importlib.util.spec_from_file_location("datasets_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_delete_old_versions_cli_prune_and_list():
    df = pd.DataFrame({"a": [1, 2, 3]})
    y = pd.Series([0.1, 0.2, 0.3])
    with tempfile.TemporaryDirectory() as td:
        # create three versions
        tds.export_dataset_with_version(
            df, y=y, output_dir=td, name="cli_ds", version="v1", fmt_prefer="csv"
        )
        tds.export_dataset_with_version(
            df, y=y, output_dir=td, name="cli_ds", version="v2", fmt_prefer="csv"
        )
        tds.export_dataset_with_version(
            df, y=y, output_dir=td, name="cli_ds", version="v3", fmt_prefer="csv"
        )

        script_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "datasets.py"
        )
        script_path = str(Path(script_path).resolve())
        mod = _load_module_from_path(script_path)

        # dry run prune
        deleted = mod.delete_old_versions("cli_ds", keep=1, output_dir=td, dry_run=True)
        # Should report two paths to delete
        assert len(deleted) >= 2

        # perform actual deletion
        deleted_real = mod.delete_old_versions(
            "cli_ds", keep=1, output_dir=td, dry_run=False
        )
        # after deletion only one dataset dir should remain for cli_ds
        remaining = [
            d for d in tds.list_datasets(output_dir=td) if d.get("name") == "cli_ds"
        ]
        assert len(remaining) == 1
