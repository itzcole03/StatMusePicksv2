Purpose
-------
Provide concise, repository-specific guidance so an AI coding agent (Copilot-style) becomes productive immediately.

Quick Big Picture
-----------------
- Frontend: Vite + React + TypeScript in `src/`. Large lists are virtualized (`react-window`) and styles use Tailwind.
- Heavy parsing lives in a web worker: `src/workers/parser.worker.ts` — large JSON must NOT be parsed on the main thread.
- Persistence: IndexedDB is the client store. Key service: `src/services/indexedDBService.ts` (call `initDB()` before DB ops).
- Numeric context / NBA data: `src/services/nbaService.ts` + dev proxy at `backend/fastapi_nba.py` for local numeric context fetching.
- AI layers: `src/services/aiService.ts` (LLM integration) and `src/services/aiService.v2.ts` (statistical checks). UI compares both in `src/components/AnalysisSection.tsx`.
- Backend: small FastAPI dev proxy and Python services in `backend/` used for training, ingestion, and numeric lookups.

Key Files / Where To Look
-------------------------
- Parser & chunking: `src/workers/parser.worker.ts`
- IndexedDB API + migrations: `src/services/indexedDBService.ts`
- NBA numeric context + TTL logic: `src/services/nbaService.ts`
- LLM prompts and streaming: `src/services/aiService.ts`, `src/services/aiService.v2.ts`
- Training / datasets / models: `backend/services/training_data_service.py`, `backend/services/model_registry.py`, `backend/services/training_pipeline.py`
- Backtesting & evaluation: `backend/evaluation/backtesting.py`, `backend/evaluation/calibration_metrics.py`
- Dev backend proxy: `backend/fastapi_nba.py`
- Useful scripts: `scripts/backtest_run.py`, `scripts/train_orchestrator.py`, `scripts/datasets.py`

Developer Workflows / Useful Commands
------------------------------------
- Frontend dev: `npm run dev` (Vite). If port conflicts: `npm run dev -- --port 5173`.
- Backend dev proxy (dev-only): `npm run backend:dev` (starts uvicorn on `3002` in dev setups).
- Tests: frontend uses `npx vitest --run` or `npm test`; backend Python tests: `python -m pytest backend/tests/`.
- Typecheck: `npm run typecheck` for the TS project.
- Run smoke training/backtest locally: `python scripts/backtest_run.py -o backend/models_store/backtest_reports/smoke.json`.

Project-Specific Conventions
----------------------------
- Worker import pattern (Vite):
	`new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' })` — keep parsing off main thread.
- IndexedDB stores: `players`, `player_map`, `projections`. Use `saveBatch(items)` and `rebuildPlayersIndex()` instead of scanning whole tables.
- Numeric context shape: attach `nbaContext` to projection objects with `fetchedAt` (UTC) and optionally `noGamesThisSeason` when appropriate.
- UI live-update pattern: after DB writes, dispatch `window.dispatchEvent(new CustomEvent('db-updated', { detail }))` so components refresh.
- Virtualized lists: `src/components/ProjectionsTable.tsx` uses `outerElementType` and `forwardRef` — preserve that pattern when editing.

Testing Gotchas & Notes
----------------------
- Vitest runs in `jsdom`. Guard browser-only APIs (eg. `scrollIntoView`) in tests or mock them.
- Many backend tests assume `initDB()` was called; call it in test setup if you exercise IndexedDB helpers.
- Parquet export tests tolerate missing parquet engines (pyarrow/fastparquet); be explicit in CI if you need that path tested.

Integration Points & External Dependencies
-----------------------------------------
- NBA numeric context backend (dev): `backend/fastapi_nba.py` — used by `nbaService.ts` in dev.
- Optional dependencies: `xgboost`, `pyarrow`/`fastparquet`. Wrappers check for missing packages and fall back gracefully.
- Redis is present in some dev flows as a cache; services provide in-process fallback so tests run without Redis.

When Editing / Adding Code
-------------------------
- Keep heavy parsing in `src/workers/parser.worker.ts`. Preserve chunking and `saveBatch()` semantics.
- For DB schema changes bump `DB_VERSION` in `src/services/indexedDBService.ts` and add migrations in `initDB()`.
- When changing training/data export paths, update dataset manifest generation and `scripts/datasets.py` to preserve versioning.

Examples & Patterns (copyable)
------------------------------
- Worker import (Vite):
	`new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' })`
- Emit DB update after persistence:
	`window.dispatchEvent(new CustomEvent('db-updated', { detail: { store: 'projections' } }))`

CI / Next Steps
---------------
- A minimal Phase 2 smoke workflow exists at `.github/workflows/phase2-train-smoke.yml` — push branch/PR to run it.
- To validate parquet export in CI, add a job that installs `pyarrow`.

Questions / Feedback
--------------------
If any key integration or workflow is missing or unclear, tell me which area to expand (backend training, worker parsing, DB migrations, or CI). I can iterate on this file.

