const STORAGE_PREFIX = "autoRefresh:";
const DEFAULT_URL = "https://partner-api.prizepicks.com/projections";

// optional proxy URL key: if direct fetch fails (CORS/Network), service will
// attempt to fetch via this proxy URL (user-configurable)
function storageKey(k: string) {
  return STORAGE_PREFIX + k;
}

export type AutoRefreshSettings = {
  enabled: boolean;
  intervalMinutes: number;
  url: string;
  proxyUrl?: string | null;
};

let timer: number | null = null;

function readSetting(): AutoRefreshSettings {
  const enabled = localStorage.getItem(storageKey("enabled")) === "true";
  const interval = parseInt(
    localStorage.getItem(storageKey("interval")) || "60",
    10
  );
  const url = localStorage.getItem(storageKey("url")) || DEFAULT_URL;
  const proxyUrl = localStorage.getItem(storageKey("proxyUrl")) || null;
  return {
    enabled,
    intervalMinutes: isNaN(interval) ? 60 : interval,
    url,
    proxyUrl,
  };
}

function writeSetting(s: Partial<AutoRefreshSettings>) {
  if (typeof s.enabled === "boolean")
    localStorage.setItem(storageKey("enabled"), String(s.enabled));
  if (typeof s.intervalMinutes === "number")
    localStorage.setItem(storageKey("interval"), String(s.intervalMinutes));
  if (typeof s.url === "string") localStorage.setItem(storageKey("url"), s.url);
  if (typeof s.proxyUrl === "string")
    localStorage.setItem(storageKey("proxyUrl"), s.proxyUrl);
}

function getStoredHeaders() {
  return {
    etag: localStorage.getItem(storageKey("etag")) || undefined,
    lastModified: localStorage.getItem(storageKey("lastModified")) || undefined,
    headHash: localStorage.getItem(storageKey("headHash")) || undefined,
  };
}

function saveHeaders(
  etag?: string | null,
  lastModified?: string | null,
  headHash?: string | null
) {
  if (etag) localStorage.setItem(storageKey("etag"), etag);
  if (lastModified)
    localStorage.setItem(storageKey("lastModified"), lastModified);
  if (headHash) localStorage.setItem(storageKey("headHash"), headHash);
}

function djb2Hash(s: string) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i);
  return (h >>> 0).toString(36);
}

// Backoff helpers persisted in localStorage so backoff survives reloads
const BACKOFF_BASE_SECONDS = 60; // base backoff on first 429
const BACKOFF_MAX_SECONDS = 60 * 60; // max 1 hour

function backoffKeyAttempts(url: string) {
  return storageKey(`backoff:attempts:${encodeURIComponent(url)}`);
}
function backoffKeyNext(url: string) {
  return storageKey(`backoff:next:${encodeURIComponent(url)}`);
}

function getBackoffInfo(url: string) {
  try {
    const attempts =
      parseInt(localStorage.getItem(backoffKeyAttempts(url)) || "0", 10) || 0;
    const next =
      parseInt(localStorage.getItem(backoffKeyNext(url)) || "0", 10) || 0;
    return { attempts, next };
  } catch {
    return { attempts: 0, next: 0 };
  }
}

function clearBackoff(url: string) {
  try {
    localStorage.removeItem(backoffKeyAttempts(url));
    localStorage.removeItem(backoffKeyNext(url));
  } catch {}
}

function applyBackoff(url: string) {
  try {
    const info = getBackoffInfo(url);
    const attempts = info.attempts + 1;
    // exponential: base * 2^(attempts-1)
    let delay = BACKOFF_BASE_SECONDS * Math.pow(2, Math.max(0, attempts - 1));
    if (delay > BACKOFF_MAX_SECONDS) delay = BACKOFF_MAX_SECONDS;
    // add jitter ±30%
    const jitter = Math.floor(delay * 0.3 * (Math.random() * 2 - 1));
    delay = Math.max(1, Math.round(delay + jitter));
    const next = Date.now() + delay * 1000;
    localStorage.setItem(backoffKeyAttempts(url), String(attempts));
    localStorage.setItem(backoffKeyNext(url), String(next));
    try {
      window.dispatchEvent(
        new CustomEvent("auto-refresh-backoff", {
          detail: { url, attempts, next, delay },
        })
      );
    } catch {}
    return { attempts, next, delay };
  } catch {
    return null;
  }
}

