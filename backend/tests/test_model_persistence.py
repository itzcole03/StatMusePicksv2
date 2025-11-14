import pathlib


def test_model_load_and_predict():
    """Smoke test: load persisted model and run a single prediction."""
    import joblib
    import numpy as np

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    model_path = repo_root / "models_store" / "LeBron_James.pkl"
    assert model_path.exists(), f"Expected model at {model_path}"

    model = joblib.load(model_path)

    # Determine expected input width from model attributes, fallback to 34
    n_features = getattr(model, "n_features_in_", None) or getattr(model, "n_features_", None) or 34
    X = np.zeros((1, int(n_features)))

    # Ensure model can produce a prediction or predict_proba output
    if hasattr(model, "predict"):
        preds = model.predict(X)
        assert hasattr(preds, "shape") and preds.shape[0] == 1
    elif hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)
        assert probs.shape[0] == 1
    else:
        raise AssertionError("Loaded object is not a scikit-learn estimator with predict()/predict_proba().")
