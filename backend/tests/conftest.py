import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip tests marked `integration` unless RUN_LIVE_NBA_TESTS=1 is set.

    This prevents CI/dev runs from hitting live upstream services unless
    explicitly enabled.
    """
    run_live = os.environ.get("RUN_LIVE_NBA_TESTS", "0") == "1"
    if run_live:
        return

    skip_integration = pytest.mark.skip(reason="skipped integration test (set RUN_LIVE_NBA_TESTS=1 to enable)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
import warnings

# Suppress known non-blocking deprecation/warning noise during test runs.
# These are tracked follow-up items in the roadmap and will be addressed
# in dedicated migrations (Pydantic v2 ConfigDict migration, sklearn artifact
# compatibility, and SQLAlchemy timezone-aware timestamps).

# Pydantic class-config deprecation (v2 migration warning)
warnings.filterwarnings(
    "ignore",
    message=r"Support for class-based `config` is deprecated",
    category=DeprecationWarning,
)

# Pydantic v2 config key rename notices
warnings.filterwarnings(
    "ignore",
    message=r"Valid config keys have changed in V2",
    category=UserWarning,
)

# FastAPI `on_event` decorator deprecation (some example files may still
# reference it transiently in CI runs; core modules have been migrated).
warnings.filterwarnings(
    "ignore",
    message=r"on_event is deprecated, use lifespan event handlers instead",
    category=DeprecationWarning,
)

# SQLAlchemy UTC deprecation warning about datetime.utcnow()
warnings.filterwarnings(
    "ignore",
    message=r"datetime.datetime.utcnow\(\) is deprecated",
    category=DeprecationWarning,
)

# sklearn InconsistentVersionWarning when unpickling test artifacts built
# with a slightly different sklearn version. Prefer re-saving artifacts
# with the current environment as a long-term fix.
try:
    from sklearn.exceptions import InconsistentVersionWarning

    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except Exception:
    # sklearn may not be installed in some environments where backend tests
    # are not executed; ignore if unavailable.
    pass


# Ensure a legacy toy model exists for tests that expect `backend/models_store/LeBron_James.pkl`.
def _ensure_legacy_lebron_model():
    import pathlib
    import joblib
    import os
    try:
        from sklearn.dummy import DummyRegressor
        import numpy as _np
    except Exception:
        return

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    MODELS_DIR = ROOT / "models_store"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_PATH = MODELS_DIR / "LeBron_James.pkl"

    if not MODEL_PATH.exists():
        dummy = DummyRegressor(strategy="constant", constant=42.0)
        # fit on trivial data so sklearn attributes like `n_features_in_` exist
        dummy.fit(_np.zeros((2, 1)), _np.array([42.0, 42.0]))
        joblib.dump(dummy, MODEL_PATH)

    os.environ.setdefault("MODEL_STORE_DIR", str(MODELS_DIR))


_ensure_legacy_lebron_model()
