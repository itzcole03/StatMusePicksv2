 # Contributing: Alembic migration guidance

 When adding or modifying database migrations, follow these steps to avoid migration graph issues and platform-specific failures (e.g., SQLite in CI):

 1. Create a new Alembic revision using the project alembic environment:

 ```pwsh
 # from repo root
 python -m alembic revision -m "describe change" --autogenerate
 ```

 2. Edit the generated migration to ensure it is idempotent and safe across dialects.
    - Avoid issuing duplicate `CREATE INDEX` statements when a Column was declared with `index=True`.
    - Guard Timescale/Postgres-only SQL behind runtime checks or skip them when `op.get_bind().dialect.name != 'postgresql'`.

 3. Validate the migration locally against SQLite (fast) and a disposable Postgres if available:

 ```pwsh
 # Quick check (uses ephemeral sqlite DB)
 python backend/scripts/check_alembic_graph.py

 # If you have docker/postgres available, set DATABASE_URL to test against Postgres:
 $env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/test_migrations'
 python backend/scripts/check_alembic_graph.py --database-url $env:DATABASE_URL
 ```

 4. If Alembic produces multiple heads (divergent branches), merge them explicitly:

 ```pwsh
 # Create a merge revision
 python -m alembic merge -m "merge heads" <head1> <head2>
 ```

 5. Run the full backend test suite before opening a PR:

 ```pwsh
 & .venv\Scripts\Activate.ps1
 python -m pytest backend/tests -q
 ```

 6. Push the changes and open a PR. The CI includes an `alembic-validate` job that runs `check_alembic_graph.py` and will fail the PR if the migration graph is broken or migrations fail to apply to an ephemeral SQLite DB.

 If you're unsure about a migration change, please ask for a review and include the migration filename and a short rationale in the PR description.
