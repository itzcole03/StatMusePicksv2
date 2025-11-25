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

function App() {
  const [projectionsData, setProjectionsData] = useState<ParsedProjection[]>(
    []
  );
  const [selectedProjections, setSelectedProjections] = useState<Set<string>>(new Set());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>({
    aiProvider: "backend",
    llmEndpoint: "",
    llmModel: "",
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
  const [analysisProjections, setAnalysisProjections] = useState<ParsedProjection[]>([]);
  const [analysisVisible, setAnalysisVisible] = useState(false);
  const [sessionModel, setSessionModel] = useState<string | null>(null);

  const handleProjectionToggle = (id: string, checked: boolean) => {
    setSelectedProjections((prev) => {
      const newSet = new Set(prev);
      if (checked) newSet.add(id);
      else newSet.delete(id);
      return newSet;
    });
  };

  const handleAnalyze = async () => {
    if (selectedProjections.size === 0) {
      alert("Please select at least one projection to analyze.");
      return;
    }
    if (selectedProjections.size > 10) {
      alert("Please select no more than 10 projections at a time for optimal analysis.");
      return;
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
      const items = await getProjectionsByIds(ids);
      try {
        const contexts = await buildExternalContextForProjections(items, settings);
        await saveNbaContexts(contexts);
        const merged = items.map((it) => ({ ...it, nbaContext: contexts[it.id] || it.nbaContext || null }));
        setAnalysisProjections(merged);
      } catch {
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

  useEffect(() => {
    const refreshCounts = async () => {
      const total = await countAll();
      setTotalProjectionsCount(total);
      const players = await getDistinctValues("player");
      setTotalPlayersCount(players.length);
      const leagues = await getDistinctValues("league");
      setTotalLeaguesCount(leagues.length);
    };
    refreshCounts();
    const handler = () => refreshCounts();
    window.addEventListener("db-updated", handler as EventListener);
    const modelHandler = (e: any) => {
      try {
        const m = e?.detail?.model;
        if (m) setSessionModel(m);
      } catch {}
    };
    window.addEventListener("llm-model-applied", modelHandler as EventListener);
    return () => {
      window.removeEventListener("db-updated", handler as EventListener);
      window.removeEventListener("llm-model-applied", modelHandler as EventListener);
    };
  }, []);

  return (
    <div className="min-h-screen bg-white dark:bg-[#181818] text-gray-900 dark:text-gray-100">
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <Header onOpenSettings={() => setIsSettingsOpen(true)} />

        <DataLoader />

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
                settings={{ ...settings, llmModel: sessionModel || settings.llmModel }}
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
