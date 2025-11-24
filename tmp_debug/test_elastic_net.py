import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
from backend.models.elastic_net_model import train_elastic_net, predict, get_coefs, save_model, load_model

rng = np.random.RandomState(1)
X = rng.randn(300, 6)
y = X[:,0]*1.5 + X[:,2]*-0.7 + rng.randn(300)*0.2

model = train_elastic_net(X, y, cv=3)
print('alpha:', float(model.alpha_))
print('l1_ratio:', float(model.l1_ratio_))

preds = predict(model, X[:10])
print('preds[:3]', preds[:3])
print('coefs', get_coefs(model))

p='backend/models_store/tmp_elastic.pkl'
save_model(model,p)
print('saved')
model2 = load_model(p)
print('loaded, preds match:', (predict(model2, X[:10]) - preds).mean())
