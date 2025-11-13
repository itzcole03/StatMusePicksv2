import { initDB, clearDB, saveBatch, saveNbaContexts, getProjectionsByIds } from '../src/services/indexedDBService';

describe('saveNbaContexts integration', () => {
  beforeEach(async () => {
    await initDB();
    await clearDB();
  });

  it('persists contextualFactors and sets fetchedAt', async () => {
    const proj = { id: 'p1', player: 'Player One', league: 'NBA', stat: 'pts' } as any;
    await saveBatch([proj]);

    const ctx = { contextualFactors: { daysRest: 0, isBackToBack: true } };
    await saveNbaContexts({ p1: ctx });

    const res = await getProjectionsByIds(['p1']);
    expect(res.length).toBe(1);
    const saved = res[0];
    expect(saved.nbaContext).toBeDefined();
    expect(saved.nbaContext.contextualFactors).toEqual(ctx.contextualFactors);
    expect(saved.nbaContext.fetchedAt).toBeDefined();
  });
});
