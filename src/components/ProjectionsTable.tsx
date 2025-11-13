import React, { useState, useEffect, useRef, useCallback } from "react";
import { Settings } from "../types";
import { buildExternalContextForProjections } from "../services/nbaService";
import { FixedSizeList as List } from "react-window";
import { ParsedProjection } from "../types";

interface ProjectionsTableProps {
  projections: ParsedProjection[];
  total: number;
  selectedProjections: Set<string>;
  onProjectionToggle: (_id: string, _checked: boolean) => void;
  // parameter names prefixed with underscore are acceptable for type-only positions
  loadMore: () => Promise<void>;
  settings?: Settings;
}

const ROW_HEIGHT = 64;

export default function ProjectionsTable({
  projections,
  total,
  selectedProjections,
  onProjectionToggle,
  loadMore,
  settings,
}: ProjectionsTableProps) {
  // Build grouped projection entries keyed by player+stat
  type Group = {
    key: string;
    items: ParsedProjection[];
    rep: ParsedProjection; // representative (most recent)
    count: number;
    minLine: number;
    maxLine: number;
    avgLine: number;
  };

  const groups: Group[] = (() => {
    const map = new Map<string, ParsedProjection[]>();
    for (const p of projections) {
      const key = `${p.player}||${p.stat}`;
      const list = map.get(key) || [];
      list.push(p);
      map.set(key, list);
    }
    const out: Group[] = [];
    for (const [key, items] of map.entries()) {
      // compute aggregates and pick most recent as representative
      let latest = items[0];
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      let sum = 0;
      for (const it of items) {
        const val = Number(it.line) || 0;
        if (val < min) min = val;
        if (val > max) max = val;
        sum += val;
        try {
          if (
            new Date(it.startTime).getTime() >
            new Date(latest.startTime).getTime()
          )
            latest = it;
        } catch {
          // ignore
        }
      }
      if (!isFinite(min)) min = 0;
      if (!isFinite(max)) max = 0;
      const avg = items.length ? +(sum / items.length).toFixed(2) : 0;
      out.push({
        key,
        items,
        rep: latest,
        count: items.length,
        minLine: min,
        maxLine: max,
        avgLine: avg,
      });
    }
    return out;
  })();

  const [showAll, setShowAll] = useState<boolean>(false);
  const [modalGroup, setModalGroup] = useState<Group | null>(null);
  const [nbaContexts, setNbaContexts] = useState<Record<string, any>>({});
  const fetchedIds = useRef<Set<string>>(new Set());
  const fetchTimer = useRef<any>(null);

  const markFetched = useCallback((ids: string[]) => {
    for (const id of ids) fetchedIds.current.add(id);
  }, []);

  const scheduleFetchForRange = useCallback(
    (visibleProjs: ParsedProjection[]) => {
      // debounce rapid scroll events
      if (fetchTimer.current) clearTimeout(fetchTimer.current);
      fetchTimer.current = setTimeout(async () => {
        const toFetch = visibleProjs.filter(
          (p) => !fetchedIds.current.has(p.id)
        );
        if (toFetch.length === 0) return;
        try {
          const ctxs = await buildExternalContextForProjections(
            toFetch as ParsedProjection[],
            settings as any
          );
          setNbaContexts((prev) => ({ ...prev, ...ctxs }));
          markFetched(toFetch.map((t) => t.id));
        } catch {
          // ignore fetch errors
        }
      }, 250);
    },
    [markFetched, settings]
  );

  useEffect(() => {
    return () => {
      if (fetchTimer.current) clearTimeout(fetchTimer.current);
    };
  }, []);
  // Use flexible columns (fr units) so columns scale with available width and remain aligned
  const GRID_TEMPLATE = "48px 2fr 1fr 1fr 1fr 0.7fr 1fr auto";

  // Outer element for react-window list so we can apply matching padding
  const OuterElement = React.forwardRef<HTMLDivElement, any>((props, ref) => {
    const { style, children, ...rest } = props;
    return (
      <div
        ref={ref}
        {...rest}
        className="px-6"
        style={{ ...(style || {}), overflowY: "scroll" }}
      >
        {children}
      </div>
    );
  });

  const RowContainer = ({
    children,
    style,
  }: {
    children: any;
    style?: any;
  }) => (
    <div
      className="grid items-center border-b border-gray-100 dark:border-gray-700"
      style={{
        ...(style || {}),
        gridTemplateColumns: GRID_TEMPLATE,
        alignItems: "center",
      }}
    >
      {children}
    </div>
  );
  const ItemRow = ({ proj, style }: { proj: ParsedProjection; style: any }) => {
    if (!proj) return <div style={style} />;

    const time = new Date(proj.startTime).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });

    return (
      <RowContainer style={style}>
        <div className="pl-1">
          <input
            type="checkbox"
            checked={selectedProjections.has(proj.id)}
            onChange={(e) => onProjectionToggle(proj.id, e.target.checked)}
            className="w-5 h-5 text-[#5D5CDE] rounded focus:ring-[#5D5CDE] cursor-pointer"
          />
        </div>
        <div className="font-medium text-left flex items-center gap-2">
          <span>{proj.player}</span>
          {(proj.nbaContext?.noGamesThisSeason ||
            nbaContexts[proj.id]?.noGamesThisSeason) && (
            <span
              title="No recent games this season"
              className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
            >
              No recent
            </span>
          )}
        </div>
        <div className="text-left">{proj.team}</div>
        <div className="text-left">
          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-[#5D5CDE] bg-opacity-10 text-[#5D5CDE]">
            {proj.league}
          </span>
        </div>
        <div className="text-left">{proj.stat}</div>
        <div className="text-xl font-extrabold text-gray-900 dark:text-white text-right">
          {proj.line}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">{time}</div>
        <div />
      </RowContainer>
    );
  };

  const GroupRow = ({ group, style }: { group: Group; style: any }) => {
    const proj = group.rep;
    const time = new Date(proj.startTime).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
    const allSelected = group.items.every((i) => selectedProjections.has(i.id));
    const toggleGroup = (checked: boolean) => {
      // select/deselect all items in the group
      for (const it of group.items) {
        onProjectionToggle(it.id, checked);
      }
    };
    return (
      <RowContainer style={style}>
        <div className="pl-1">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => toggleGroup(e.target.checked)}
            className="w-5 h-5 text-[#5D5CDE] rounded focus:ring-[#5D5CDE] cursor-pointer"
          />
        </div>
        <div className="font-medium text-left flex items-center gap-2">
          <span>{proj.player}</span>
          {(proj.nbaContext?.noGamesThisSeason ||
            nbaContexts[proj.id]?.noGamesThisSeason) && (
            <span
              title="No recent games this season"
              className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
            >
              No recent
            </span>
          )}
        </div>
        <div className="text-left">{proj.team}</div>
        <div className="text-left">
          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-[#5D5CDE] bg-opacity-10 text-[#5D5CDE]">
            {proj.league}
          </span>
        </div>
        <div className="text-left">{proj.stat}</div>
        <div className="text-xl font-extrabold text-gray-900 dark:text-white text-right">
          {proj.line}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">{time}</div>
        <div className="ml-3 text-sm font-medium text-gray-200 dark:text-gray-300 flex items-center gap-3">
          <span>{group.count} variants</span>
          <span>avg {group.avgLine}</span>
          <span>
            {group.minLine}/{group.maxLine}
          </span>
          <button
            onClick={() => setModalGroup(group)}
            className="text-sm px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded"
          >
            View
          </button>
        </div>
      </RowContainer>
    );
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden mb-6">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 className="text-xl font-semibold">Available Projections</h2>
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {showAll ? projections.length : groups.length} shown ({total} total)
        </span>
      </div>
      <div>
        <div className="px-6 py-3 flex items-center justify-between">
          <div />
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-500">Collapse duplicates</label>
            <button
              onClick={() => setShowAll((s) => !s)}
              className="px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded"
            >
              {showAll ? "Show collapsed" : "Show all"}
            </button>
          </div>
        </div>
        {/* Column header to keep alignment with rows */}
        <div
          className="grid text-xs text-gray-400 dark:text-gray-300 px-6"
          style={{ gridTemplateColumns: GRID_TEMPLATE, alignItems: "center" }}
        >
          <div />
          <div className="font-medium text-left">Player</div>
          <div className="text-left">Team</div>
          <div className="text-left">League</div>
          <div className="text-left">Stat</div>
          <div className="text-right">Line</div>
          <div className="text-left">Start Time</div>
          <div />
        </div>
        <div style={{ scrollbarGutter: "stable" as any }}>
          <List
            height={Math.min(
              600,
              (showAll ? projections.length : groups.length) * ROW_HEIGHT
            )}
            itemCount={showAll ? projections.length : groups.length}
            itemSize={ROW_HEIGHT}
            width="100%"
            outerElementType={OuterElement}
            onItemsRendered={(params: any) => {
              const { visibleStartIndex, visibleStopIndex } = params;
              const start = visibleStartIndex ?? 0;
              const stop = visibleStopIndex ?? 0;
              let visibleProjs: ParsedProjection[] = [];
              if (showAll) {
                visibleProjs = projections.slice(start, stop + 1);
              } else {
                visibleProjs = groups.slice(start, stop + 1).map((g) => g.rep);
              }
              if (visibleProjs.length) scheduleFetchForRange(visibleProjs);
            }}
          >
            {({ index, style }: { index: number; style: any }) => {
              if (showAll) {
                const proj = projections[index];
                return <ItemRow proj={proj} style={style} />;
              }
              const group = groups[index];
              return <GroupRow group={group} style={style} />;
            }}
          </List>
        </div>
      </div>

      <div className="p-4 border-t border-gray-100 dark:border-gray-700 flex justify-center">
        {projections.length < total ? (
          <button
            onClick={loadMore}
            className="px-6 py-2 bg-[#5D5CDE] hover:bg-[#4a49c9] text-white rounded-lg"
          >
            Load more
          </button>
        ) : (
          <div className="text-sm text-gray-500">No more results</div>
        )}
      </div>
      {modalGroup && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-xl w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">
                Variants for {modalGroup.rep.player} — {modalGroup.rep.stat}
              </h3>
              <button
                onClick={() => setModalGroup(null)}
                className="text-gray-500"
              >
                Close
              </button>
            </div>
            <div className="space-y-2 max-h-96 overflow-auto">
              {modalGroup.items.map((it) => (
                <div
                  key={it.id}
                  className="flex items-center px-3 py-2 border-b border-gray-100 dark:border-gray-700"
                >
                  <input
                    type="checkbox"
                    checked={selectedProjections.has(it.id)}
                    onChange={(e) =>
                      onProjectionToggle(it.id, e.target.checked)
                    }
                    className="mr-3"
                  />
                  <div className="flex-1">
                    <div className="font-medium">
                      {it.player} — {it.stat}
                    </div>
                    <div className="text-sm text-gray-400 dark:text-gray-300">
                      {it.team} •{" "}
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {it.line}
                      </span>{" "}
                      • {new Date(it.startTime).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setModalGroup(null)}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
