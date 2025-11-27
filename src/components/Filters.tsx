import { useEffect, useState, useRef } from "react";
import {
  getDistinctValues,
  getDistinctStatsByLeague,
  getDistinctLeaguesByStat,
  getPlayersWithCounts,
  getPlayerMappings,
} from "../services/indexedDBService";

interface FiltersProps {
  filters: { league: string; stat: string; search: string };
  onFilterChange: (_filters: {
    league: string;
    stat: string;
    search: string;
  }) => void;
  // Note: parameter name prefixed with underscore if unused
  onAnalyze: () => void;
  onSearch: () => void;
}

export default function Filters({
  filters: _filters,
  onFilterChange,
  onAnalyze,
  onSearch,
}: FiltersProps) {
  // map incoming prop to local name used throughout the component
  const filters = _filters;
  const [leagues, setLeagues] = useState<string[]>([]);
  const [stats, setStats] = useState<string[]>([]);
  const [players, setPlayers] = useState<{ name: string; count: number }[]>([]);

  const [playerQuery, setPlayerQuery] = useState<string>(filters.search || "");
  const [isOpen, setIsOpen] = useState(false);
  const [highlighted, setHighlighted] = useState<number>(-1);

  const [loading, setLoading] = useState(false);
  // (filters already mapped above)
  const containerRef = useRef<HTMLDivElement | null>(null);

  const debounceRef = useRef<number | null>(null);
  const statsTimer = useRef<number | null>(null);
  const leaguesTimer = useRef<number | null>(null);

  // initial load
  useEffect(() => {
    let mounted = true;
    (async () => {
      const [l, s] = await Promise.all([
        getDistinctValues("league"),
        getDistinctStatsByLeague(),
      ]);
      if (!mounted) return;
      setLeagues(l);
      setStats(s);
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // query players (debounced)
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current as any);
    setLoading(true);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const res = await getPlayersWithCounts(
          filters.league || undefined,
          filters.stat || undefined,
          playerQuery || undefined
        );
        setPlayers(res || []);
        setHighlighted(-1);
      } finally {
        setLoading(false);
      }
    }, 200) as unknown as number;
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current as any);
    };
  }, [playerQuery, filters.league, filters.stat]);

  // when a player is selected via filters.search (external), pre-filter leagues/stats
  useEffect(() => {
    let mounted = true;
    (async () => {
      // keep the local input in sync with external filter.search
      setPlayerQuery(filters.search || "");

      // if search was cleared, restore full league/stat lists (respect current league filter)
      if (!filters.search) {
        try {
          const [allLeagues, statsForLeague] = await Promise.all([
            getDistinctValues("league"),
            getDistinctStatsByLeague(filters.league || undefined),
          ]);
          if (!mounted) return;
          setLeagues(allLeagues);
          setStats(statsForLeague);
        } catch {
          // ignore
        }
        return;
      }

      // players loading state intentionally omitted to reduce noise
      try {
        const maps = await getPlayerMappings(filters.search);
        if (!mounted) return;
        const uniqueLeagues = Array.from(
          new Set(maps.map((m) => m.league).filter(Boolean))
        );
        const uniqueStats = Array.from(
          new Set(maps.map((m) => m.stat).filter(Boolean))
        );
        if (uniqueLeagues.length > 0) {
          setLeagues(uniqueLeagues);
          if (
            uniqueLeagues.length === 1 &&
            filters.league !== uniqueLeagues[0]
          ) {
            onFilterChange({ ...filters, league: uniqueLeagues[0] });
          }
        } else {
          const allLeagues = await getDistinctValues("league");
          if (!mounted) return;
          setLeagues(allLeagues);
        }
        if (uniqueStats.length > 0) {
          setStats(uniqueStats);
          if (filters.stat && uniqueStats.indexOf(filters.stat) === -1) {
            onFilterChange({ ...filters, stat: "" });
          }
        } else {
          const s = await getDistinctStatsByLeague(filters.league || undefined);
          if (!mounted) return;
          setStats(s);
        }
      } finally {
        // no-op
      }
    })();
    return () => {
      mounted = false;
    };
  }, [filters, filters.search, filters.league, filters.stat, onFilterChange]);

  // when league changes, update stats (debounced)
  useEffect(() => {
    if (statsTimer.current) window.clearTimeout(statsTimer.current as any);
    // stats loading state omitted to reduce noise
    statsTimer.current = window.setTimeout(() => {
      let mounted = true;
      (async () => {
        try {
          const s = await getDistinctStatsByLeague(filters.league || undefined);
          if (!mounted) return;
          setStats(s);
        } finally {
          // no-op
        }
      })();
      return () => {
        mounted = false;
      };
    }, 120) as unknown as number;
    return () => {
      if (statsTimer.current) window.clearTimeout(statsTimer.current as any);
    };
  }, [filters.league]);

  // when stat changes, update leagues (debounced)
  useEffect(() => {
    if (leaguesTimer.current) window.clearTimeout(leaguesTimer.current as any);
    // leagues loading state omitted to reduce noise
    leaguesTimer.current = window.setTimeout(() => {
      let mounted = true;
      (async () => {
        try {
          const l = await getDistinctLeaguesByStat(filters.stat || undefined);
          if (!mounted) return;
          setLeagues(l);
        } finally {
          // no-op
        }
      })();
      return () => {
        mounted = false;
      };
    }, 120) as unknown as number;
    return () => {
      if (leaguesTimer.current)
        window.clearTimeout(leaguesTimer.current as any);
    };
  }, [filters.stat]);

  // close dropdown when clicking outside
  useEffect(() => {
    function onDocClick(e: MouseEvent | TouchEvent) {
      const el = containerRef.current;
      if (!el) return;
      const target = e.target as Node | null;
      if (target && !el.contains(target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("touchstart", onDocClick);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("touchstart", onDocClick);
    };
  }, []);

  function clearAll() {
    setPlayerQuery("");
    onFilterChange({ league: "", stat: "", search: "" });
    setIsOpen(false);
    setHighlighted(-1);
  }

  function choosePlayer(name: string) {
    onFilterChange({ ...filters, search: name });
    setPlayerQuery(name);
    setIsOpen(false);
  }

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 mb-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
          <select
            value={filters.league}
            onChange={(e) =>
              onFilterChange({ ...filters, league: e.target.value })
            }
            className="w-full h-11 px-4 border dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 appearance-none"
          >
            <option value="">All Leagues</option>
            {leagues.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        <div>
          <select
            value={filters.stat}
            onChange={(e) =>
              onFilterChange({ ...filters, stat: e.target.value })
            }
            className="w-full h-11 px-4 border dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 appearance-none"
          >
            <option value="">All Stats</option>
            {stats.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="col-span-1 md:col-span-2">
          <div className="relative" ref={containerRef}>
            <div className="flex gap-3 items-center">
              <input
                value={playerQuery}
                onChange={(e) => setPlayerQuery(e.target.value)}
                onClick={() => setIsOpen(true)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setHighlighted((h) =>
                      Math.min(h + 1, Math.max(0, players.length - 1))
                    );
                    setIsOpen(true);
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setHighlighted((h) => Math.max(h - 1, 0));
                  } else if (e.key === "Enter") {
                    e.preventDefault();
                    if (highlighted >= 0 && highlighted < players.length) {
                      choosePlayer(players[highlighted].name);
                    } else {
                      onSearch();
                      setIsOpen(false);
                    }
                  } else if (e.key === "Escape") {
                    setIsOpen(false);
                  }
                }}
                placeholder="Search players"
                className="w-full h-11 px-4 border dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 placeholder-gray-400"
              />

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    onSearch();
                    setIsOpen(false);
                  }}
                  className="h-11 px-4 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm"
                >
                  Search
                </button>
                <button
                  onClick={() => {
                    onAnalyze();
                    setIsOpen(false);
                  }}
                  className="h-11 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm"
                >
                  Analyze
                </button>
                <button
                  onClick={clearAll}
                  className="h-11 px-4 bg-transparent border border-gray-700 dark:border-gray-500 text-gray-200 hover:bg-gray-700/30 rounded-lg text-sm"
                >
                  Clear
                </button>
              </div>
            </div>

            {isOpen && (
              <ul className="absolute z-50 mt-2 max-h-56 w-full overflow-auto rounded-lg shadow-lg bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600">
                {players
                  .filter((p) =>
                    p.name
                      .toLowerCase()
                      .includes((playerQuery || "").toLowerCase())
                  )
                  .slice(0, 100)
                  .map((p, idx) => (
                    <li
                      key={p.name}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        choosePlayer(p.name);
                      }}
                      onMouseEnter={() => setHighlighted(idx)}
                      className={`px-3 py-2 cursor-pointer flex justify-between items-center ${
                        highlighted === idx
                          ? "bg-gray-100 dark:bg-gray-600"
                          : "hover:bg-gray-50 dark:hover:bg-gray-600"
                      }`}
                    >
                      <span className="font-medium">{p.name}</span>
                      <span className="text-sm text-gray-500 ml-2">
                        {p.count ?? 0}
                      </span>
                    </li>
                  ))}
                {players.length === 0 && !loading && (
                  <li className="px-3 py-2 text-sm text-gray-500">
                    No players
                  </li>
                )}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
