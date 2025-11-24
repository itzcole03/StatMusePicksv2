import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
from backend.models.ensemble_model import build_voting_ensemble, predict, save_model, load_model

rng = np.random.RandomState(2)
X = rng.randn(250, 6)
y = X[:,0]*1.8 + X[:,1]*-1.2 + rng.randn(250)*0.15

model = build_voting_ensemble(X[:200], y[:200])
print('ensemble trained')
vals = predict(model, X[200:220])
print('preds shape', vals.shape)

p = 'backend/models_store/tmp_ensemble.pkl'
save_model(model, p)
model2 = load_model(p)
print('loaded ok, diff mean:', float((predict(model2, X[200:220]) - vals).mean()))
