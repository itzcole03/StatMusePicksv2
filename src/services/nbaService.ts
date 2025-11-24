import { ParsedProjection, Settings } from "../types";
import { getProjectionsByIds } from "./indexedDBService";

/*
  NOTE: The frontend should not run `nba_api` directly — `nba_api` is a Python
  library and must be executed server-side. This module intentionally provides
  lightweight stubs and guidance for how to integrate `nba_api` from a backend.

  Recommended options to obtain structured NBA data for the frontend:
  1) Create a small server (FastAPI or Flask) that imports `nba_api` and
     exposes minimal endpoints (e.g., `/player_summary`). Host it separately
     from the frontend (local dev or production). The frontend calls that server.
  2) Use a serverless function (AWS Lambda, Cloud Run) that bundles `nba_api`
     and responds to on-demand requests. Keep rate-limiting and caching in mind.
  3) If you cannot run Python, use a commercial sports data API (Sportradar,
     StatsPerform, etc.) with an official HTTP API and wire it directly.

  Example server-side (FastAPI) minimal handler (Python):

  ```py
  # fastapi_nba_example.py
  from fastapi import FastAPI, HTTPException
  from nba_api.stats.static import players
  from nba_api.stats.endpoints import playergamelog
  from pydantic import BaseModel

  app = FastAPI()

  class PlayerSummary(BaseModel):
      player: str
      stat: str
      recentGames: list
      seasonAvg: float | None = None

  @app.get('/player_summary')
  def player_summary(player: str, stat: str = 'points', limit: int = 8):
      matches = players.find_players_by_full_name(player)
      if not matches:
          raise HTTPException(status_code=404, detail='player not found')
      pid = matches[0]['id']
      gl = playergamelog.PlayerGameLog(player_id=pid)
      df = gl.get_data_frames()[0]
      recent = df.head(limit).to_dict(orient='records')
      # transform into desired JSON structure
      return PlayerSummary(player=player, stat=stat, recentGames=recent)
  ```

  Frontend integration pattern (recommended): keep `src/services/nbaService.ts`
  as a thin client that calls your backend endpoints. That backend runs `nba_api`.

  The functions below are stubs to avoid runtime fetches when no backend is
  provided. Update them to call your authoritative service once deployed.
*/

export interface NBAPlayerContext {
  player: string;
  stat: string;
  recent?: string | null;
  recentGames?: Array<any> | null;
  season?: string | null;
  seasonAvg?: number | null;
  notes?: string | null;
  // Opponent and matchup metrics
  opponent?: {
    name?: string | null;
    defensiveRating?: number | null;
    pace?: number | null;
  } | null;
  // Projected minutes for the player in the upcoming game
  projectedMinutes?: number | null;
  // Additional optional metadata returned by the backend
  noGamesThisSeason?: boolean;
  note?: string | null;
  lastSeason?: string | null;
  lastGameDate?: string | null;
  // ISO timestamp when this context was fetched from the backend
  fetchedAt?: string | null;
  recentSource?: string | null;
  seasonSource?: string | null;
  // Rolling averages keyed by window (e.g. sma_5, ema_10)
  rollingAverages?: Record<string, number | null> | null;
  // Opponent-specific info and matchup summaries
  opponentInfo?: Record<string, any> | null;
  // Multi-season aggregated contexts (training-scoped responses)
  seasonsConsidered?: string[] | null;
  seasonStatsMulti?: Record<string, Record<string, number>> | null;
  advancedStatsMulti?: { per_season?: Record<string, Record<string, number>>; aggregated?: Record<string, number> } | null;
  teamId?: number | null;
  teamStatsMulti?: Record<string, Record<string, number>> | null;
  teamAdvancedMulti?: { per_season?: Record<string, Record<string, number>>; aggregated?: Record<string, number> } | null;
}

