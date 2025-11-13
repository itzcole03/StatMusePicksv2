## Purpose

Brief, high-value guidance so an AI coding agent becomes productive immediately in this repository.
Focus on exact files, commands, and patterns unique to this project — not generic advice.

## Big picture (what this app is and why it’s structured this way)
## Big picture (what to know quickly)
- Frontend: Vite + React + TypeScript in `src/`. UI is virtualized (`react-window`) and styled with Tailwind.
- Data ingest: Large PrizePicks JSONs are parsed inside `src/workers/parser.worker.ts` and written in chunks to IndexedDB.
- Persistence: `src/services/indexedDBService.ts` is the ground truth. Call `initDB()` before DB operations in tests/dev.
- External numeric context: `src/services/nbaService.ts` builds and caches contexts; use `buildExternalContextForProjections()` + `saveNbaContexts()` to persist.
- AI layers: `src/services/aiService.ts` (LLM prompts/streaming) and `src/services/aiService.v2.ts` (statistical checks). `AnalysisSection.tsx` compares outputs and applies deterministic safety rules.
- Backend (dev-only): `backend/fastapi_nba.py` wraps `nba_api` for local numeric context during dev.

## Key files to inspect first
- `src/workers/parser.worker.ts` — parser, chunking, and main-thread message protocol. Keep heavy parsing in the worker.
- `src/services/indexedDBService.ts` — DB init, migrations, `saveBatch`, `rebuildPlayersIndex()`, `getPlayersWithCounts()`.
- `src/services/nbaService.ts` — TTL/cache strategy, backend proxy usage, `buildExternalContextForProjections()`.
- `src/services/aiService.ts` & `src/services/aiService.v2.ts` — LLM prompt builders, streaming parser, and deterministic heuristics.
- `src/components/AnalysisSection.tsx` — where LLM + v2 are compared and items can be flagged/nullified.
- `src/components/ProjectionsTable.tsx` — virtualized list pattern; `outerElementType` must be a `forwardRef` wrapper.

## Project-specific conventions & patterns
- Worker import (Vite): `new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' })` — do not parse large JSON on main thread.
- IndexedDB stores: `players`, `player_map`, `projections`. Use `saveBatch(items)` and `rebuildPlayersIndex()`; avoid full-table synchronous scans.
- Numeric context: attach as `nbaContext` with `fetchedAt`. When no recent games exist backend sets `noGamesThisSeason`.
- Broadcast DB changes: emit `window.dispatchEvent(new CustomEvent('db-updated',{detail}))` after persistence updates so UI can refresh.
- Deterministic safety: `aiService.v2` provides calibrated confidences; `AnalysisSection` applies thresholds to null/flag LLM outputs.

## Common developer workflows & commands
- Start frontend: `npm run dev` (Vite). If port conflicts, use `npm run dev -- --port 5173`.
- Start backend proxy (dev): `npm run backend:dev` (uvicorn on `3002`) — frontend `nbaService` expects this in dev.
- Run tests: `npx vitest --run` or `npm test` (uses `vitest.setup.ts`, `jsdom`).
- Typecheck: `npm run typecheck`.
- ESLint quick fix for src: 
```pwsh
npx eslint "src/**/*.{ts,tsx}" --ext .ts,.tsx --fix
```

## Testing & gotchas
- Vitest runs in `jsdom`. Guard browser-only APIs (e.g., `scrollIntoView`) and mock IndexedDB when needed.
- Always call `initDB()` before DB ops in tests or dev harnesses. For schema changes bump `DB_VERSION` in `src/services/indexedDBService.ts` and add migrations in `initDB()`.
- Worker tests: avoid importing worker code directly in the main thread; test worker protocols by mocking `postMessage`/`onmessage` patterns.

## Integration points & external deps
- Local LLM endpoints: `src/services/aiService.ts` reads `settings.llmEndpoint` & `llmModel`. Dev scripts in `scripts/` help build prompts and probe endpoints.
- NBA numeric context backend: `backend/fastapi_nba.py` (dev-only) or `nba-proxy/app.py` for alternative proxying.
- CI & migrations: Alembic migrations live in `backend/alembic/versions/`. Migrations must be dialect-aware; some CI jobs run SQLite, others Postgres/Timescale.
- Timescale rollout helpers and benchmarks: `backend/scripts/run_timescale_benchmark.py` and `backend/TIMESCALE_ROLLOUT.md` (if present) — review before applying hypertable migrations.

## Small examples & snippets
- Debounced player search: `getPlayersWithCounts(league || undefined, stat || undefined, query || undefined)` in `src/components/Filters.tsx`.
- Pre-warm contexts before analysis: `const contexts = await buildExternalContextForProjections(items, settings); await saveNbaContexts(contexts);` (see `src/App.tsx`).

## When editing / making fixes (repo-specific)
- Keep heavy parsing in `src/workers/parser.worker.ts`. Preserve chunking and `saveBatch()` semantics to avoid UI freezes.
- When touching `indexedDBService.ts`:
	- Call `initDB()` in tests/dev harnesses.
	- Bump `DB_VERSION` for schema changes and add upgrade logic.
