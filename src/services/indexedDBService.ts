import { openDB, IDBPDatabase } from 'idb';
import { ParsedProjection } from '../types';

const DB_NAME = 'prizepicks-db';
const STORE = 'projections';
const PLAYERS_STORE = 'players';
const HANDLES_STORE = 'handles';
const DB_VERSION = 3;

let dbPromise: Promise<IDBPDatabase> | null = null;

export function initDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db, _oldVersion) {
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'id' });
          store.createIndex('league', 'league', { unique: false });
          store.createIndex('stat', 'stat', { unique: false });
          store.createIndex('player', 'player', { unique: false });
        }
        if (!db.objectStoreNames.contains(PLAYERS_STORE)) {
          // store distinct player names for fast suggestions; keyPath 'name'
          // we'll store { name: string, count?: number }
          db.createObjectStore(PLAYERS_STORE, { keyPath: 'name' });
        }
        // add a mapping store for league/stat -> player for fast filtered lookups
        if (!db.objectStoreNames.contains('player_map')) {
          const pm = db.createObjectStore('player_map', { keyPath: ['league', 'stat', 'name'] });
          pm.createIndex('league_stat', ['league', 'stat'], { unique: false });
        }
        // add a small store for storing handles (FileSystemDirectoryHandle via structured clone)
        if (!db.objectStoreNames.contains(HANDLES_STORE)) {
          db.createObjectStore(HANDLES_STORE, { keyPath: 'key' });
        }
      }
    }).then(async (db) => {
      // one-time population: if player_map is empty but projections exist, populate players and player_map
      try {
        const tx = db.transaction('player_map', 'readonly');
        const count = await tx.store.count();
        await tx.done;
        if (count === 0) {
          // populate from projections
          const tx2 = db.transaction([STORE, PLAYERS_STORE, 'player_map'], 'readwrite');
          const all = await tx2.objectStore(STORE).getAll();
          const playersSet = new Set<string>();
          for (const it of all) {
            if (it.player) playersSet.add(it.player);
            try {
              tx2.objectStore('player_map').put({ league: it.league || '', stat: it.stat || '', name: it.player });
            } catch (e) {
              // ignore individual put errors
            }
          }
          for (const name of playersSet) {
            try { tx2.objectStore(PLAYERS_STORE).put({ name }); } catch (e) { }
          }
          await tx2.done;
        }
      } catch (e) {
        // ignore migration errors
      }
      return db;
    });
  }
  return dbPromise;
}

// Save a FileSystemDirectoryHandle (or any serializable handle) under key 'modelDir'
export async function saveModelDirHandle(handle: any) {
  const db = await initDB();
  const tx = db.transaction(HANDLES_STORE, 'readwrite');
  try {
    await tx.store.put({ key: 'modelDir', handle, name: handle?.name || '' });
    await tx.done;
  } catch (err) {
    console.warn('saveModelDirHandle error', err);
  }
}

export async function getModelDirHandle(): Promise<any | null> {
  const db = await initDB();
  const tx = db.transaction(HANDLES_STORE, 'readonly');
  const rec = await tx.store.get('modelDir');
  await tx.done;
  return rec?.handle || null;
}

export async function getSavedModelDirName(): Promise<string | null> {
  const db = await initDB();
  const tx = db.transaction(HANDLES_STORE, 'readonly');
  const rec = await tx.store.get('modelDir');
  await tx.done;
  return rec?.name || null;
}

// List children names inside the saved model directory handle (if available)
export async function listModelsInSavedDir(): Promise<string[]> {
  const handle = await getModelDirHandle();
  if (!handle) return [];
  const names: string[] = [];
  try {
    // `entries()` is supported in the File System Access API; treat as any to avoid TS lib issues
    // iterate children and collect directory or file names
    for await (const entry of (handle as any).values ? (handle as any).values() : (handle as any).entries()) {
      // entries can be [name, handle] or direct handles depending on browser
      if (Array.isArray(entry)) {
        const [name, _child] = entry as [string, any];
        names.push(name);
      } else if (entry && entry.name) {
        names.push(entry.name);
      }
    }
  } catch (err) {
    // fallback: try keys() or values()
    try {
      for await (const [name] of (handle as any).entries()) {
        names.push(name as string);
      }
    } catch (e) {
      console.warn('Could not list directory entries', e);
    }
  }
  return names.sort();
}

