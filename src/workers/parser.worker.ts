import type { ParsedProjection } from '../types';

// Worker receives raw JSON string and posts back chunk messages
self.onmessage = async (e: MessageEvent) => {
  const raw = e.data as string;
  try {
    const parsed = JSON.parse(raw);
    const list = Array.isArray(parsed.data) ? parsed.data : parsed;

    const included = parsed.included || [];
    // build lookup maps from included
    const players: Record<string, any> = {};
    const leagues: Record<string, string> = {};
    const games: Record<string, any> = {};

    included.forEach((item: any) => {
      if (item.type === 'new_player') {
        players[item.id] = {
          name: item.attributes?.name || 'Unknown',
          team: item.attributes?.team || 'Unknown',
          position: item.attributes?.position || 'Unknown'
        };
      } else if (item.type === 'league') {
        leagues[item.id] = item.attributes?.name || 'Unknown';
      } else if (item.type === 'game') {
        games[item.id] = {
          home: item.attributes?.home_team || 'Unknown',
          away: item.attributes?.away_team || 'Unknown'
        };
      }
    });

    const CHUNK = 500;
    for (let i = 0; i < list.length; i += CHUNK) {
      const chunk = list.slice(i, i + CHUNK).map((proj: any) => {
        const playerId = proj.relationships?.new_player?.data?.id;
        const leagueId = proj.relationships?.league?.data?.id;
        const gameId = proj.relationships?.game?.data?.id;

        const mapped: ParsedProjection = {
          id: proj.id,
          player: players[playerId]?.name || 'Unknown',
          team: players[playerId]?.team || 'Unknown',
          position: players[playerId]?.position || 'Unknown',
          league: leagues[leagueId] || 'Unknown',
          stat: proj.attributes?.stat_type || 'unknown',
          line: proj.attributes?.line_score ?? 0,
          startTime: proj.attributes?.start_time || '',
          status: proj.attributes?.status || 'unknown',
          gameId: gameId
        };
        return mapped;
      }).filter((p: ParsedProjection) => p.status === 'pre_game');

      self.postMessage({ type: 'chunk', chunk, progress: Math.min(1, (i + CHUNK) / list.length) });
      // yield
      await new Promise(r => setTimeout(r, 0));
    }

    self.postMessage({ type: 'done' });
  } catch (err: any) {
    self.postMessage({ type: 'error', message: err?.message || String(err) });
  }
};

export {};
