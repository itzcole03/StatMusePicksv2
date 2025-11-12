Developer note: Stub model & NBA service wiring
=============================================

Purpose
-------
- The repository includes a small pickled "stub" model used by unit tests that expect a persisted model with a `.predict()` method.
- Backend tests (and some integration code) load model files from `backend/models_store/` by player name (e.g. `LeBron_James.pkl`).

Regenerating the stub model
----------------------------
To create or update the stub model used in tests run this from the project root (PowerShell):

```pwsh
.venv\Scripts\python -c "import joblib; from backend.services.stub_model import StubModel; import os; os.makedirs('backend/models_store', exist_ok=True); joblib.dump(StubModel(), 'backend/models_store/LeBron_James.pkl'); print('Wrote stub model')"
```

Why a stub exists
-----------------
- Some tests exercise ML prediction code paths expecting a persisted model object with a `.predict()` API. The stub replicates that minimal surface so tests can run deterministically without shipping a heavy ML artifact.

Where the NBA service wiring lives
---------------------------------
- `backend/services/nba_stats_client.py` contains low-level helpers that resolve player IDs and fetch recent game rows.
- `backend/services/nba_service.py` wraps those helpers and provides `get_player_summary()` and `build_external_context_for_projections()` which mirror the HTTP `/player_summary` endpoint shape.
- The service attempts to read/write Redis via `backend/services/cache.py`'s `get_redis()`; when Redis is unavailable, the service uses best-effort logic (e.g., falling back to `playercareerstats` or returning a `noGamesThisSeason` flag).

Testing notes
-------------
- Unit tests can monkeypatch `nba_service._redis_client` to simulate Redis present/absent or to inject erroring clients.
- Tests that need the persisted model should either create the model with the command above or use `monkeypatch` to inject a fake model loader.

Contact
-------
If you need a richer test model (real predict behavior), we can add a small sklearn pipeline to `requirements-dev.txt` and persist it under `backend/models_store/`.
