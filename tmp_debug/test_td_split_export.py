import sys
import os
import pandas as pd
# ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from backend.services.training_data_service import chronological_split_by_ratio, export_dataset_with_version
from pathlib import Path

def make_df(n=100):
    dates = pd.date_range('2020-01-01', periods=n, freq='D')
    df = pd.DataFrame({'player': ['Test Player']*n, 'game_date': dates, 'feature1': range(n), 'target': [float(i%30) for i in range(n)]})
    return df

if __name__ == '__main__':
    df = make_df(23)
    train, val, test = chronological_split_by_ratio(df, date_col='game_date', train_frac=0.7, val_frac=0.15, test_frac=0.15)
    print('rows:', len(df), 'train', len(train), 'val', len(val), 'test', len(test))
    out = export_dataset_with_version(train.drop(columns=['target']), y=train['target'], output_dir='backend/models_store/datasets_test', name='test_dataset')
    print('manifest written:', out)
    p = Path(out['files']['features'])
    print('features exists:', p.exists())