async function fetchAndMaybeDispatch(
  url: string
): Promise<{ ok: boolean; type: string; detail?: any }> {
  const headers: Record<string, string> = {};
  const stored = getStoredHeaders();
  if (stored.etag) headers["If-None-Match"] = stored.etag;
  if (stored.lastModified) headers["If-Modified-Since"] = stored.lastModified;

  const start = Date.now();
  const FALLBACK_PROXIES = ["/backend/proxy/prizepicks"];
  const backendProxy = `${location.protocol}//${location.hostname}:3002/api/proxy/prizepicks`;
  const settings = readSetting();
  const userProxy = settings.proxyUrl || undefined;

  const tryOrder = [...FALLBACK_PROXIES, backendProxy, userProxy].filter(
    Boolean
  ) as string[];
  // lastErr was previously tracked for diagnostics; not needed now

  // helper to handle a successful text payload
  const handlePayload = (
    text: string,
    etag?: string | null,
    lastModified?: string | null,
    source?: string
  ) => {
    const head = text.slice(0, 4096);
    const headHash = djb2Hash(head + (etag || "") + (lastModified || ""));
    const storedHash = localStorage.getItem(storageKey("headHash"));
    if (storedHash && storedHash === headHash) {
      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-nochange", {
            detail: { elapsed: Date.now() - start, source },
          })
        );
      } catch {}
      // update headers if needed and return indicator
      saveHeaders(etag || undefined, lastModified || undefined, headHash);
      return { same: true };
    }
    saveHeaders(etag || undefined, lastModified || undefined, headHash);
    try {
      window.dispatchEvent(
        new CustomEvent("auto-refresh-fetched", {
          detail: {
            raw: text,
            etag,
            lastModified,
            elapsed: Date.now() - start,
            source,
          },
        })
      );
    } catch {}
    return { same: false };
  };

  // try proxies in order
  for (const attemptUrl of tryOrder) {
    try {
      // skip if in backoff
      const { next } = getBackoffInfo(attemptUrl);
      if (next && Date.now() < next) {
        try {
          window.dispatchEvent(
            new CustomEvent("auto-refresh-skip", {
              detail: { url: attemptUrl, reason: "backoff" },
            })
          );
        } catch {}
        continue;
      }

      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-attempt", {
            detail: { url: attemptUrl },
          })
        );
      } catch {}
      const proxyUrl = attemptUrl.includes("?")
        ? `${attemptUrl}&url=${encodeURIComponent(url)}`
        : `${attemptUrl}?url=${encodeURIComponent(url)}`;
      const resp = await fetch(proxyUrl, { headers, cache: "no-store" });
      if (resp.status === 429) {
        applyBackoff(attemptUrl);
        continue;
      }
      if (!resp.ok) {
        try {
          window.dispatchEvent(
            new CustomEvent("auto-refresh-error", {
              detail: { status: resp.status, viaProxy: attemptUrl },
            })
          );
        } catch {}
        try {
          window.dispatchEvent(
            new CustomEvent("auto-refresh-error", {
              detail: { status: resp.status, viaProxy: attemptUrl },
            })
          );
        } catch {}
        continue;
      }
      const etag = resp.headers.get("etag");
      const lastModified = resp.headers.get("last-modified");
      const text = await resp.text();
      const same = handlePayload(text, etag, lastModified, attemptUrl);
      clearBackoff(attemptUrl);
      if (same && same.same)
        return { ok: false, type: "no-change", detail: { source: attemptUrl } };
      return { ok: true, type: "fetched", detail: { source: attemptUrl } };
    } catch (err) {
      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-error", {
            detail: { error: String(err), step: "proxy", url: attemptUrl },
          })
        );
      } catch {}
      continue;
    }
  }

  // as last resort, try direct fetch (subject to backoff)
  try {
    const directKey = "direct:" + url;
    const { next } = getBackoffInfo(directKey);
    if (next && Date.now() < next) {
      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-skip", {
            detail: { url: "direct", reason: "backoff" },
          })
        );
      } catch {}
      return { ok: false, type: "error", detail: { error: "in backoff" } };
    }
    try {
      window.dispatchEvent(
        new CustomEvent("auto-refresh-attempt", { detail: { url } })
      );
    } catch {}
    const resp = await fetch(url, { headers, cache: "no-store" });
    if (resp.status === 429) {
      applyBackoff(directKey);
      return { ok: false, type: "error", detail: { error: "429" } };
    }
    if (resp.status === 304) {
      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-skip", { detail: { status: 304 } })
        );
      } catch {}
      return { ok: true, type: "skip", detail: { status: 304 } };
    }
    if (!resp.ok) {
      try {
        window.dispatchEvent(
          new CustomEvent("auto-refresh-error", {
            detail: { status: resp.status },
          })
        );
      } catch {}
      return { ok: false, type: "error", detail: { status: resp.status } };
    }
    const etag = resp.headers.get("etag");
    const lastModified = resp.headers.get("last-modified");
    const text = await resp.text();
    const same = handlePayload(text, etag, lastModified, "direct");
    clearBackoff(directKey);
    if (same && same.same)
      return { ok: false, type: "no-change", detail: { source: "direct" } };
    return { ok: true, type: "fetched", detail: { source: "direct" } };
  } catch (err) {
    try {
      window.dispatchEvent(
        new CustomEvent("auto-refresh-error", {
          detail: { error: String(err), step: "direct" },
        })
      );
    } catch {}
    return { ok: false, type: "error", detail: { error: String(err) } };
  }
}

export function startAutoRefresh() {
  const settings = readSetting();
  stopAutoRefresh();
  // run immediately then schedule
  void fetchAndMaybeDispatch(settings.url);
  timer = window.setInterval(() => {
    void fetchAndMaybeDispatch(settings.url);
  }, Math.max(1000, settings.intervalMinutes * 60 * 1000));
  writeSetting({ enabled: true });
  try {
    window.dispatchEvent(
      new CustomEvent("auto-refresh-started", {
        detail: { interval: settings.intervalMinutes },
      })
    );
  } catch {}
}

export function stopAutoRefresh() {
  if (timer) {
    clearInterval(timer);
    timer = null;
    try {
      window.dispatchEvent(new CustomEvent("auto-refresh-stopped"));
    } catch {}
  }
  writeSetting({ enabled: false });
}

export async function refreshNow() {
  const settings = readSetting();
  const res = await fetchAndMaybeDispatch(settings.url);
  return res;
}

export function updateSettings(s: Partial<AutoRefreshSettings>) {
  writeSetting(s);
  const current = readSetting();
  if (current.enabled) {
    startAutoRefresh();
  }
}

export function getSettings() {
  return readSetting();
}

export default {
  startAutoRefresh,
  stopAutoRefresh,
  refreshNow,
  updateSettings,
  getSettings,
};
