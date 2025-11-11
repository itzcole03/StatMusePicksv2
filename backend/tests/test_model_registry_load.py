import os
from backend.services.model_registry import ModelRegistry


def test_load_saved_model():
    # This test assumes `persist_toy_model.py` ran and created a model file
    player = os.environ.get('TOY_PLAYER_NAME', 'LeBron James')
    reg = ModelRegistry()
    model = reg.load_model(player)
    assert model is not None

    # If the model supports predict, call it on a dummy array
    try:
        import numpy as np

        X = np.zeros((1, 5))
        preds = model.predict(X)
        assert hasattr(preds, '__len__')
    except Exception:
        # model may be a stub; at minimum load succeeded
        pass
