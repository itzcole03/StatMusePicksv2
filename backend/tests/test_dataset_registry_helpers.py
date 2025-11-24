import tempfile
import os
from backend.services import training_data_service as tds
import pandas as pd


def test_list_and_latest_dataset_helpers_use_exported_manifests():
    df = pd.DataFrame({'x': [1, 2, 3]})
    y = pd.Series([0.1, 0.2, 0.3])
    with tempfile.TemporaryDirectory() as td:
        # create two versions sequentially
        m1 = tds.export_dataset_with_version(df, y=y, output_dir=td, name='myds', version='v1', fmt_prefer='csv')
        m2 = tds.export_dataset_with_version(df, y=y, output_dir=td, name='myds', version='v2', fmt_prefer='csv')

        all_manifests = tds.list_datasets(output_dir=td)
        # ensure at least two manifests present for this dataset name
        myds = [m for m in all_manifests if m.get('name') == 'myds']
        assert len(myds) >= 2

        latest = tds.latest_dataset('myds', output_dir=td)
        assert latest is not None
        assert latest.get('version') in ('v2', 'v2')
        # verify manifest path exists
        assert latest.get('_manifest_path') and os.path.exists(latest['_manifest_path'])
