import pandas as pd
from backend.services import training_pipeline as tp

# create tiny dataset
s = {
    'recent_mean':[10.0,12.0,9.5],
    'recent_std':[2.0,1.5,2.5],
    'multi_PER':[15.0,16.2,14.8],
    'multi_TS_PCT':[0.55,0.57,0.52],
    'multi_BPM':[1.2,2.0,-0.5],
    'multi_USG_PCT':[22.0,24.0,20.0],
    'multi_season_PTS_avg':[11.0,13.0,9.0],
    'multi_season_count':[2,3,1],
    'multi_PIE':[0.10,0.12,0.09],
    'multi_off_rating':[110.0,112.0,108.0],
    'multi_def_rating':[105.0,103.0,107.0],
    'target':[11.5,12.8,9.2]
}

df = pd.DataFrame(s)
model = tp.train_player_model(df, target_col='target')
print('trained-model-type:', type(model))
tp.save_model(model, 'backend/models_store/tmp_model_bpm_test.pkl')
print('saved-model')
