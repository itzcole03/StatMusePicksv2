import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
from backend.models.xgboost_model import train_xgboost, predict, save_model, load_model

# synthetic regression data
rng = np.random.RandomState(0)
X = rng.randn(200, 5)
y = X[:, 0]*2.0 + X[:,1]*-1.5 + rng.randn(200)*0.1

# simple split
X_train, X_val = X[:160], X[160:180]
y_train, y_val = y[:160], y[160:180]

model = train_xgboost(X_train, y_train, X_val=X_val, y_val=y_val, num_rounds=50, early_stopping_rounds=5)
preds = predict(model, X_val)
print('preds shape', preds.shape)
# save/load
p = 'backend/models_store/tmp_xgb.pkl'
save_model(model, p)
model2 = load_model(p)
print('loaded ok, predict matches:', (predict(model2, X_val) - preds).mean())
