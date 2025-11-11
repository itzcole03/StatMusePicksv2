import { useCallback, useEffect, useState } from "react";
import Header from "./components/Header";
import DataLoader from "./components/DataLoader";
import Filters from "./components/Filters";
import StatsSection from "./components/StatsSection";
import ProjectionsTable from "./components/ProjectionsTable";
import AnalysisSection from "./components/AnalysisSection";
import SettingsModal from "./components/SettingsModal";
import { ParsedProjection, Settings } from "./types";
import {
  queryProjections,
  countAll,
  getDistinctValues,
  getProjectionsByIds,
  saveNbaContexts,
} from "./services/indexedDBService";
import { buildExternalContextForProjections } from "./services/nbaService";
import { findWorkingEndpoint } from "./services/aiService";

function App() {
  const [projectionsData, setProjectionsData] = useState<ParsedProjection[]>(
    []
  );
  const [selectedProjections, setSelectedProjections] = useState<Set<string>>(
    new Set()
  );
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>({
    aiProvider: "local",
    llmEndpoint: "http://localhost:11434/api/chat",
    llmModel: "llama3.2:latest",
    requireExternalData: false,
  });
  const [filters, setFilters] = useState({
    league: "",
    stat: "",
    search: "",
  });
  const [totalMatched, setTotalMatched] = useState(0);
  const [offset, setOffset] = useState(0);
  const PAGE_SIZE = 50;
  const [totalProjectionsCount, setTotalProjectionsCount] = useState(0);
  const [totalPlayersCount, setTotalPlayersCount] = useState(0);
  const [totalLeaguesCount, setTotalLeaguesCount] = useState(0);
  const [analysisProjections, setAnalysisProjections] = useState<
    ParsedProjection[]
  >([]);
  const [analysisVisible, setAnalysisVisible] = useState(false);
  // session-level override for selected model (applies immediately but not persisted)
  const [sessionModel, setSessionModel] = useState<string | null>(null);

  // DataLoader writes to IndexedDB directly; App will query DB when filters change

  const handleProjectionToggle = (id: string, checked: boolean) => {
    setSelectedProjections((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(id);
      } else {
        newSet.delete(id);
      }
      return newSet;
    });
  };

  const handleAnalyze = async () => {
    if (selectedProjections.size === 0) {
      alert("Please select at least one projection to analyze.");
      return;
    }
    if (selectedProjections.size > 10) {
      alert(
        "Please select no more than 10 projections at a time for optimal analysis."
      );
      return;
    }

    // Try to auto-detect a working endpoint/model before analysis so users don't have to open Settings.
    try {
      const probe = await findWorkingEndpoint(settings.llmEndpoint);
      if (probe) {
        const updated = {
          ...settings,
          llmEndpoint: probe.endpoint,
          llmModel: (probe.models && probe.models[0]) || settings.llmModel,
        };
        setSettings(updated);
        try {
          window.dispatchEvent(
            new CustomEvent("llm-model-applied", {
              detail: { model: updated.llmModel },
            })
          );
        } catch {}
      }
    } catch {
      // ignore detection errors; analysis will proceed and may fail with diagnostics shown in UI
    }

    setAnalysisVisible(true);
  };

  useEffect(() => {
    if (!analysisVisible) return;
    (async () => {
      const ids = Array.from(selectedProjections);
      if (ids.length === 0) {
        setAnalysisProjections([]);
        return;
      }
      // Pre-warm NBA contexts for the selected projections to ensure analysis prompts
      // have the freshest available numeric context and the UI shows badges quickly.
      const items = await getProjectionsByIds(ids);
      try {
        const contexts = await buildExternalContextForProjections(
          items,
          settings
        );
        // persist contexts into IndexedDB so subsequent UI renders pick them up
        await saveNbaContexts(contexts);
        // merge contexts into the in-memory items for immediate use
        const merged = items.map((it) => ({
          ...it,
          nbaContext: contexts[it.id] || it.nbaContext || null,
        }));
        setAnalysisProjections(merged);
      } catch {
        // if pre-warm fails, fall back to items without contexts
        setAnalysisProjections(items);
      }
    })();
  }, [analysisVisible, selectedProjections, settings]);

  const loadFirstPage = useCallback(async () => {
    setOffset(0);
    const hasFiltersLocal = !!(filters.league || filters.stat || filters.search);
    if (!hasFiltersLocal) {
      setProjectionsData([]);
      setTotalMatched(0);
      return;
    }
    const res = await queryProjections(
      {
        league: filters.league || undefined,
        stat: filters.stat || undefined,
        playerName: filters.search || undefined,
      },
      0,
      PAGE_SIZE
    );
    setProjectionsData(res.items);
    setTotalMatched(res.totalMatched);
    setOffset(res.items.length);
  }, [filters]);

  const loadMore = useCallback(async () => {
    const res = await queryProjections(
      {
        league: filters.league || undefined,
        stat: filters.stat || undefined,
        playerName: filters.search || undefined,
      },
      offset,
      PAGE_SIZE
    );
    setProjectionsData((prev) => [...prev, ...res.items]);
    setOffset((prev) => prev + res.items.length);
  }, [filters, offset]);

  // Results are loaded explicitly via the Filters "Show Results" button (onSearch)

  useEffect(() => {
    const refreshCounts = async () => {
      const total = await countAll();
      setTotalProjectionsCount(total);
      const players = await getDistinctValues("player");
      setTotalPlayersCount(players.length);
      const leagues = await getDistinctValues("league");
      setTotalLeaguesCount(leagues.length);
    };

    // refresh on mount
    refreshCounts();

    // also refresh when DB signals updates
    const handler = () => {
      refreshCounts();
    };
    window.addEventListener("db-updated", handler as EventListener);
    // listen for model-applied events from SettingsModal (applies for this session only)
    const modelHandler = (e: any) => {
      try {
        const m = e?.detail?.model;
        if (m) setSessionModel(m);
      } catch {
        // ignore
      }
    };
    window.addEventListener("llm-model-applied", modelHandler as EventListener);
    return () => {
      window.removeEventListener("db-updated", handler as EventListener);
      window.removeEventListener(
        "llm-model-applied",
        modelHandler as EventListener
      );
    };
  }, []);

  return (
    <div className="min-h-screen bg-white dark:bg-[#181818] text-gray-900 dark:text-gray-100">
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <Header onOpenSettings={() => setIsSettingsOpen(true)} />

        <DataLoader />

        {/* show filters/stats/table when there is at least some stored data */}
        {totalProjectionsCount > 0 && (
          <>
            <Filters
              filters={filters}
              onFilterChange={setFilters}
              onAnalyze={handleAnalyze}
              onSearch={loadFirstPage}
            />

            <StatsSection
              totalProjections={totalProjectionsCount}
              totalPlayers={totalPlayersCount}
              totalLeagues={totalLeaguesCount}
            />

            <ProjectionsTable
              projections={projectionsData}
              total={totalMatched}
              selectedProjections={selectedProjections}
              onProjectionToggle={handleProjectionToggle}
              loadMore={loadMore}
              settings={settings}
            />

            {analysisVisible && (
              <AnalysisSection
                projections={analysisProjections}
                settings={{
                  ...settings,
                  llmModel: sessionModel || settings.llmModel,
                }}
              />
            )}
          </>
        )}

        <SettingsModal
          isOpen={isSettingsOpen}
          settings={settings}
          onClose={() => setIsSettingsOpen(false)}
          onSave={setSettings}
        />
      </div>
    </div>
  );
}

export default App;
