import tempfile
import os
import pandas as pd

from backend.services import training_data_service as tds


def test_train_orchestrator_trains_and_saves_model():
    # Create simple dataset with target
    df = pd.DataFrame({
        'game_date': pd.date_range('2020-01-01', periods=20),
        'feat1': range(20),
        'feat2': [float(i) * 0.5 for i in range(20)],
        'target': [float(i) for i in range(20)],
    })
    with tempfile.TemporaryDirectory() as td:
        manifest = tds.export_dataset_with_version(df, y=None, output_dir=td, name='orchestrator_test', version='v0', fmt_prefer='csv')
        manifest_path = os.path.join(td, [d for d in os.listdir(td) if d.startswith('orchestrator_test')][0], 'manifest.json')
        # run orchestrator script functionally
        from scripts.train_orchestrator import run_from_manifest
        report = run_from_manifest(manifest_path, player_name='Test Player', model_dir=os.path.join(td, 'models'))
        assert report.get('player') == 'Test Player'
        assert os.path.exists(report.get('saved_to'))
