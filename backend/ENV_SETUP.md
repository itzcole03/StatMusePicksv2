# Backend Development Env — Postgres & Redis (dev)

This file documents recommended, repeatable steps to run the local dev database stack and set the `DATABASE_URL` environment variable used by the backend and Alembic. Follow the PowerShell examples if you are on Windows (developer environment is Windows by default in this workspace).

## Start dev services (docker-compose)

The repo includes `docker-compose.dev.yml` which launches Postgres 15 and Redis. From the repository root:

PowerShell (recommended):

```pwsh
# from repo root
docker compose -f docker-compose.dev.yml up -d
# wait a couple seconds for Postgres to initialize
Start-Sleep -Seconds 3
```

Bash/Linux:

```bash
docker compose -f docker-compose.dev.yml up -d
sleep 3
```

## Set `DATABASE_URL` for the current shell

Use the `postgresql+asyncpg` scheme in the backend to enable async SQLAlchemy (asyncpg driver).

PowerShell example (temporary for the session):

```pwsh
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
$env:REDIS_URL = 'redis://localhost:6379/0'
```

Bash example:

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
export REDIS_URL='redis://localhost:6379/0'
```

Notes:
- For scripts that need a synchronous DB URL (e.g., `ModelRegistry.save_model` uses a short-lived sync engine), the codebase converts the async URL to a sync form internally (removes `+asyncpg` or `+aiosqlite`).
- Use `sqlite+aiosqlite:///./dev.db` if you prefer not to run Postgres locally for a quick dev run.

## Apply Alembic migrations

Alembic reads `DATABASE_URL` from the environment via `backend/alembic/env.py` if set. To run migrations:

PowerShell:

```pwsh
# ensure the env var is set in the same shell
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
alembic -c backend/alembic.ini upgrade head
```

Bash:

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
alembic -c backend/alembic.ini upgrade head
```

If you see Alembic use `sqlite` during CI runs, ensure `DATABASE_URL` is set in the CI environment or the `alembic.ini`/`env.py` invocation passes `-x db_url=...`.

## Run the backend (FastAPI)

When running ad-hoc scripts that interact with the backend code (e.g., scripts that persist models), avoid running the server with the reloader in the same shell as your script. The reloader can restart and interfere with short-lived scripts.

PowerShell (dev server, reload enabled):

```pwsh
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
uvicorn backend.main:app --reload --port 8000
```

Run scripts in another shell without `--reload` conflicts (or disable reload for long-running development servers):

```pwsh
$env:PYTHONPATH='.'
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
python backend/scripts/persist_toy_model.py
```

## Quick troubleshooting

- If imports fail when running scripts, set `PYTHONPATH='.'` or run with `python -m backend.scripts.persist_toy_model` from the repo root.
- If Alembic migrations seem to use SQLite even though `DATABASE_URL` is set, check for literal placeholders like `${DATABASE_URL}` in your shell/CI and verify `env.py` picks up `os.environ['DATABASE_URL']`.
- If the FastAPI startup `@app.on_event('startup')` preloading behaves unexpectedly, consider running tests with `TestClient(app)` which triggers startup events in-process.

## Best practices

- Keep `DATABASE_URL` out of committed files. Use `.env` files with a secret manager or CI environment variables for production.
- Use `postgresql+asyncpg://` for async app runtime, and rely on the repo code to convert to a sync URL for short-lived admin interactions when necessary.
- Prefer running migrations in CI or deploy pipelines rather than ad-hoc on production servers.


