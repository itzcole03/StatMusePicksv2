import { describe, it, expect, vi } from 'vitest';
import { buildAnalysisPromptAsync } from '../src/services/aiService';
import * as nbaService from '../src/services/nbaService';

const sampleProjections = [{ id: 'p1', player: 'John Doe', team: 'ABC', league: 'NBA', stat: 'points', line: 20, startTime: new Date().toISOString() } as any];

describe('buildAnalysisPromptAsync', () => {
  it('includes opponent and projectedMinutes in trusted block when available', async () => {
    // mock buildExternalContextForProjections used by aiService to return enriched context
    vi.spyOn(nbaService, 'buildExternalContextForProjections' as any).mockResolvedValueOnce({
      p1: {
        recentGames: [{ date: '2025-11-01', statValue: 18 }],
        seasonAvg: 19.5,
        opponent: { name: 'Rival', defensiveRating: 105.2, pace: 99.1 },
        projectedMinutes: 32
      }
    });

    const settings = { llmEndpoint: 'http://localhost:3002', llmModel: 'test' } as any;
    const { prompt, externalUsed, contexts } = await buildAnalysisPromptAsync(sampleProjections as any, settings as any) as any;
    expect(externalUsed).toBe(true);
    expect(prompt).toContain('projectedMinutes');
    expect(prompt).toContain('opponent');
    expect(contexts.p1.opponent.name).toBe('Rival');
  });
});