- Alembic migrations (backend): edit files in `backend/alembic/versions/`. Use dialect guards for Postgres-only/Timescale SQL and avoid running Timescale-specific SQL on SQLite CI jobs.
- CI: upload Alembic logs and JUnit XML (`logs/alembic.log`, `reports/junit.xml`) — agents should parse these to diagnose migration/test failures.

If you want a role-focused variant (UI-only / ingest-only / backend-only), tell me which and I'll produce a trimmed variant.
## Purpose

Short, focused instructions so an AI coding agent becomes productive immediately in this repository.

Keep these instructions precise — reference the exact files, conventions and commands the agent will need.

## Big picture

- Frontend: Vite + React + TypeScript single-page app in `src/`.
- Data ingest: large PrizePicks JSON files are parsed in `src/workers/parser.worker.ts` and saved in chunks to IndexedDB.
- Persistence & query layer: `src/services/indexedDBService.ts` — call `initDB()` first. Key helpers: `saveBatch(items)`, `rebuildPlayersIndex()`, `queryProjections()`, `getProjectionsByIds()`, `saveNbaContexts(contexts)`.
- External numeric context: `src/services/nbaService.ts` builds and caches NBA context for projections and delegates to the local FastAPI backend when needed.
- AI layers: `src/services/aiService.ts` (LLM integration) and `src/services/aiService.v2.ts` (statistical helpers and deterministic checks). The UI uses both to present & sometimes override LLM output.
- Backend (dev-only): `backend/fastapi_nba.py` wraps `nba_api` and is started with `npm run backend:dev` (uvicorn on port 3002).

## Important project-specific conventions

- Worker import for Vite: use `new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' })`.
- IndexedDB stores include `players` and `player_map` for fast autocomplete — avoid full synchronous scans on the main thread.
- External numeric context is stored on projection objects as `nbaContext` and must include `fetchedAt` and optionally `noGamesThisSeason` when applicable.
- When building external contexts for analysis use `buildExternalContextForProjections()` — this applies TTL and caching behavior.
- UI components listen to DB updates via: `window.dispatchEvent(new CustomEvent('db-updated', { detail }))`.
- Virtualized lists: `src/components/ProjectionsTable.tsx` uses `react-window` and requires `outerElementType` to support `forwardRef`.

## Critical files to inspect (quick map)

- Parser worker: `src/workers/parser.worker.ts` (chunking + main-thread message protocol).
- IndexedDB service: `src/services/indexedDBService.ts` (init, migrations, `saveNbaContexts`).
- NBA context client: `src/services/nbaService.ts` (TTL + backend proxy usage).
- LLM glue: `src/services/aiService.ts` (prompt builder, streaming LLM wrapper) and `src/services/aiService.v2.ts` (statistical prediction helpers used for deterministic flagging).
- Analysis UI: `src/components/AnalysisSection.tsx` (where LLM + v2 are compared and flagged).
- Import UI: `src/components/DataLoader.tsx` (uses the worker and writes to DB).
- Table UI: `src/components/ProjectionsTable.tsx` (virtualization + badges).
- Backend dev proxy: `backend/fastapi_nba.py` (local-only wrapper around `nba_api`).
- Dev scripts: `scripts/fetch_and_build_prompt.cjs`, `scripts/run_local_backend_and_prompt.ps1`, `scripts/sample_projections.json`.

## Developer workflows & commands

- Start frontend dev server: `npm run dev` (Vite). If port 3000 is blocked try: `npm run dev -- --port 5173`.
- Start backend dev proxy: `npm run backend:dev` (uvicorn on port `3002` by default; frontend `nbaService` expects local proxy during dev).
- Run tests: `npx vitest --run` or `npm test` (Vitest). The project uses `jsdom` environment and a setup file `vitest.setup.ts` to register `@testing-library/jest-dom` matchers.
- Typecheck: `npm run typecheck` (tsc with the app tsconfig).
- Build: `npm run build`.

Testing gotchas (learned from repo):

- Ensure dev dependencies installed: `@testing-library/react`, `@testing-library/jest-dom`, `vitest`, and `jsdom`.
- Vitest config uses `globals: true` and `setupFiles` — the setup file registers jest-dom matchers; tests should not import `@testing-library/jest-dom` directly.
- Components that call browser APIs in useEffect may need guards for jsdom (e.g., `scrollIntoView` may be undefined) and React must be in scope for JSX in tests.

Patterns to preserve

- Large JSON parsing must remain in the worker and saved in chunks to avoid blocking the main thread.
- Numeric external context must be factual: backend supplies `recentGames` and `seasonAvg` or `noGamesThisSeason` — do not fabricate numeric fallbacks in UI.
- Deterministic safety: `aiService.v2` produces calibrated confidences and `AnalysisSection` nulls LLM recommendations and flags items when v2 strongly disagrees (see `v2.calibratedConfidence` usage).

Integration points & external dependencies

