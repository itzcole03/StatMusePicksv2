import { useEffect, useRef, useState } from "react";
import { clearDB, countAll, rebuildPlayersIndex } from "../services/indexedDBService";
import { getSettings as getAutoSettings, startAutoRefresh, refreshNow } from "../services/autoRefreshService";

export default function DataLoader() {
  const [dataInput, setDataInput] = useState("");
  const [status, setStatus] = useState<{
    message: string;
    type: "error" | "success" | "info";
  } | null>(null);
  const [progress, setProgress] = useState(0);
  const [parsedCount, setParsedCount] = useState(0);
  const workerRef = useRef<Worker | null>(null);
  const [autoStatus, setAutoStatus] = useState<string | null>(null);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [lastSource, setLastSource] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    // read persisted auto settings
    try {
      const s = getAutoSettings();
      if (s.enabled) startAutoRefresh();
    } catch {}

    const onFetched = (e: any) => {
      const raw = e?.detail?.raw;
      if (raw) {
        setAutoStatus(`fetched ${raw.length} bytes`);
        setLastRefreshTime(new Date());
        setLastSource(e?.detail?.viaProxy ? String(e.detail.viaProxy) : "direct");
        setLastError(null);
        setShowManual(false);
        // hand to existing loader path using fastImport mode for auto runs
        handleLoadDataWithString(raw, { fastImport: true });
      }
    };
    const onStarted = (e: any) => setAutoStatus(`started interval ${e?.detail?.interval}m`);
    const onStopped = () => setAutoStatus("stopped");
    const onError = (e: any) => {
      const status = e?.detail?.status;
      const err = e?.detail?.error || "";
      const viaProxy = e?.detail?.viaProxy || e?.detail?.url || null;
      const isRateLimit = (() => {
        if (status === 502 && viaProxy) return true; // backend proxy returned 502 (often from upstream 429)
        if (/429|Too Many Requests/i.test(String(err))) return true;
        return false;
      })();

      const msg = isRateLimit ? "Timeout: Try again later" : `error: ${err || status}`;
      setAutoStatus(msg);
      setLastError(msg);
      // show manual paste area so user can recover
      setShowManual(true);
    };

    window.addEventListener("auto-refresh-fetched", onFetched as EventListener);
    window.addEventListener("auto-refresh-started", onStarted as EventListener);
    window.addEventListener("auto-refresh-stopped", onStopped as EventListener);
    window.addEventListener("auto-refresh-error", onError as EventListener);

    return () => {
      window.removeEventListener("auto-refresh-fetched", onFetched as EventListener);
      window.removeEventListener("auto-refresh-started", onStarted as EventListener);
      window.removeEventListener("auto-refresh-stopped", onStopped as EventListener);
      window.removeEventListener("auto-refresh-error", onError as EventListener);
    };
  }, []);

  // sample loader removed — automation and manual paste are primary flows

  const handleLoadData = () => {
    if (!dataInput.trim()) {
      setStatus({
        message: "Please paste JSON data or load sample data first.",
        type: "error",
      });
      return;
    }
    handleLoadDataWithString(dataInput);
  };

  const handleLoadDataWithString = (raw: string, opts?: { fastImport?: boolean }) => {
    setStatus({ message: "Parsing and saving data...", type: "info" });
    setProgress(0);
    setParsedCount(0);

    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
    }

    const worker = new Worker(
      new URL("../workers/parser.worker.ts", import.meta.url),
      { type: "module" }
    );
    workerRef.current = worker;

    // We'll throttle UI updates by accumulating counts in a ref
    const parsedRef = { count: 0, progress: 0 } as { count: number; progress: number };
    const rafRef = { scheduled: false } as { scheduled: boolean };

    const flushToState = () => {
      rafRef.scheduled = false;
      setParsedCount(parsedRef.count);
      setProgress(parsedRef.progress);
    };

    worker.onmessage = async (ev) => {
      const msg = ev.data as any;
      if (msg.type === "chunk") {
        const count = (msg.count as number) || 0;
        parsedRef.count += count;
        parsedRef.progress = msg.progress ?? parsedRef.progress;
        if (!rafRef.scheduled) {
          rafRef.scheduled = true;
          requestAnimationFrame(flushToState);
        }
      } else if (msg.type === "done") {
        const total = await countAll();
        // ensure we flush any remaining before finalizing
        parsedRef.progress = 1;
        parsedRef.count = total;
        if (rafRef.scheduled) {
          // will flush on next frame
        } else {
          // no pending raf; flush now
          flushToState();
        }
        setStatus({ message: `Data parsed and saved (${total} items).`, type: "success" });
        setProgress(1);
        worker.terminate();
        workerRef.current = null;
        try {
          window.dispatchEvent(new CustomEvent("db-updated", { detail: { total } }));
        } catch {}

        // if worker indicated the player index is dirty (fast import), schedule rebuild in idle time
        if (msg.indexDirty) {
          setStatus({ message: `Data imported; scheduling index rebuild...`, type: "info" });
          const doRebuild = async () => {
            try {
              // use requestIdleCallback when available to avoid blocking UI
              const work = async () => {
                const res = await rebuildPlayersIndex();
                setStatus({ message: `Rebuilt player index: ${res.players} players, ${res.mappings} mappings.`, type: "success" });
                try { window.dispatchEvent(new CustomEvent("db-updated", { detail: { total } })); } catch {}
              };
              if ((window as any).requestIdleCallback) {
                (window as any).requestIdleCallback(() => { work(); });
              } else {
                // fallback delay
                setTimeout(() => { work(); }, 2000);
              }
            } catch (err) {
              console.error("scheduled rebuildPlayersIndex error", err);
            }
          };
          doRebuild();
        }
      } else if (msg.type === "error") {
        setStatus({ message: `Parse error: ${msg.message}`, type: "error" });
        worker.terminate();
        workerRef.current = null;
      }
    };

    if (opts?.fastImport) worker.postMessage({ raw, fastImport: true } as any);
    else worker.postMessage(raw);
    // Clear the input immediately to free memory and remove sensitive pasted data
    setDataInput("");
  };

  const handleClear = async () => {
    await clearDB();
    setStatus({ message: "Stored data cleared.", type: "success" });
    setProgress(0);
    setParsedCount(0);
  };

  // settings-driven handlers removed — settings UI no longer exposes proxy URL

  const handleRefreshNow = () => {
    (async () => {
      setRefreshBusy(true);
      setAutoStatus("refreshing now...");
      try {
        const res = await refreshNow();
        if (!res) {
          setAutoStatus("refresh failed");
          setLastError("refresh failed");
          setShowManual(true);
        } else if (res.ok && res.type === "fetched") {
          setAutoStatus(`refreshed (${res.detail?.viaProxy ? String(res.detail.viaProxy) : 'direct'})`);
          setLastRefreshTime(new Date());
          setLastSource(res.detail?.viaProxy ? String(res.detail.viaProxy) : 'direct');
        } else if (res.ok && res.type === "nochange") {
          setAutoStatus("no change");
        } else {
          setAutoStatus(`refresh result: ${res.type}`);
        }
      } catch (err) {
        const m = `refresh error: ${String(err)}`;
        setAutoStatus(m);
        setLastError(m);
        setShowManual(true);
      } finally {
        setRefreshBusy(false);
      }
    })();
  };

  // manual rebuild handler removed; index rebuilds are scheduled automatically when needed

  const statusColors = {
    error: "text-red-500",
    success: "text-green-500",
    info: "text-blue-500",
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 mb-6 shadow-sm">
      <h2 className="text-xl font-semibold mb-4">Load Projections Data</h2>

      {/* Instruction panel removed — automation handles fetching now */}

      <div className="flex gap-3 mb-4">
        <button
          onClick={handleClear}
          className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors"
        >
          Clear Stored Data
        </button>
        <div className="ml-4 flex items-center gap-2">
          <button onClick={handleRefreshNow} className="px-6 py-2 bg-indigo-600 text-white rounded-lg">
            {refreshBusy ? "Refreshing..." : "Refresh Data"}
          </button>
        </div>
      </div>
      {/* Compact status area */}
      <div className="mt-2 flex items-center justify-between">
        <div className="text-sm text-gray-300">
          {lastRefreshTime ? (
            <span>Last refresh: {lastRefreshTime.toLocaleString()} ({lastSource || 'direct'})</span>
          ) : (
            <span>No refresh yet</span>
          )}
          {lastError && <div className="text-xs text-red-400">Last error: {lastError}</div>}
        </div>
        <div>
          {!showManual && lastError && (
            <button onClick={() => setShowManual(true)} className="text-sm underline text-gray-300">Paste JSON manually</button>
          )}
        </div>
      </div>

      {/* Manual paste panel - hidden unless user needs it */}
      {showManual && (
        <>
          <textarea
            value={dataInput}
            onChange={(e) => setDataInput(e.target.value)}
            className="w-full px-4 py-3 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:ring-2 focus:ring-[#5D5CDE] focus:border-transparent font-mono text-sm mt-4"
            rows={8}
            placeholder='{"data": [...], "included": [...]}'
          />

          <div className="flex gap-3 mt-4">
            <button
              onClick={handleLoadData}
              className="px-6 py-2 bg-[#5D5CDE] hover:bg-[#4a49c9] text-white font-medium rounded-lg transition-colors"
            >
              Load Data
            </button>
            <button onClick={() => setShowManual(false)} className="px-4 py-2 border rounded">Hide</button>
          </div>
        </>
      )}

      {progress > 0 && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
            <div
              style={{ width: `${Math.round(progress * 100)}%` }}
              className="h-2 bg-[#5D5CDE]"
            />
          </div>
          <div className="text-sm mt-1">Saved: {parsedCount}</div>
        </div>
      )}

      {status && (
        <div className={`mt-3 text-sm ${statusColors[status.type]}`}>
          {status.message}
        </div>
      )}
      {autoStatus && (
        <div className="mt-2 text-xs text-gray-500">Auto: {autoStatus}</div>
      )}
    </div>
  );
}
