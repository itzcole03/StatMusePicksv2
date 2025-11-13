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
