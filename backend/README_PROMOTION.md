# Model Promotion Workflow

This file documents how to promote a saved player model to production.

1. Promote via CLI (local/dev):

```powershell
& .\.venv\Scripts\Activate.ps1
python backend/scripts/promote_model.py --player "LeBron James" --version <ver> --by alice --notes "promote to prod" --write-legacy
```

2. Promote via admin API (recommended for integrations):

- Set `ADMIN_API_KEY` in the environment for the backend process.
- Optionally set `MODEL_STORE_DIR` to override the default model store location.
- POST JSON to `/api/admin/promote` with header `X-ADMIN-KEY: <ADMIN_API_KEY>`.

Example body:

```json
{
  "player": "LeBron James",
  "version": "abc123",
  "promoted_by": "alice",
  "notes": "promote for production",
  "write_legacy": true
}
```

3. Audit logs

- An Alembic migration stub `backend/alembic/versions/0008_add_model_promotions.py` was added to create a `model_promotions` table for future DB-backed auditing. Run migrations in your deployment pipeline to apply it.

Notes:
- The admin endpoint uses a simple header `X-ADMIN-KEY` auth. For production, replace this with a real auth/authorization (OAuth2, API key management, or RBAC).
- Writing legacy `.pkl` files is optional and intended to provide compatibility for older consumers.
