PR: Phase 2 signoff — smoke validation and roadmap checklist

Summary
- Performed local validation: backend tests, frontend tests, TypeScript typecheck, and ESLint fixes.
- Created Alembic merge revision to resolve multiple heads and made Alembic env robust to long revision ids.
- Added CI smoke workflow to run migrations, backend tests, typecheck, and frontend tests on PRs.

Files changed (high level)
- `backend/alembic/versions/0010_merge_0008s.py` (merge migration)
- `backend/alembic/env.py` (robust alembic_version handling)
- `.github/workflows/ci-smoke.yml` (CI smoke flow)
- multiple frontend files: ESLint autofix changes

Checklist (local validations completed)
- [x] Repo scan and code inspection
- [x] Backend pytest run (local)
- [x] Alembic migrations applied locally
- [x] TypeScript typecheck
- [x] Frontend Vitest run (local)
- [x] ESLint autofix applied
- [x] Pushed branch `phase2/signoff-Nov17-2025` and opened PR

Requested next steps
- Wait for CI checks on this PR to finish.
- If CI passes, request reviewers for formal signoff (please provide GitHub usernames).

Notes
- CI initially failed due to Alembic `Multiple head revisions` and a `StringDataRightTruncation` for `alembic_version.version_num`; fixes applied in this branch.
- CI now runs `alembic upgrade heads` and `env.py` will best-effort widen the `alembic_version.version_num` column where supported.

If you want me to request reviewers now, reply with the GitHub usernames to add.
