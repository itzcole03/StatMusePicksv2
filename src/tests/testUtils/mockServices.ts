// Centralized mocks for component tests that need external NBA/AI services.
// Importing this module registers `vi.mock` handlers so tests can import
// components without hitting real network or LLM endpoints.

// Note: This file is intended to be imported at the very top of a test
// file before importing the component under test so vitest picks up the
// module mocks.

vi.mock('../../services/nbaService', () => ({
  buildExternalContextForProjections: async (projs: any[], _settings: any) => {
    const contexts: Record<string, any> = {};
    for (const p of projs) {
      contexts[p.id] = {
        player: p.player,
        stat: p.stat,
        recentGames: [
          { date: '2025-11-01', statValue: 20 },
          { date: '2025-10-30', statValue: 25 },
          { date: '2025-10-28', statValue: 18 },
        ],
        seasonAvg: 21.0,
        rollingAverages: { last_3_avg: 21.0, ema_5: 20.5 },
        fetchedAt: new Date().toISOString(),
      };
    }
    return contexts;
  },
  fetchPlayerContextFromNBA: async (proj: any, _settings: any) => {
    return {
      player: proj.player,
      stat: proj.stat,
      recentGames: [
        { date: '2025-11-01', statValue: 20 },
        { date: '2025-10-30', statValue: 25 },
        { date: '2025-10-28', statValue: 18 },
      ],
      seasonAvg: 21.0,
      rollingAverages: { last_3_avg: 21.0, ema_5: 20.5 },
      fetchedAt: new Date().toISOString(),
    };
  },
}));

vi.mock('../../services/aiService', () => ({
  analyzeWithLocalLLM: async (_prompt: string, _settings: any, onChunk: any) => {
    const arr = [
      {
        player: 'Test Player',
        stat: 'points',
        line: 20,
        recommendation: 'OVER',
        confidence: 'High',
        numericEvidence: { recentGames: null, seasonAvg: null, opponent: null, projectedMinutes: null },
        reasoning: 'Test',
      },
    ];
    onChunk(JSON.stringify(arr));
  },
  buildAnalysisPromptAsync: async (projs: any[], _settings: any) => {
    const nba: any = await vi.importMock('../../services/nbaService');
    const contexts = await nba.buildExternalContextForProjections(projs, _settings);
    return { prompt: 'ok', externalUsed: true, contexts };
  },
  scoreModelOutput: (parsed: any[], _projections: any[], _contextsMap: Record<string, any> | null) => {
    const items = parsed.map((p, idx) => ({ index: idx, expectedRec: null, modelRec: p.recommendation || null, match: true, trustedAvg: null, heuristicScore: 50, modelScore: p.modelConfidenceScore || null }));
    return { items, agreement: 100 };
  }
}));

vi.mock('../../services/aiService.v2', () => ({ buildPredictionFromFeatures: (_player: string) => ({ recommendation: 'OVER', calibratedConfidence: 70 }) }));

vi.mock('../../services/analysisValidator', () => ({ validateOutput: () => ({ ok: true }) }));

vi.mock('../../services/indexedDBService', () => ({ saveNbaContexts: async () => {} }));

export {};