- Local backend proxy: `backend/fastapi_nba.py` — consult when you need authoritative NBA contexts.
- Optional `nba-proxy/app.py` (another proxy) — inspect README if you plan to run alternate proxies.
- IndexedDB (browser) is the persistent store in normal runs — migrations are handled in `initDB()` in `indexedDBService.ts`.

How to add new features safely

- When adding UI features that surface numeric context, prefer reading from `indexedDBService` helpers, and dispatch `db-updated` so other UI components refresh.
- If touching import/parse flows, keep the worker chunking pattern and use `saveBatch(items)` to persist progressively.

If something is unclear or you need deeper examples (prompts, backend API, or test fixtures), ask for which area to expand.

--
Short and focused — update me if you want additional examples or a longer agent-run checklist.
**Purpose**: Short, project-specific guidance to make AI coding agents productive here.

**Big picture**

- Frontend: Vite + React + TypeScript single-page app. Projections are parsed (worker), normalized, and stored in IndexedDB for fast client-side queries and autocomplete. UI uses Tailwind + `react-window` for large lists.
- Backend (optional/local): A small FastAPI service lives in `backend/fastapi_nba.py` (started in dev with `npm run backend:dev`) and wraps `nba_api` to provide authoritative player contexts (`/player_summary`). The frontend calls this for numeric context.

**Data flow & boundaries**

- Import: `src/workers/parser.worker.ts` parses PrizePicks JSON in chunks and posts messages to the main thread.
- Persist/index: `src/services/indexedDBService.ts` (call `initDB()` first). Key helpers: `saveBatch(items)`, `rebuildPlayersIndex()`, `queryProjections()`, `getProjectionsByIds()`, `saveNbaContexts(contexts)`.
- NBA context: `src/services/nbaService.ts` is a thin client that reads cached `nbaContext` from IndexedDB and calls the backend proxy when stale. Use `buildExternalContextForProjections()` to fetch contexts (it applies a TTL).
- Presentation: Components in `src/components/*` consume DB helpers and listen for `window.dispatchEvent(new CustomEvent('db-updated', { detail }))` to refresh UI.

**Key design decisions to preserve**

- Large JSON must be parsed in a worker and saved in chunks to avoid UI blocking — keep that pattern when touching import code.
- IndexedDB includes `players` and `player_map` stores for fast filtered/autocomplete queries; avoid full synchronous scans on the main thread.
- Numeric external context must be factual: backend supplies real recentGames/seasonAvg or an explicit `noGamesThisSeason` flag. Do not fabricate numeric fallbacks.

**Project-specific conventions & patterns**

- Worker import: `new Worker(new URL('../workers/parser.worker.ts', import.meta.url), { type: 'module' })` for Vite compatibility.
- Virtualized lists require an `outerElementType` that supports `forwardRef` (see `src/components/ProjectionsTable.tsx`).
- Cached NBA contexts are stored on the projection as `nbaContext` (include `fetchedAt`) and persisted via `saveNbaContexts()`.
- Analysis flow: when analyzing selected projections, the app pre-warms contexts (`buildExternalContextForProjections`) and persists them before building LLM prompts (see `src/App.tsx` and `src/services/aiService.ts`).

**Important files to inspect**

- `src/workers/parser.worker.ts` — parser and chunking logic.
- `src/services/indexedDBService.ts` — DB API, migrations, `saveNbaContexts` and query helpers.
- `src/services/nbaService.ts` — client-side cache + backend fetch logic (TTL behavior).
- `backend/fastapi_nba.py` — FastAPI wrapper around `nba_api` (dev-only, optional).
- `src/services/aiService.ts` — prompt builder and LLM integration; appends external numeric context when available.
- `src/components/DataLoader.tsx` — importer UI; dispatches `db-updated` after import.
- `src/components/ProjectionsTable.tsx` — grouping, virtualization, and badge UI (shows `No recent` when `nbaContext.noGamesThisSeason`).
- `scripts/fetch_and_build_prompt.cjs` and `scripts/run_local_backend_and_prompt.ps1` — dev tooling for E2E smoke tests.

**Dev & debug commands**

- Frontend: `npm run dev` (port 3000) or `npm run dev -- --port 5173` if port blocked.
- Backend (dev): `npm run backend:dev` (starts uvicorn on port 3002).
- Typecheck: `npm run typecheck`.
- Build: `npm run build`.

**Runtime notes & gotchas**

- HMR works but schema/IndexedDB migrations may require clearing browser DB or bumping `DB_VERSION` in `src/services/indexedDBService.ts`.
- Some browsers block certain local ports (e.g., 3000); prefer 5173 if you see ERR_UNSAFE_PORT.
- When changing indexing or DB stores, ensure `upgrade()` in `initDB()` safely migrates and backfills `player_map` if needed.

**Examples / quick snippets**

- Query suggestions with counts: `await getPlayersWithCounts(league || undefined, stat || undefined, query || undefined)`
- Pre-warm contexts for analysis: see `src/App.tsx` — it calls `buildExternalContextForProjections(items, settings)` then `saveNbaContexts(contexts)`.

If you want this tuned for a narrower agent role (frontend-only, backend-only, or data-indexing-only), say which focus and I will produce a trimmed variant.
