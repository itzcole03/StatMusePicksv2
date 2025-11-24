import pandas as pd
import glob

players=['Stephen_Curry','Kevin_Durant','Luka_Doncic','LeBron_James']
cols=['multi_PER','multi_WS','adv_PER','adv_WS']
for p in players:
    files=glob.glob(f'backend/models_store/player_features_{p}_*.csv')
    if not files:
        print(p,'no file')
        continue
    f=sorted(files)[-1]
    df=pd.read_csv(f)
    print('\nFile:', f)
    for col in cols:
        if col in df.columns:
            vals=df[col].dropna()
            print(p, col, 'unique_count=',vals.nunique(), 'mean=', round(float(vals.mean()),4) if len(vals)>0 else 'nan', 'std=', round(float(vals.std()),4) if len(vals)>0 else 'nan')
        else:
            print(p, col, 'missing')
