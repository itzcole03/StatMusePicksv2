"""Prometheus metrics helper with multiprocess support.

Provides `generate_latest` and `CONTENT_TYPE_LATEST` compatible exports used
by `backend.main` to expose /metrics safely in single- and multi-process
deployments.
"""
import os

try:
    from prometheus_client import generate_latest as _gen_default, CONTENT_TYPE_LATEST
    from prometheus_client import CollectorRegistry
    from prometheus_client import multiprocess as _multiprocess
except Exception:
    _gen_default = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    CollectorRegistry = None
    _multiprocess = None


def generate_latest():
    """Return latest metrics payload using multiprocess registry when
    `PROMETHEUS_MULTIPROC_DIR` is set (common for Gunicorn/Uvicorn workers).
    Falls back to prometheus_client.generate_latest when multiprocess is
    not configured or library is unavailable.
    """
    if _gen_default is None:
        raise RuntimeError("prometheus_client not available")

    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if mp_dir and CollectorRegistry is not None and _multiprocess is not None:
        # Use a separate CollectorRegistry and multiprocess mode to merge
        # metrics files produced by multiple worker processes.
        registry = CollectorRegistry()
        _multiprocess.MultiProcessCollector(registry)
        return _gen_default(registry)

    # Single-process default
    return _gen_default()