export async function saveBatch(items: ParsedProjection[]) {
  const db = await initDB();
  // write to projections, players store and player_map in single transaction
  const tx = db.transaction([STORE, PLAYERS_STORE, 'player_map'], 'readwrite');
  try {
    // count occurrences in this batch for each player
    const batchCounts = new Map<string, number>();
    for (const it of items) {
      if (!it.id) continue;
      tx.objectStore(STORE).put(it);
      if (it.player) {
        batchCounts.set(it.player, (batchCounts.get(it.player) || 0) + 1);
      }
      try {
        tx.objectStore('player_map').put({ league: it.league || '', stat: it.stat || '', name: it.player });
      } catch (e) {
        // ignore single put errors
      }
    }

    // update players store counts by reading existing counts and adding batch counts
    for (const [name, cnt] of batchCounts.entries()) {
      try {
        const existing = await tx.objectStore(PLAYERS_STORE).get(name);
        const existingCount = existing?.count || 0;
        await tx.objectStore(PLAYERS_STORE).put({ name, count: existingCount + cnt });
      } catch (e) {
        // ignore single put errors
      }
    }

    await tx.done;
  } catch (err) {
    console.error('saveBatch error', err);
    throw err;
  }
}

// Rebuild players and player_map stores from existing projections. Returns summary counts.
export async function rebuildPlayersIndex(): Promise<{ players: number; mappings: number }> {
  const db = await initDB();
  // read all projections and repopulate players and player_map
  const tx = db.transaction([STORE, PLAYERS_STORE, 'player_map'], 'readwrite');
  try {
    await tx.objectStore(PLAYERS_STORE).clear();
    await tx.objectStore('player_map').clear();
    const all = await tx.objectStore(STORE).getAll();
    const playerCounts = new Map<string, number>();
    let mappings = 0;
    for (const it of all) {
      if (!it.player) continue;
      playerCounts.set(it.player, (playerCounts.get(it.player) || 0) + 1);
      try {
        tx.objectStore('player_map').put({ league: it.league || '', stat: it.stat || '', name: it.player });
        mappings++;
      } catch (e) {
        // ignore individual put errors
      }
    }
    for (const [name, cnt] of playerCounts.entries()) {
      try { await tx.objectStore(PLAYERS_STORE).put({ name, count: cnt }); } catch (e) { }
    }
    await tx.done;
    return { players: playerCounts.size, mappings };
  } catch (e) {
    try { await tx.done; } catch (_) {}
    throw e;
  }
}

export async function clearDB() {
  const db = await initDB();
  const tx = db.transaction([STORE, PLAYERS_STORE, 'player_map'], 'readwrite');
  await tx.objectStore(STORE).clear();
  await tx.objectStore(PLAYERS_STORE).clear();
  await tx.objectStore('player_map').clear();
  await tx.done;
}

export async function countAll() {
  const db = await initDB();
  return db.count(STORE);
}

export async function getDistinctValues(field: 'league' | 'stat' | 'player') {
  const db = await initDB();
  const tx = db.transaction(STORE, 'readonly');
  const all = await tx.store.getAll();
  await tx.done;
  const set = new Set<string>();
  for (const item of all) {
    const v = item[field];
    if (v) set.add(v);
  }
  return Array.from(set).sort();
}

export async function getDistinctStatsByLeague(league?: string) {
  const db = await initDB();
  const tx = db.transaction(STORE, 'readonly');
  const all = await tx.store.getAll();
  await tx.done;
  const set = new Set<string>();
  for (const item of all) {
    if (league && item.league !== league) continue;
    if (item.stat) set.add(item.stat);
  }
  return Array.from(set).sort();
}

export async function getDistinctLeaguesByStat(stat?: string) {
  const db = await initDB();
  const tx = db.transaction(STORE, 'readonly');
  const all = await tx.store.getAll();
  await tx.done;
  const set = new Set<string>();
  for (const item of all) {
    if (stat && item.stat !== stat) continue;
    if (item.league) set.add(item.league);
  }
  return Array.from(set).sort();
}