// Module-level normalizer so both single and batch fetchers can reuse the logic.
function normalizeBackendResponse(json: any, playerName?: string, statType?: string): NBAPlayerContext | null {
  if (!json) return null;
  const recentGames = Array.isArray(json.recentGames)
    ? json.recentGames.map((g: any) => ({
        date: g.date || g.gameDate || null,
        statValue: g.statValue != null ? Number(g.statValue) : null,
      }))
    : null;
  // rollingAverages may be returned as object of numeric strings
  const rollingAverages = json.rollingAverages && typeof json.rollingAverages === 'object'
    ? Object.fromEntries(
        Object.entries(json.rollingAverages).map(([k, v]) => [k, v != null ? Number(v) : null])
      )
    : null;
  const seasonAvg = json.seasonAvg != null ? Number(json.seasonAvg) : null;
  const recent = typeof json.recent === 'string' ? json.recent : null;
  const notes = json.notes || null;
  const noGamesThisSeason = !!json.noGamesThisSeason;
  const recentSource = json.recentSource || null;
  const seasonSource = json.seasonSource || null;
  const opponent = json.opponent
    ? {
        name: json.opponent.name || null,
        defensiveRating: json.opponent.defensiveRating != null ? Number(json.opponent.defensiveRating) : null,
        pace: json.opponent.pace != null ? Number(json.opponent.pace) : null,
      }
    : null;
  const opponentInfo = json.opponentInfo && typeof json.opponentInfo === 'object' ? json.opponentInfo : null;
  const contextualFactors = json.contextualFactors
    ? {
        daysRest: json.contextualFactors.daysRest != null ? Number(json.contextualFactors.daysRest) : null,
        isBackToBack: json.contextualFactors.isBackToBack != null ? Boolean(json.contextualFactors.isBackToBack) : null,
      }
    : null;
  const projectedMinutes = json.projectedMinutes != null ? Number(json.projectedMinutes) : null;

  // Multi-season / training-scoped fields (may be present on richer backend responses)
  const seasonsConsidered = Array.isArray(json.seasonsConsidered) ? json.seasonsConsidered.map(String) : null;
  const seasonStatsMulti = json.seasonStatsMulti || null;
  const advancedStatsMulti = json.advancedStatsMulti || null;
  const teamId = json.teamId != null ? Number(json.teamId) : null;
  const teamStatsMulti = json.teamStatsMulti || null;
  const teamAdvancedMulti = json.teamAdvancedMulti || null;

  if ((!recentGames || recentGames.length === 0) && seasonAvg == null && !noGamesThisSeason) return null;

  return {
    player: playerName || (json.player as string) || null,
    stat: statType || (json.stat as string) || null,
    recent: recent,
    recentGames,
    season: json.season || null,
    seasonAvg,
    notes,
    opponent,
    projectedMinutes,
    noGamesThisSeason,
    note: json.note || null,
    lastSeason: json.lastSeason || null,
    lastGameDate: json.lastGameDate || null,
    fetchedAt: new Date().toISOString(),
    contextualFactors,
    recentSource,
    seasonSource,
      // include rolling averages/opponent info and optional multi-season training fields when present
      rollingAverages,
      opponentInfo,
      seasonsConsidered,
      seasonStatsMulti,
      advancedStatsMulti,
      teamId,
      teamStatsMulti,
      teamAdvancedMulti,
  } as NBAPlayerContext;
}

export async function fetchPlayerContextFromNBA(
  proj: ParsedProjection,
  settings: Settings,
  limit = 8
): Promise<NBAPlayerContext | null> {
  // Prefer Vite env var `VITE_NBA_ENDPOINT`, then local FastAPI backend on port 8000 (dev); fall back to 3002 if needed
  // This allows using e.g. .env: VITE_NBA_ENDPOINT=http://localhost:8001
   
  // @ts-ignore
  const viteEnvEndpoint =
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_NBA_ENDPOINT
      ? String(import.meta.env.VITE_NBA_ENDPOINT)
      : undefined;
  const defaultEndpoint = viteEnvEndpoint || "http://localhost:8000";
  const base =
    settings?.nbaEndpoint && settings.nbaEndpoint.length > 0
      ? settings.nbaEndpoint
      : defaultEndpoint;

  // Prefer the canonical new backend paths first
  const candidates = [
    base + "/api/player_context",
    base + "/player_summary",
    base + "/api/player_summary",
    base + "/player/context",
    base,
  ];

  const headersBase: Record<string, string> = { Accept: "application/json" };
  if (settings?.nbaApiKey)
    headersBase["Authorization"] = `Bearer ${settings.nbaApiKey}`;

  // Helper uses module-level normalizer

  // Try each candidate with retries/backoff
  for (const candidate of candidates) {
    try {
      const url = `${candidate}${
        candidate.includes("?") ? "&" : "?"
      }player=${encodeURIComponent(proj.player)}&stat=${encodeURIComponent(
        proj.stat
      )}&limit=${limit}`;
      let attempt = 0;
      while (attempt < 3) {
        try {
          const resp = await fetch(url, {
            method: "GET",
            headers: headersBase,
          });
          if (!resp.ok) {
            attempt++;
            await new Promise((r) => setTimeout(r, 200 * attempt));
            continue;
          }
          const json = await resp.json();
          const ctx = normalizeBackendResponse(json, proj.player, proj.stat);
          if (ctx) return ctx;
          // if normalization failed, stop trying this candidate and move to next
          break;
        } catch {
          attempt++;
          await new Promise((r) => setTimeout(r, 200 * attempt));
          continue;
        }
      }
    } catch {
      // continue to next candidate
    }
  }

  return null;
}

