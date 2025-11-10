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