export async function getDistinctPlayersByFilters(league?: string, stat?: string) {
  const db = await initDB();
  // If no league/stat filters, we can return the players from the dedicated players store
  if (!league && !stat) {
    const tx = db.transaction(PLAYERS_STORE, 'readonly');
    const keys = await tx.store.getAllKeys();
    await tx.done;
    return (keys as string[]).sort();
  }
  // Try to use player_map for fast lookup of players by league/stat
  try {
    const tx = db.transaction('player_map', 'readonly');
    const store = tx.objectStore('player_map');
    const idx = store.index('league_stat');
    let entries: any[] = [];
    if (league && stat) {
      entries = await idx.getAll([league, stat]);
    } else if (league && !stat) {
      const range = IDBKeyRange.bound([league, ''], [league, '\uffff']);
      entries = await idx.getAll(range);
    } else if (!league && stat) {
      // no direct index for stat-only; fallback to scanning entries
      const all = await store.getAll();
      entries = all.filter((e: any) => e.stat === stat);
    }
    await tx.done;
    const set = new Set<string>();
    for (const e of entries) if (e && e.name) set.add(e.name);
    return Array.from(set).sort();
  } catch (e) {
    // fallback to scanning projections store
    const tx = db.transaction(STORE, 'readonly');
    const all = await tx.store.getAll();
    await tx.done;
    const set = new Set<string>();
    for (const item of all) {
      if (league && item.league !== league) continue;
      if (stat && item.stat !== stat) continue;
      if (item.player) set.add(item.player);
    }
    return Array.from(set).sort();
  }
}

// Like getDistinctPlayersByFilters but allows a search query (substring match)
export async function getDistinctPlayersByFiltersWithQuery(league?: string, stat?: string, query?: string) {
  const db = await initDB();
  const q = query ? query.toLowerCase() : '';
  // If no league/stat filters, query the players store (fast)
  if (!league && !stat) {
    const tx = db.transaction(PLAYERS_STORE, 'readonly');
    const keys = await tx.store.getAllKeys();
    await tx.done;
    let arr = (keys as string[]);
    if (q) arr = arr.filter(p => p.toLowerCase().includes(q));
    return arr.sort();
  }

  // Try to use player_map index for filtered, queried suggestions
  try {
    const tx = db.transaction('player_map', 'readonly');
    const store = tx.objectStore('player_map');
    const idx = store.index('league_stat');
    let entries: any[] = [];
    if (league && stat) {
      entries = await idx.getAll([league, stat]);
    } else if (league && !stat) {
      const range = IDBKeyRange.bound([league, ''], [league, '\uffff']);
      entries = await idx.getAll(range);
    } else if (!league && stat) {
      const all = await store.getAll();
      entries = all.filter((e: any) => e.stat === stat);
    }
    await tx.done;
    const set = new Set<string>();
    for (const e of entries) {
      if (!e || !e.name) continue;
      if (q && !e.name.toLowerCase().includes(q)) continue;
      set.add(e.name);
    }
    return Array.from(set).sort();
  } catch (e) {
    // fallback to scanning projections store but apply query filtering
    const tx = db.transaction(STORE, 'readonly');
    const all = await tx.store.getAll();
    await tx.done;
    const set = new Set<string>();
    for (const item of all) {
      if (league && item.league !== league) continue;
      if (stat && item.stat !== stat) continue;
      if (!item.player) continue;
      if (q && !item.player.toLowerCase().includes(q)) continue;
      set.add(item.player);
    }
    return Array.from(set).sort();
  }
}

// Return distinct league/stat mappings for a given player name.
export async function getPlayerMappings(name: string) {
  const db = await initDB();
  const tx = db.transaction(['player_map', STORE], 'readonly');
  try {
    const pm = tx.objectStore('player_map');
    // player_map doesn't have a name index, so read all and filter — it's small relative to projections
    const all = await pm.getAll();
    await tx.done;
    const mappings: { league: string; stat: string }[] = [];
    for (const e of all) {
      if (!e || !e.name) continue;
      if (e.name === name) mappings.push({ league: e.league || '', stat: e.stat || '' });
    }
    // dedupe
    const seen = new Set<string>();
    const dedup: { league: string; stat: string }[] = [];
    for (const m of mappings) {
      const key = `${m.league}::${m.stat}`;
      if (seen.has(key)) continue;
      seen.add(key);
      dedup.push(m);
    }
    return dedup;
  } catch (e) {
    try { await tx.done; } catch (_) {}
    // fallback to scanning projections store
    const tx2 = db.transaction(STORE, 'readonly');
    const allp = await tx2.store.getAll();
    await tx2.done;
    const set = new Set<string>();
    const out: { league: string; stat: string }[] = [];
    for (const it of allp) {
      if (!it.player) continue;
      if (it.player !== name) continue;
      const key = `${it.league || ''}::${it.stat || ''}`;
      if (set.has(key)) continue;
      set.add(key);
      out.push({ league: it.league || '', stat: it.stat || '' });
    }
    return out;
  }
}

