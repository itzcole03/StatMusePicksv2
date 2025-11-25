import type { ParsedProjection } from "../types";

// Streaming parser: incrementally extract objects from a large JSON `data` array
// so we never materialize the full array. This reduces memory and GC churn.
const DB_NAME = "prizepicks-db";
const DB_VERSION = 3;
const STORE = "projections";
const PLAYERS_STORE = "players";
const PLAYER_MAP = "player_map";

function openIndexedDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (ev: any) => {
      const db = ev.target.result as IDBDatabase;
      try {
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: "id" });
          try { store.createIndex("league", "league", { unique: false }); } catch {}
          try { store.createIndex("stat", "stat", { unique: false }); } catch {}
          try { store.createIndex("player", "player", { unique: false }); } catch {}
        }
        if (!db.objectStoreNames.contains(PLAYERS_STORE)) {
          db.createObjectStore(PLAYERS_STORE, { keyPath: "name" });
        }
        if (!db.objectStoreNames.contains(PLAYER_MAP)) {
          const pm = db.createObjectStore(PLAYER_MAP, { keyPath: ["league", "stat", "name"] });
          try { pm.createIndex("league_stat", ["league", "stat"], { unique: false }); } catch {}
        }
      } catch {}
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function txDone(tx: IDBTransaction) {
  return new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

function findMatchingBracket(str: string, start: number, openCh: string, closeCh: string) {
  let depth = 0;
  for (let i = start; i < str.length; i++) {
    const ch = str[i];
    if (ch === openCh) depth++;
    else if (ch === closeCh) {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

// Extract a JSON value (object/array) starting at `start` (pointing at '[' or '{')
function extractJsonValue(str: string, start: number) {
  const ch = str[start];
  if (ch === "[") {
    const end = findMatchingBracket(str, start, "[", "]");
    if (end === -1) throw new Error("No matching ] found");
    return { slice: str.slice(start, end + 1), end };
  }
  if (ch === "{") {
    const end = findMatchingBracket(str, start, "{", "}");
    if (end === -1) throw new Error("No matching } found");
    return { slice: str.slice(start, end + 1), end };
  }
  throw new Error("Unsupported JSON value start: " + ch);
}

// Stream-parse an array embedded in `raw`. startIdx should point at the '[' of the array.
async function* streamArrayItems(raw: string, startIdx: number) {
  let i = startIdx + 1; // skip '['
  const L = raw.length;
  while (i < L) {
    // skip whitespace and commas
    while (i < L && /[\s,]/.test(raw[i])) i++;
    if (i >= L) break;
    if (raw[i] === ']') break;
    if (raw[i] === '{') {
      const end = findMatchingBracket(raw, i, '{', '}');
      if (end === -1) throw new Error('Unterminated object in array');
      const itemStr = raw.slice(i, end + 1);
      let parsed;
      try {
        parsed = JSON.parse(itemStr);
      } catch (e) {
        throw new Error('Item parse error: ' + (e as any).message);
      }
      yield { item: parsed, endIndex: end + 1 };
      i = end + 1;
    } else {
      // handle primitives (strings/numbers/null) if necessary
      // find next comma or closing bracket
      let j = i;
      while (j < L && raw[j] !== ',' && raw[j] !== ']') j++;
      const token = raw.slice(i, j).trim();
      if (token) {
        try {
          const parsed = JSON.parse(token);
          yield { item: parsed, endIndex: j };
        } catch {
          // ignore unparsable tokens
        }
      }
      i = j + 1;
    }
  }
}

// Main worker entrypoint
self.onmessage = async (e: MessageEvent) => {
  // accept either a raw string or { raw: string, fastImport?: boolean }
  const payload: any = e.data;
  const raw = typeof payload === 'string' ? payload : payload?.raw;
  const fastImport = typeof payload === 'object' && payload?.fastImport === true;
  let db: IDBDatabase | null = null;
  let totalSaved = 0;
  try {
    // locate `included` (optional) and parse it (usually small)
    const included: any[] = [];
    const includedKey = '"included"';
    const incPos = raw.indexOf(includedKey);
    if (incPos !== -1) {
      try {
        // find the ':' after 'included'
        let colon = raw.indexOf(':', incPos + includedKey.length);
        if (colon !== -1) {
          // find the start of the value (skip whitespace)
          let vstart = colon + 1;
          while (vstart < raw.length && /[\s]/.test(raw[vstart])) vstart++;
            if (raw[vstart] === '[') {
            const res = extractJsonValue(raw, vstart);
            const parsedIncl = JSON.parse(res.slice);
            if (Array.isArray(parsedIncl)) {
              parsedIncl.forEach((it: any) => included.push(it));
            }
          }
        }
      } catch {
        // Fallback: if our incremental extraction fails (edge cases with strings/brackets),
        // parse the whole payload as a last resort to recover `included`. This is rare
        // and only affects the small `included` section; we avoid this path normally.
        try {
          const parsedAll = JSON.parse(raw);
          if (parsedAll && Array.isArray(parsedAll.included)) {
            parsedAll.included.forEach((it: any) => included.push(it));
          }
        } catch {
          // ignore; leave included empty
        }
      }
    }

    // build lookup maps from included
    const playersMap: Record<string, any> = {};
    const leagues: Record<string, string> = {};
    included.forEach((item: any) => {
      if (item.type === "new_player") {
        playersMap[item.id] = {
          name: item.attributes?.name || "Unknown",
          team: item.attributes?.team || "Unknown",
          position: item.attributes?.position || "Unknown",
        };
      } else if (item.type === "league") {
        leagues[item.id] = item.attributes?.name || "Unknown";
      }
    });

    // find start of data array: look for "data" then '[' or fall back to top-level array
    let dataStart = -1;
    const dataKey = '"data"';
    const dpos = raw.indexOf(dataKey);
    if (dpos !== -1) {
      let colon = raw.indexOf(':', dpos + dataKey.length);
      if (colon !== -1) {
        let vstart = colon + 1;
        while (vstart < raw.length && /[\s]/.test(raw[vstart])) vstart++;
        if (raw[vstart] === '[') dataStart = vstart;
      }
    }
    if (dataStart === -1) {
      // if raw itself is an array
      const trimmed = raw.trimStart();
      if (trimmed[0] === '[') {
        dataStart = raw.indexOf('[');
      }
    }

    if (dataStart === -1) {
      throw new Error('No data array found in payload');
    }

    db = await openIndexedDB();

    // adaptive chunk size based on payload length
    const targetTransactions = 60;
    const CHUNK = Math.min(2000, Math.max(200, Math.ceil((raw.length / 1000) / targetTransactions)));

    // accumulate per-chunk arrays and unique player_map entries
    let mappedBatch: ParsedProjection[] = [];
    let pmSet = new Set<string>();
    const playerCounts = new Map<string, number>();

    let processedChars = 0;
    let pendingCount = 0;
    let lastPost = Date.now();
    const POST_INTERVAL = 120; // ms

    // iterate items from stream generator
    for await (const { item, endIndex } of streamArrayItems(raw, dataStart)) {
      processedChars = endIndex;
      // map projection
      try {
        const proj = item as any;
        const playerId = proj.relationships?.new_player?.data?.id;
        const leagueId = proj.relationships?.league?.data?.id;
        const gameId = proj.relationships?.game?.data?.id;
        const pName = playersMap[playerId]?.name || "Unknown";
        const rec: ParsedProjection = {
          id: proj.id,
          player: pName,
          team: playersMap[playerId]?.team || "Unknown",
          position: playersMap[playerId]?.position || "Unknown",
          league: leagues[leagueId] || "Unknown",
          stat: proj.attributes?.stat_type || "unknown",
          line: proj.attributes?.line_score ?? 0,
          startTime: proj.attributes?.start_time || "",
          status: proj.attributes?.status || "unknown",
          gameId: gameId,
        };
        if (rec.status === 'pre_game') {
          mappedBatch.push(rec);
          pmSet.add(`${rec.league}:::${rec.stat}:::${rec.player}`);
          playerCounts.set(rec.player, (playerCounts.get(rec.player) || 0) + 1);
        }
      } catch {
        // ignore individual parse/map errors
      }

      if (mappedBatch.length >= CHUNK) {
        // write batch
        try {
          const tx = db.transaction([STORE, PLAYER_MAP], 'readwrite');
          const store = tx.objectStore(STORE);
          const pm = tx.objectStore(PLAYER_MAP);
          for (const it of mappedBatch) {
            try { store.put(it); totalSaved++; } catch {}
          }
          for (const key of pmSet) {
            try {
              const parts = key.split(':::');
              pm.put({ league: parts[0] || '', stat: parts[1] || '', name: parts[2] || '' });
            } catch {}
          }
          await txDone(tx);
        } catch {
          // swallow but continue
        }

        pendingCount += mappedBatch.length;
        mappedBatch = [];
        pmSet = new Set<string>();
      }

      // throttled progress post
      const now = Date.now();
      if (now - lastPost >= POST_INTERVAL) {
        const progress = Math.min(1, processedChars / raw.length);
        self.postMessage({ type: 'chunk', count: pendingCount, progress });
        pendingCount = 0;
        lastPost = now;
      }
    }

    // flush remaining mappedBatch
    if (mappedBatch.length > 0) {
      try {
        const tx = db.transaction([STORE, PLAYER_MAP], 'readwrite');
        const store = tx.objectStore(STORE);
        const pm = tx.objectStore(PLAYER_MAP);
        for (const it of mappedBatch) {
          try { store.put(it); totalSaved++; } catch {}
        }
        for (const key of pmSet) {
          try {
            const parts = key.split(':::');
            pm.put({ league: parts[0] || '', stat: parts[1] || '', name: parts[2] || '' });
          } catch {}
        }
        await txDone(tx);
      } catch {}
      pendingCount += mappedBatch.length;
    }

    // flush playerCounts to PLAYERS_STORE in one transaction (deferred if desired)
    if (!fastImport && playerCounts.size > 0) {
      try {
        const tx2 = db.transaction(PLAYERS_STORE, 'readwrite');
        const ps = tx2.objectStore(PLAYERS_STORE);
        for (const [name, cnt] of playerCounts.entries()) {
          try {
            const getReq = ps.get(name);
            const existing = await new Promise<any>((res, rej) => {
              getReq.onsuccess = () => res(getReq.result);
              getReq.onerror = () => rej(getReq.error);
            });
            const existingCount = existing?.count || 0;
            ps.put({ name, count: existingCount + cnt });
          } catch {}
        }
        await txDone(tx2);
      } catch {}
    }

    // final progress and done
    if (pendingCount > 0) self.postMessage({ type: 'chunk', count: pendingCount, progress: 1 });
    // if fastImport, indicate that index rebuild is needed
    self.postMessage({ type: 'done', total: totalSaved, indexDirty: fastImport ? true : false });
  } catch (err: any) {
    try { self.postMessage({ type: 'error', message: err?.message || String(err) }); } catch {}
  } finally {
    try { if (db) db.close(); } catch {}
  }
};

export {};
