import asyncio


def test_db_health_sqlite(tmp_path, monkeypatch):
    # Use a temporary sqlite file for the test
    db_file = tmp_path / "test_db_health.db"
    sqlite_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", sqlite_url)

    # Ensure backend modules use the test DB URL
    # Add repo root to sys.path so imports work in test runner
    import pathlib
    import sys

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    from backend import db as backend_db

    # create engine/session and tables
    backend_db._ensure_engine_and_session()
    asyncio.run(backend_db.init_db())

    # import app after env var set
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        r = client.get("/api/db_health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("db", {}).get("ok") is True
