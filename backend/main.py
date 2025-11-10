"""Backend entrypoint wrapper.

This file exposes `app` for tools that expect `backend.main:app` and
provides minimal startup/shutdown hooks.
"""
from fastapi import FastAPI

try:
    # import the app defined in fastapi_nba.py
    from .fastapi_nba import app as nba_app
except Exception:
    # fallback: create an empty FastAPI app so the module always imports
    nba_app = FastAPI(title="NBA Data Backend (fallback)")

app: FastAPI = nba_app


@app.on_event("startup")
async def _startup():
    # placeholder for startup tasks (DB connections, caches)
    return None


@app.on_event("shutdown")
async def _shutdown():
    # placeholder for graceful shutdown
    return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
