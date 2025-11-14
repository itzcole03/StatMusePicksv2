import React from 'react';
import { render, waitFor } from '@testing-library/react';
import AnalysisSection from '../AnalysisSection';
import { vi } from 'vitest';

// Mock aiService helpers similar to existing E2E test so parsedResults is produced
vi.mock('../../../src/services/aiService', async () => {
  return {
    buildAnalysisPromptAsync: vi.fn(async (projections: any[], _settings: any) => {
      const contexts: Record<string, any> = {};
      projections.forEach((p: any, idx: number) => {
        contexts[p.id] = {
          recentGames: [ { statValue: 10 + idx }, { statValue: 11 + idx } ],
          seasonAvg: 12 + idx,
          opponent: { name: 'Opp' },
          projectedMinutes: 30,
        };
      });
      return { prompt: 'fake', externalUsed: true, contexts };
    }),
    analyzeWithLocalLLM: vi.fn(async (prompt: string, settings: any, onChunk: (_c: string) => void) => {
      const arr = settings.testProjections.map((p: any, idx: number) => ({
        player: p.player,
        stat: p.stat,
        line: p.line,
        recommendation: 'OVER',
        confidence: 'High',
        modelConfidenceScore: 90,
        numericEvidence: {
          recentGames: [12 + idx, 13 + idx],
          // match the mocked contexts returned by buildAnalysisPromptAsync
          seasonAvg: 12 + idx,
          opponent: { name: 'Opp' },
          projectedMinutes: 30,
        },
        reasoning: 'test',
        dataUsed: { external: true, sources: ['test'] },
      }));
      onChunk(JSON.stringify(arr));
    }),
    scoreModelOutput: (parsed: any[]) => ({ items: parsed.map((p, i) => ({ index: i, match: true, heuristicScore: 80 })), agreement: 100 }),
  };
});

const sampleProjections = [
  { id: 'p1', player: 'Player One', stat: 'points', line: 10, team: 'T1', league: 'NBA', startTime: Date.now() },
];

describe('AnalysisSection analysis-json machine-readable blob', () => {
  it('renders a hidden analysis-json blob when parsedResults present', async () => {
    const settings: any = { llmEndpoint: 'http://local.test', llmModel: 'test', requireExternalData: true, testProjections: sampleProjections };
    const { container } = render(<AnalysisSection projections={sampleProjections as any} settings={settings} />);

    await waitFor(() => {
      const el = container.querySelector('[data-test="analysis-json"]');
      if (!el) throw new Error('analysis-json not found yet');
    }, { timeout: 2000 });

    const el = container.querySelector('[data-test="analysis-json"]') as HTMLElement | null;
    expect(el).not.toBeNull();
    const raw = el!.textContent || '';
    const parsed = JSON.parse(raw);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed.length).toBeGreaterThan(0);
    expect(parsed[0].numericEvidence).toBeDefined();
    expect(parsed[0].numericEvidence.seasonAvg).toBe(12);
    expect(parsed[0].recommendation).toBe('OVER');
  });
});
