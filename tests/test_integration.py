import importlib
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_migrations_train_and_endpoints(tmp_path):
    """Run migrations, train the synthetic model, and verify model endpoints."""
    repo_root = Path.cwd()

    # Use an isolated SQLite file inside the pytest tmp path
    db_file = tmp_path / "test_dev.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"

    # Run alembic migrations
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "heads",
        ],
        check=True,
        env=env,
        cwd=str(repo_root),
    )

    # Run the synthetic training script to produce a model artifact
    subprocess.run(
        [sys.executable, "backend/scripts/train_example.py"],
        check=True,
        env=env,
        cwd=str(repo_root),
    )

    # Import the FastAPI app and use TestClient to hit endpoints
    app_module = importlib.import_module("backend.fastapi_nba")
    app = getattr(app_module, "app")
    client = TestClient(app)

    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert any("synthetic_player" in m for m in data["models"]) or any(
        m.endswith("synthetic_player.pkl") for m in data["models"]
    )

    r2 = client.post("/api/models/load?player=synthetic_player")
    assert r2.status_code == 200
    assert r2.json().get("loaded") is True
