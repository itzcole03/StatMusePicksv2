import { describe, it, expect } from 'vitest';
import { validateOutput } from '../src/services/analysisValidator';

const sampleProjection = [{ id: 'p1', player: 'John Doe', stat: 'points', line: 20 }];

const contexts = {
  p1: {
    recentGames: [{ date: '2025-11-01', statValue: 18 }, { date: '2025-11-03', statValue: 22 }],
    seasonAvg: 19.5,
    opponent: { name: 'Rival', defensiveRating: 105.2, pace: 99.1 },
    projectedMinutes: 32
  }
};

describe('validateOutput', () => {
  it('accepts valid matching numericEvidence', () => {
    const arr = [{
      player: 'John Doe', stat: 'points', line: 20, recommendation: 'OVER', confidence: 'High',
      numericEvidence: { recentGames: [{ statValue: 18 }, { statValue: 22 }], seasonAvg: 19.5, opponent: { name: 'Rival', defensiveRating: 105.2, pace: 99.1 }, projectedMinutes: 32 },
      reasoning: 'Because recent games and season average support it.', dataUsed: { external: true, sources: ['nba'] }
    }];

    const res = validateOutput(arr as any, sampleProjection as any, contexts as any);
    expect(res.ok).toBe(true);
  });

  it('flags seasonAvg that is too far from trusted context', () => {
    const arr = [{
      player: 'John Doe', stat: 'points', line: 20, recommendation: 'OVER', confidence: 'High',
      numericEvidence: { recentGames: [{ statValue: 18 }, { statValue: 22 }], seasonAvg: 40 },
      reasoning: 'Erroneous season avg', dataUsed: { external: true, sources: [] }
    }];

    const res = validateOutput(arr as any, sampleProjection as any, contexts as any);
    expect(res.ok).toBe(false);
    expect(res.reasons.some(r => r.includes('seasonAvg'))).toBe(true);
  });

  it('flags missing recentGames values', () => {
    const arr = [{
      player: 'John Doe', stat: 'points', line: 20, recommendation: 'OVER', confidence: 'High',
      numericEvidence: { recentGames: [{ statValue: 99 }] , seasonAvg: 19.5 },
      reasoning: 'Bad recent', dataUsed: { external: true, sources: [] }
    }];

    const res = validateOutput(arr as any, sampleProjection as any, contexts as any);
    expect(res.ok).toBe(false);
    expect(res.reasons.some(r => r.includes('recentGames'))).toBe(true);
  });
});
