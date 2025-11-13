"""Example FastAPI app showing how to schedule `run_daily_sync_async()`
from an existing asyncio event loop (background task).

This is a minimal example: adapt logging, error handling and scheduling
policy to your ops requirements.
"""
import asyncio
import logging
from datetime import date

from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.services import data_ingestion_service as dis

logger = logging.getLogger(__name__)

app = FastAPI()

# Event used to signal the periodic task to stop during shutdown
_stop_event: asyncio.Event | None = None
# Task handle for the periodic ingest loop
_ingest_task: asyncio.Task | None = None


async def _periodic_ingest(interval_seconds: int = 24 * 60 * 60):
    """Periodic loop that calls the async ingestion entrypoint.

    Behavior:
    - Runs `run_daily_sync_async()` once, then sleeps for `interval_seconds`.
    - Uses `_stop_event` to exit quickly on shutdown.
    """
    global _stop_event
    while not _stop_event.is_set():
        try:
            result = await dis.run_daily_sync_async(when=date.today())
            logger.info("run_daily_sync_async result: %s", result)
        except Exception:
            logger.exception("Periodic ingest failed")

        try:
            # wait for either stop signal or timeout
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Lifespan handler to start and stop the periodic ingest background task.

    This replaces the deprecated `@app.on_event` usage and ensures the
    periodic task is signalled to stop cleanly on shutdown.
    """
    global _stop_event, _ingest_task
    # startup
    _stop_event = asyncio.Event()
    _ingest_task = asyncio.create_task(_periodic_ingest())
    logger.info("Started periodic ingest task")

    yield

    # shutdown
    if _stop_event is not None:
        _stop_event.set()
    if _ingest_task is not None:
        try:
            await _ingest_task
        except Exception:
            logger.exception("Error while awaiting ingest task shutdown")


# Attach lifespan to app
app.router.lifespan_context = _lifespan


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
