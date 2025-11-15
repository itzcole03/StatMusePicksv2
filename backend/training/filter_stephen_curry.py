import pandas as pd

src = 'backend/data/training_datasets/points_dataset_07da6da35dd7.csv'
dst = 'backend/training/stephen_curry_dataset.csv'
print('Reading', src)
df = pd.read_csv(src)
# Filter exact player name
sdf = df[df['player_name'].str.strip() == 'Stephen Curry']
print('Found rows:', len(sdf))
if len(sdf) == 0:
    # try case-insensitive contains
    sdf = df[df['player_name'].str.contains('Stephen', case=False, na=False)]
    print('Fallback contains found rows:', len(sdf))
if len(sdf) == 0:
    raise SystemExit('No Stephen Curry rows found in source dataset')
# Save filtered dataset
sdf.to_csv(dst, index=False)
print('Wrote', dst)