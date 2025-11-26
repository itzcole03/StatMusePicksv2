import pandas as pd

p = r"backend\data\datasets\points_dataset_v20251121T235153Z_c71436ea\points_dataset_val_v20251121T235153Z_ba19a764\features.parquet"
df = pd.read_parquet(p)
print(list(df.columns))
print(df.head(3))
print("rows", len(df))
