import { useEffect, useState, useRef } from 'react';
import { getDistinctValues, getDistinctStatsByLeague, getDistinctLeaguesByStat, getPlayersWithCounts, getPlayerMappings } from '../services/indexedDBService';

interface FiltersProps {
  filters: { league: string; stat: string; search: string };
  onFilterChange: (filters: { league: string; stat: string; search: string }) => void;
  onAnalyze: () => void;
  onSearch: () => void;
}

export default function Filters({ filters, onFilterChange, onAnalyze, onSearch }: FiltersProps) {
  const [leagues, setLeagues] = useState<string[]>([]);
  const [stats, setStats] = useState<string[]>([]);
  const [players, setPlayers] = useState<{ name: string; count: number }[]>([]);
  const [playerQuery, setPlayerQuery] = useState<string>(filters.search || '');
  const [isOpen, setIsOpen] = useState(false);
  const [highlighted, setHighlighted] = useState<number>(-1);
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [leaguesLoading, setLeaguesLoading] = useState(false);
  const [playersLoading, setPlayersLoading] = useState(false);
  const debounceRef = useRef<number | null>(null);
  const statsTimer = useRef<number | null>(null);
  const leaguesTimer = useRef<number | null>(null);
  const statsAnimateTimer = useRef<number | null>(null);
  const leaguesAnimateTimer = useRef<number | null>(null);
  const playersAnimateTimer = useRef<number | null>(null);
  const [statsAnimating, setStatsAnimating] = useState(false);
  const [leaguesAnimating, setLeaguesAnimating] = useState(false);
  const [playersAnimating, setPlayersAnimating] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const l = await getDistinctValues('league');
      const s = await getDistinctStatsByLeague();
      const p = await getPlayersWithCounts();
      if (!mounted) return;
      setLeagues(l);
      setStats(s);
      setPlayers(p);
    })();
    return () => { mounted = false; };
  }, []);

  // When a player is selected (filters.search), auto-adjust league and available stats.
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!filters.search) return;
      setPlayersLoading(true);
      try {
        const maps = await getPlayerMappings(filters.search);
        if (!mounted) return;
        const uniqueLeagues = Array.from(new Set(maps.map(m => m.league).filter(Boolean)));
        const uniqueStats = Array.from(new Set(maps.map(m => m.stat).filter(Boolean)));

        // Update leagues list to only those relevant if we found any; otherwise restore full list
        if (uniqueLeagues.length > 0) {
          setLeagues(uniqueLeagues);
          // Auto-set league when it's unambiguous
          if (uniqueLeagues.length === 1 && filters.league !== uniqueLeagues[0]) {
            onFilterChange({ ...filters, league: uniqueLeagues[0] });
          }
        } else {
          const allLeagues = await getDistinctValues('league');
          if (!mounted) return;
          setLeagues(allLeagues);
        }

        // Update stat options to only those correlated with the selected player
        if (uniqueStats.length > 0) {
          setStats(uniqueStats);
          if (filters.stat && uniqueStats.indexOf(filters.stat) === -1) {
            onFilterChange({ ...filters, stat: '' });
          }
        } else {
          const s = await getDistinctStatsByLeague(filters.league || undefined);
          if (!mounted) return;
          setStats(s);
        }
      } finally {
        if (mounted) setPlayersLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [filters.search]);

  // If all filters are cleared, restore the full lists for leagues, stats, and players.
  useEffect(() => {
    let mounted = true;
    (async () => {
      if (filters.search || filters.league || filters.stat) return;
      setLeaguesLoading(true);
      setStatsLoading(true);
      setPlayersLoading(true);
      try {
        const [allLeagues, allStats, allPlayers] = await Promise.all([
          getDistinctValues('league'),
          getDistinctStatsByLeague(),
          getPlayersWithCounts()
        ]);
        if (!mounted) return;
        setLeagues(allLeagues);
        setStats(allStats);
        setPlayers(allPlayers);
      } finally {
        if (mounted) {
          setLeaguesLoading(false);
          setStatsLoading(false);
          setPlayersLoading(false);
        }
      }
    })();
    return () => { mounted = false; };
  }, [filters.search, filters.league, filters.stat]);

  // When league is changed, update available stats filtered by that league (debounced)
  useEffect(() => {
    if (statsTimer.current) window.clearTimeout(statsTimer.current as any);
    setStatsLoading(true);
    statsTimer.current = window.setTimeout(() => {
      let mounted = true;
      (async () => {
        try {
          const s = await getDistinctStatsByLeague(filters.league || undefined);
          if (!mounted) return;
          setStats(s);
          // animate a short fade when stats change
          setStatsAnimating(true);
          if (statsAnimateTimer.current) window.clearTimeout(statsAnimateTimer.current as any);
          statsAnimateTimer.current = window.setTimeout(() => setStatsAnimating(false), 220) as unknown as number;
          // keep current stat if still valid, otherwise clear it
          if (filters.stat && s.indexOf(filters.stat) === -1) {
            onFilterChange({ ...filters, stat: '' });
          }
        } finally {
          if (mounted) setStatsLoading(false);
        }
      })();
      return () => { mounted = false; };
    }, 120) as unknown as number;
    return () => {
      if (statsTimer.current) window.clearTimeout(statsTimer.current as any);
      setStatsLoading(false);
    };
  }, [filters.league]);

  // When stat is changed, update available leagues filtered by that stat (debounced)
  useEffect(() => {
    if (leaguesTimer.current) window.clearTimeout(leaguesTimer.current as any);
    setLeaguesLoading(true);
    leaguesTimer.current = window.setTimeout(() => {
      let mounted = true;
      (async () => {
        try {
          const l = await getDistinctLeaguesByStat(filters.stat || undefined);
          if (!mounted) return;
          setLeagues(l);
          // animate a short fade when leagues change
          setLeaguesAnimating(true);
          if (leaguesAnimateTimer.current) window.clearTimeout(leaguesAnimateTimer.current as any);
          leaguesAnimateTimer.current = window.setTimeout(() => setLeaguesAnimating(false), 220) as unknown as number;
          if (filters.league && l.indexOf(filters.league) === -1) {
            onFilterChange({ ...filters, league: '' });
          }
        } finally {
          if (mounted) setLeaguesLoading(false);
        }
      })();
      return () => { mounted = false; };
    }, 120) as unknown as number;
    return () => {
      if (leaguesTimer.current) window.clearTimeout(leaguesTimer.current as any);
      setLeaguesLoading(false);
    };
  }, [filters.stat]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setPlayersLoading(true);
      try {
        const p = await getPlayersWithCounts(filters.league || undefined, filters.stat || undefined);
        if (!mounted) return;
        setPlayers(p);
        // animate players list change
        setPlayersAnimating(true);
        if (playersAnimateTimer.current) window.clearTimeout(playersAnimateTimer.current as any);
        playersAnimateTimer.current = window.setTimeout(() => setPlayersAnimating(false), 220) as unknown as number;
        // If current selected player is no longer present, clear selection
        if (filters.search && p.findIndex(x => x.name === filters.search) === -1) {
          onFilterChange({ ...filters, search: '' });
          setPlayerQuery('');
        }
      } finally {
        if (mounted) setPlayersLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [filters.league, filters.stat]);

  function doQuery(q: string) {
    setLoading(true);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      const res = await getPlayersWithCounts(filters.league || undefined, filters.stat || undefined, q);
      setPlayers(res);
      setLoading(false);
      setIsOpen(true);
      debounceRef.current = null;
    }, 250) as unknown as number;
  }

  function clearAll() {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    setPlayerQuery('');
    setIsOpen(false);
    setHighlighted(-1);
    onFilterChange({ league: '', stat: '', search: '' });
  }

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 mb-6 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">League</label>
          <div className={`relative transition-opacity duration-200 ${leaguesLoading ? 'opacity-60' : leaguesAnimating ? 'opacity-90' : 'opacity-100'}`}>
            <select
              value={filters.league}
              onChange={(e) => onFilterChange({ ...filters, league: e.target.value })}
              className="w-full px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
            >
              <option value="">All Leagues</option>
              {leagues.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            {leaguesLoading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <svg className="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
              </div>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Stat Type</label>
          <div className={`relative transition-opacity duration-200 ${statsLoading ? 'opacity-60' : statsAnimating ? 'opacity-90' : 'opacity-100'}`}>
            <select
              value={filters.stat}
              onChange={(e) => onFilterChange({ ...filters, stat: e.target.value })}
              className="w-full px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
            >
              <option value="">All Stats</option>
              {stats.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            {statsLoading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <svg className="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
              </div>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Search Player</label>
          <div className="flex flex-col gap-2">
            <div className="relative">
              <input
                type="text"
                value={playerQuery}
                onChange={(e) => { setPlayerQuery(e.target.value); doQuery(e.target.value); onFilterChange({ ...filters, search: e.target.value }); }}
                onKeyDown={(e) => {
                  const filtered = players.filter(p => p.name.toLowerCase().includes((playerQuery || '').toLowerCase()));
                  if (e.key === 'ArrowDown') { e.preventDefault(); setHighlighted(h => Math.min(h + 1, filtered.length - 1)); }
                  if (e.key === 'ArrowUp') { e.preventDefault(); setHighlighted(h => Math.max(h - 1, 0)); }
                  if (e.key === 'Enter') {
                    (async () => {
                      if (highlighted >= 0) {
                        const sel = filtered[highlighted];
                        if (sel) {
                          setPlayerQuery(sel.name);
                          try {
                            const maps = await getPlayerMappings(sel.name);
                            const uniqueLeagues = Array.from(new Set(maps.map(m => m.league).filter(Boolean)));
                            const uniqueStats = Array.from(new Set(maps.map(m => m.stat).filter(Boolean)));
                            const next = { ...filters, search: sel.name };
                            if (uniqueLeagues.length === 1) next.league = uniqueLeagues[0];
                            if (uniqueStats.length === 1) next.stat = uniqueStats[0];
                            onFilterChange(next);
                          } catch (err) {
                            onFilterChange({ ...filters, search: sel.name });
                          }
                        }
                      } else {
                        onSearch();
                      }
                      setIsOpen(false);
                    })();
                  }
                }}
                placeholder="Type to filter players"
                className="w-64 px-4 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
              />

              {loading && (
                <div className="absolute right-3 top-1/2 -mt-2">
                  <svg className="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
                  </svg>
                </div>
              )}

              {isOpen && (
                <ul className="absolute z-50 mt-2 max-h-56 w-full overflow-auto rounded-lg shadow-lg bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600">
                  {players.filter(p => p.name.toLowerCase().includes((playerQuery || '').toLowerCase())).slice(0,50).map((p, idx) => (
                    <li
                      key={p.name}
                      onMouseDown={async (e) => {
                        e.preventDefault();
                        setPlayerQuery(p.name);
                        try {
                          const maps = await getPlayerMappings(p.name);
                          const uniqueLeagues = Array.from(new Set(maps.map(m => m.league).filter(Boolean)));
                          const uniqueStats = Array.from(new Set(maps.map(m => m.stat).filter(Boolean)));
                          const next = { ...filters, search: p.name };
                          if (uniqueLeagues.length === 1) next.league = uniqueLeagues[0];
                          if (uniqueStats.length === 1) next.stat = uniqueStats[0];
                          onFilterChange(next);
                        } catch (err) {
                          onFilterChange({ ...filters, search: p.name });
                        }
                        setIsOpen(false);
                      }}
                      onMouseEnter={() => setHighlighted(idx)}
                      className={`px-3 py-2 cursor-pointer ${highlighted === idx ? 'bg-gray-100 dark:bg-gray-600' : 'hover:bg-gray-50 dark:hover:bg-gray-600'}`}
                    >
                      <span className="font-medium">{p.name}</span>
                      <span className="text-sm text-gray-500 ml-2">({p.count || 0})</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className={`relative transition-opacity duration-200 ${playersLoading ? 'opacity-60' : playersAnimating ? 'opacity-90' : 'opacity-100'}`}>
              <select
                value={filters.search}
                onChange={async (e) => {
                  const val = e.target.value;
                  setPlayerQuery(val);
                  if (val) {
                    try {
                      const maps = await getPlayerMappings(val);
                      const uniqueLeagues = Array.from(new Set(maps.map(m => m.league).filter(Boolean)));
                      const uniqueStats = Array.from(new Set(maps.map(m => m.stat).filter(Boolean)));
                      const next = { ...filters, search: val };
                      if (uniqueLeagues.length === 1) next.league = uniqueLeagues[0];
                      if (uniqueStats.length === 1) next.stat = uniqueStats[0];
                      onFilterChange(next);
                    } catch (err) {
                      onFilterChange({ ...filters, search: val });
                    }
                  } else {
                    onFilterChange({ ...filters, search: '' });
                  }
                  setIsOpen(false);
                }}
                className="h-10 w-64 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700"
              >
                <option value="">All Players</option>
                {players.map(p => <option key={p.name} value={p.name}>{p.name} ({p.count || 0})</option>)}
              </select>
              {playersLoading && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <svg className="animate-spin h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-end">
          <div className="flex w-full gap-3">
            <button onClick={onSearch} className="flex-1 px-6 py-2 bg-[#22c55e] hover:bg-[#16a34a] text-white font-medium rounded-lg">Show Results</button>
            <button onClick={onAnalyze} className="flex-1 px-6 py-2 bg-[#5D5CDE] hover:bg-[#4a49c9] text-white font-medium rounded-lg">Analyze Selected</button>
          </div>
        </div>
      </div>

      {/* Clear button sits between stacked controls and actions */}
      <div className="mt-3 flex">
        <div className="flex-1" />
        <div>
          <button onClick={clearAll} className="h-10 px-4 py-2 border border-gray-300 rounded-lg bg-white dark:bg-gray-700">Clear</button>
        </div>
      </div>
    </div>
  );
}
