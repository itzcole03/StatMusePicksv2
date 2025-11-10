# StatMuse Integration

Overview

This project includes a small server-side proxy that scrapes StatMuse "ask" pages and returns a normalized JSON shape for the frontend to use when building LLM analysis prompts. Because StatMuse does not provide a public API, scraping is done server-side to avoid CORS and to centralize caching/rate-limiting.

Files of interest

- `statmuse-proxy/index.js` — Express proxy with polite rate-limiting (Bottleneck), TTL caching (`node-cache`) and simple HTML extraction (Cheerio).
- `src/services/statmuseService.ts` — Client-side helper that calls the proxy (defaults to `http://localhost:3001/statmuse` when settings are empty).
- `src/services/aiService.ts` — Async prompt builder `buildAnalysisPromptAsync(...)` that appends external data from StatMuse when available and returns metadata `{ prompt, externalUsed, contexts }`.
- `src/components/AnalysisSection.tsx` — Uses the async prompt builder and shows when external data was appended. The UI also includes a panel listing which players had external data and links to the proxy sources.

Running locally

1. Install dependencies (root workspace will include the `statmuse-proxy` workspace):

```pwsh
npm install
```

2. Start dev server and proxy together (cross-platform):

```pwsh
npm run dev:with-proxy
```

This runs both the Vite dev server (default port `3000`) and the proxy. Alternatively start the proxy separately:

```pwsh
npm run proxy:install
npm run proxy:start
```

Usage details

- The proxy endpoint accepts the following query parameters:
  - `player` (required): player name
  - `stat` (optional): stat keyword (e.g., `points`, `rebounds`)
  - `league` (optional): `nba` by default
  - `limit` (optional): number of recent games to query

Example:

```pwsh
curl "http://localhost:3001/statmuse?player=LeBron%20James&stat=points&league=nba&limit=8"
```

- The front-end will call `buildAnalysisPromptAsync(...)` which will call the configured `statmuseEndpoint` (or default proxy) and append any returned `recent`, `season`, and `notes` text to the LLM prompt. The UI shows when external data was included and provides links to the extraction sources.
 - The front-end will call `buildAnalysisPromptAsync(...)` which will call the configured `nbaEndpoint` (preferred) or `statmuseEndpoint` (fallback) and append any returned `recent`, `season`, `recentGames` and `seasonAvg` data to the LLM prompt. The UI shows when external data was included and provides links to the extraction sources.
 - You can protect proxies by setting API keys: set `NBA_PROXY_API_KEY` for the Python NBA proxy and `PROXY_API_KEY` for the Node StatMuse proxy. Provide keys in the app Settings to use authenticated calls.

Caveats, ethics, and legal

- Scraping any website can violate its Terms of Service. Verify legal permissions and respect `robots.txt`. Consider reaching out to StatMuse for access or use licensed data providers.
- Be polite: the proxy includes rate-limiting and caching, but if you plan to operate commercially or at scale, add persistent caching (Redis), stricter throttling, backoff, and monitoring.

Production recommendations

- Replace the in-memory cache (`node-cache`) with Redis or another persistent cache.
- Add logging, metrics, and request queuing.
- Implement per-target throttling and IP rotation only after you're certain you comply with the target site's policies.
- Consider building a formal data agreement or licensed data ingestion to avoid scraping.

If you want, I can:
- Add Redis support to the proxy and configuration for Redis URL, TTL, and cache keys.
- Add a UI panel to `AnalysisSection` that displays full fetched summaries and source links (already implemented in basic form).
- Add end-to-end tests to ensure the proxy extracts expected fields for a set of sample players.