// Return player suggestions with counts: { name, count }
export async function getPlayersWithCounts(league?: string, stat?: string, query?: string) {
  const db = await initDB();
  const q = query ? query.toLowerCase() : '';

  // If no league/stat, read directly from players store which has counts
  if (!league && !stat) {
    const tx = db.transaction(PLAYERS_STORE, 'readonly');
    const all = await tx.store.getAll();
    await tx.done;
    let arr = (all as any[]).map((r) => ({ name: r.name, count: r.count || 0 }));
    if (q) arr = arr.filter(p => p.name.toLowerCase().includes(q));
    return arr.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  }

  // For filtered queries, use player_map to find names and lookup counts from players store
  try {
    const tx = db.transaction(['player_map', PLAYERS_STORE], 'readonly');
    const pm = tx.objectStore('player_map');
    const idx = pm.index('league_stat');
    let entries: any[] = [];
    if (league && stat) {
      entries = await idx.getAll([league, stat]);
    } else if (league && !stat) {
      const range = IDBKeyRange.bound([league, ''], [league, '\uffff']);
      entries = await idx.getAll(range);
    } else if (!league && stat) {
      const all = await pm.getAll();
      entries = all.filter((e: any) => e.stat === stat);
    }
    const names = Array.from(new Set(entries.map(e => e.name).filter(Boolean)));
    const results: { name: string; count: number }[] = [];
    for (const name of names) {
      const rec = await tx.objectStore(PLAYERS_STORE).get(name);
      results.push({ name, count: rec?.count || 0 });
    }
    await tx.done;
    const qfiltered = q ? results.filter(r => r.name.toLowerCase().includes(q)) : results;
    return qfiltered.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  } catch (e) {
    // fallback: scan projections and compute counts
    const tx = db.transaction(STORE, 'readonly');
    const all = await tx.store.getAll();
    await tx.done;
    const map = new Map<string, number>();
    for (const it of all) {
      if (league && it.league !== league) continue;
      if (stat && it.stat !== stat) continue;
      if (!it.player) continue;
      if (q && !it.player.toLowerCase().includes(q)) continue;
      map.set(it.player, (map.get(it.player) || 0) + 1);
    }
    return Array.from(map.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  }
}

export async function queryProjections(filters: { league?: string; stat?: string; playerName?: string }, offset = 0, limit = 50) {
  const db = await initDB();
  const tx = db.transaction(STORE, 'readonly');
  const all = await tx.store.getAll();
  await tx.done;

  const filtered = all.filter((value: ParsedProjection) => {
    if (filters.league && value.league !== filters.league) return false;
    if (filters.stat && value.stat !== filters.stat) return false;
    if (filters.playerName && filters.playerName.length && !value.player.toLowerCase().includes(filters.playerName.toLowerCase())) return false;
    return true;
  });

  const totalMatched = filtered.length;
  const items = filtered.slice(offset, offset + limit);
  return { items, totalMatched };
}

export async function getProjectionsByIds(ids: string[]) {
  const db = await initDB();
  const tx = db.transaction(STORE, 'readonly');
  const r: ParsedProjection[] = [];
  for (const id of ids) {
    const v = await tx.store.get(id);
    if (v) r.push(v as ParsedProjection);
  }
  await tx.done;
  return r;
}

// Persist NBA contexts (mapping projectionId -> context) into the projections store.
// The context object will be attached to the `nbaContext` field on the projection.
export async function saveNbaContexts(contexts: Record<string, any>) {
  if (!contexts || Object.keys(contexts).length === 0) return;
  const db = await initDB();
  const tx = db.transaction(STORE, 'readwrite');
  try {
    for (const [id, ctx] of Object.entries(contexts)) {
      try {
        const existing = await tx.store.get(id);
        if (!existing) continue;
        const mergedCtx = { ...(existing.nbaContext || {}), ...(ctx || {}) };
        // ensure a fetchedAt timestamp exists for caching/TTL purposes
        if (!mergedCtx.fetchedAt) mergedCtx.fetchedAt = new Date().toISOString();
        const updated = { ...existing, nbaContext: mergedCtx };
        await tx.store.put(updated);
      } catch (e) {
        // ignore individual put errors
      }
    }
    await tx.done;
  } catch (e) {
    try { await tx.done; } catch (_) {}
    throw e;
  }
}
