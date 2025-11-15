import joblib, numpy as np, os, json
p = "backend/models_store/player_1001/versions/6e096584dbff/player_1001_v9ef60e247496.joblib"
print("exists", os.path.exists(p))
if not os.path.exists(p):
    raise SystemExit("Model artifact not found: %s" % p)
m = joblib.load(p)
print("model type:", type(m))
n = getattr(m, "n_features_in_", None)
print("n_features_in_", n)
if n is None:
    X = np.zeros((1, 10))
else:
    X = np.zeros((1, n))
pred = m.predict(X)
try:
    print("prediction:", pred.tolist())
except Exception:
    print("prediction:", pred)
