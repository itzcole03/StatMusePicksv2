import pandas as pd
from pathlib import Path
base=Path('backend/data/datasets/points_dataset_v20251119T043328Z_fcb745d9')
parts=['points_dataset_train_v20251119T043328Z_69d82ff0','points_dataset_val_v20251119T043328Z_8c5abf5c','points_dataset_test_v20251119T043328Z_f6efd0fb']
for p in parts:
    f=base/ p / 'features.parquet'
    print('\n===', p)
    if not f.exists():
        print('MISSING', f)
        continue
    df=pd.read_parquet(f)
    print('shape', df.shape)
    print('dtypes:\n', df.dtypes)
    print('head:\n', df.head(5).to_string(index=False))
