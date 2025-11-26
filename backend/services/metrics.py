"""Prometheus metrics for backend services.

Keep this module minimal to avoid heavy imports in startup paths.
"""
from prometheus_client import Counter, Histogram

embedding_requests_total = Counter(
    'embedding_requests_total', 'Total number of embedding requests attempted'
)

embedding_success_total = Counter(
    'embedding_success_total', 'Total number of successful embedding requests'
)

embedding_latency_seconds = Histogram(
    'embedding_latency_seconds', 'Embedding generation latency in seconds'
)
llm_tool_calls_total = Counter('llm_tool_calls_total', 'Total number of LLM tool call attempts')
llm_tool_calls_failed = Counter('llm_tool_calls_failed', 'Total number of failed LLM tool calls')
llm_tool_calls_success = Counter('llm_tool_calls_success', 'Total number of successful LLM tool calls')

llm_schema_validation_failures = Counter('llm_schema_validation_failures_total', 'Total number of schema validation failures for LLM outputs')
llm_structured_accepted = Counter('llm_structured_accepted_total', 'Total number of structured LLM outputs accepted')
llm_structured_coerced = Counter('llm_structured_coerced_total', 'Total number of structured LLM outputs coerced into schema')
llm_structured_invalid = Counter('llm_structured_invalid_total', 'Total number of structured LLM outputs deemed invalid')
llm_tool_call_latency_seconds = Histogram('llm_tool_call_latency_seconds', 'LLM tool call latency in seconds')
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