export async function buildExternalContextForProjections(
  projections: ParsedProjection[],
  settings: Settings
) {
  // Default TTL: 6 hours
  const TTL_MS = 6 * 60 * 60 * 1000;
  const contexts: Record<string, NBAPlayerContext | null> = {};

  // Attempt to read existing cached contexts from IndexedDB to avoid unnecessary
  // backend calls. We'll fetch missing or stale entries only.
  try {
    const existing = await getProjectionsByIds(projections.map((p) => p.id));
    const existingMap = new Map<string, any>();
    for (const ex of existing) existingMap.set(ex.id, ex);

    for (const p of projections) {
      try {
        const stored = existingMap.get(p.id);
        const cached: NBAPlayerContext | null = stored?.nbaContext || null;
        if (cached && cached.fetchedAt) {
          const age = Date.now() - new Date(cached.fetchedAt).getTime();
          if (age >= 0 && age < TTL_MS) {
            contexts[p.id] = cached;
            continue; // fresh cached value, skip network
          }
        }

        // fetch fresh from backend; try primary then extended if missing
        let c = await fetchPlayerContextFromNBA(p, settings);
        if (!c) {
          // attempt an extended fetch by toggling an `extended` query param (some backends support richer responses)
          const extSettings = { ...settings } as any;
          if (typeof extSettings.nbaEndpoint === "string")
            extSettings.nbaEndpoint =
              String(extSettings.nbaEndpoint) +
              (String(extSettings.nbaEndpoint).includes("?") ? "&" : "?") +
              "extended=1";
          c = await fetchPlayerContextFromNBA(p, extSettings);
        }
        if (c) {
          // ensure fetchedAt set on returned context
          c.fetchedAt = c.fetchedAt || new Date().toISOString();
        }
        contexts[p.id] = c;
      } catch {
          contexts[p.id] = null;
        }
    }
    return contexts;
  } catch {
    // If DB read fails for any reason, fall back to fetching all from backend
    for (const p of projections) {
      try {
        const c = await fetchPlayerContextFromNBA(p, settings);
        if (c) c.fetchedAt = c.fetchedAt || new Date().toISOString();
        contexts[p.id] = c;
      } catch {
        contexts[p.id] = null;
      }
    }
    return contexts;
  }
}

// Batch fetch helper: POSTs a list of player requests to the backend batch endpoint.
export async function fetchBatchPlayerContext(
  requests: Array<{ player: string; stat?: string; limit?: number }>,
  settings: Settings
): Promise<Array<NBAPlayerContext | { player: string; error: string }>> {
  const viteEnvEndpoint =
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_NBA_ENDPOINT
      ? String(import.meta.env.VITE_NBA_ENDPOINT)
      : undefined;
  const defaultEndpoint = viteEnvEndpoint || "http://localhost:8000";
  const base =
    settings?.nbaEndpoint && settings.nbaEndpoint.length > 0
      ? settings.nbaEndpoint
      : defaultEndpoint;

  const url = base + "/api/batch_player_context";

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(requests.map((r) => ({ player: r.player, stat: r.stat || "points", limit: r.limit || 8 }))),
    });
    if (!resp.ok) return requests.map((r) => ({ player: r.player, error: `http ${resp.status}` }));
    const json = await resp.json();
    // Expecting an array with per-player summaries or error objects
    if (!Array.isArray(json)) return requests.map((r) => ({ player: r.player, error: "unexpected response" }));
    return json.map((item: any, i: number) => {
      if (item && item.error) return { player: item.player || requests[i].player, error: String(item.error) };
      // try to normalize shape into NBAPlayerContext using the original request's player/stat
      const normalized = normalizeBackendResponse(item, requests[i].player, requests[i].stat || 'points');
      return (
        normalized || ({ player: requests[i].player, error: 'no context' } as any)
      );
    });
  } catch (e) {
    return requests.map((r) => ({ player: r.player, error: String(e) }));
  }
}
