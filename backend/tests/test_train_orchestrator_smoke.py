import pandas as pd
from backend.services import training_data_service as tds
from backend.services import training_pipeline as tp
from backend.services.model_registry import ModelRegistry


def test_train_orchestrator_smoke(tmp_path, monkeypatch):
    """Smoke test: ensure a minimal orchestrator flow can generate a dataset,
    train a trivial model (mocked), and persist it via ModelRegistry.
    """
    player_name = "Smoke Player"

    # Build a tiny synthetic dataset
    df = pd.DataFrame({
        "game_date": pd.date_range("2020-01-01", periods=20),
        "feat1": list(range(20)),
        "target": [i * 0.5 + 1.0 for i in range(20)],
    })

    # Monkeypatch generator to return our synthetic DF
    monkeypatch.setattr(tds, "generate_training_data", lambda name, stat, min_games, fetch_limit, seasons: df.copy())

    # Use the real chronological splitter
    train_df, val_df, test_df = tds.chronological_split_by_ratio(df, date_col="game_date")

    # Provide a simple trainer that returns a picklable sklearn model
    def fake_train(df, target_col):
        from sklearn.linear_model import LinearRegression

        X = df[["feat1"]].values
        y = df[target_col].values
        m = LinearRegression()
        m.fit(X, y)
        return m

    monkeypatch.setattr(tp, "train_player_model", fake_train)

    # Use a tmp model directory so we don't touch repo state
    registry = ModelRegistry(model_dir=str(tmp_path / "models"))

    # Run the minimal per-player flow (what orchestrator would do)
    d = tds.generate_training_data(player_name, stat="points", min_games=1, fetch_limit=10, seasons=None)
    train_df, val_df, test_df = tds.chronological_split_by_ratio(d, date_col="game_date")

    model = tp.train_player_model(train_df, target_col="target")
    registry.save_model(player_name, model, version="vtest", notes="smoke")

    # Verify artifact saved
    path = registry._model_path(player_name)
    import os


    assert os.path.exists(path)
