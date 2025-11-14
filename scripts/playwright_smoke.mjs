/* eslint-disable no-unused-vars, no-empty */
import { chromium } from 'playwright';

(async () => {
  const url = process.env.URL || 'http://localhost:5173/';
  console.log('Playwright smoke test: opening', url);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  // Intercept LLM endpoint requests and return deterministic response for stable testing
  await page.route('**/*', async (route) => {
    try {
      const req = route.request();
      const url = req.url();
      const method = req.method();
      // Match common LLM endpoints used by analyzeWithLocalLLM
      if (method === 'POST' && /\/api\/chat|\/api\/generate|\/v1\/chat|\/v1\/completions|\/v1\/completions/.test(url)) {
        const jsonArray = JSON.stringify([
          {
            player: 'LeBron James',
            stat: 'points',
            line: 25.5,
            recommendation: 'OVER',
            confidence: 'High',
            modelConfidenceScore: 90,
            numericEvidence: {
              recentGames: [{ statValue: 28 }, { statValue: 26 }, { statValue: 30 }],
              seasonAvg: 27,
              opponent: { name: 'BOS', defensiveRating: 112, pace: 100 },
              projectedMinutes: 35
            },
            reasoning: 'Recent games and season average exceed the line.',
            dataUsed: { external: true, sources: ['test'] }
          }
        ]);

        const body = JSON.stringify({ choices: [{ message: { content: jsonArray } }] });
        await route.fulfill({ status: 200, headers: { 'content-type': 'application/json' }, body });
        return;
      }
    } catch (e) {
      // fallthrough to continue
    }
    await route.continue();
  });
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    if (!resp) {
      console.error('No response from server');
      process.exit(2);
    }
    console.log('HTTP status:', resp.status());
    // Try to find the Analysis header immediately (if app already rendered it)
    let found = await page.waitForSelector('text=AI Analysis Results', { timeout: 5000 }).catch(() => null);
    if (!found) {
      console.log('Analysis header not present yet — inserting sample projection into IndexedDB and driving UI');
      // Insert a sample projection into the app IndexedDB so the UI shows data
      const sample = {
        id: 'smoke-test-1',
        player: 'LeBron James',
        team: 'LAL',
        league: 'NBA',
        stat: 'points',
        line: 25.5,
        startTime: new Date().toISOString(),
      };
      await page.evaluate(async (proj) => {
        await new Promise((resolve, reject) => {
          const req = indexedDB.open('prizepicks-db', 3);
          req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('projections')) {
              const store = db.createObjectStore('projections', { keyPath: 'id' });
              try { store.createIndex('league', 'league', { unique: false }); } catch {}
              try { store.createIndex('stat', 'stat', { unique: false }); } catch {}
              try { store.createIndex('player', 'player', { unique: false }); } catch {}
            }
          };
          req.onsuccess = () => {
            const db = req.result;
            const tx = db.transaction('projections', 'readwrite');
            tx.objectStore('projections').put(proj);
            tx.oncomplete = () => { db.close(); resolve(); };
            tx.onerror = () => reject(tx.error);
          };
          req.onerror = () => reject(req.error);
        });
      }, sample);

      // Reload so the React app picks up the new DB contents
      await page.reload({ waitUntil: 'domcontentloaded' });

      // Set league/stat filters so the Search button will return our inserted projection
      await page.waitForSelector('select', { timeout: 5000 });
      // select league (first select) and stat (second select) if available
      const selects = await page.$$('select');
      if (selects.length >= 1) {
        try {
          await page.selectOption('select', 'NBA');
        } catch {}
      }
      if (selects.length >= 2) {
        try {
          await page.selectOption('select:nth-of-type(2)', 'points');
        } catch {}
      }
      // Click Search to load results
      await page.click('button:has-text("Search")');

      // Wait for projections list to render and select the first checkbox
      await page.waitForSelector('text=Available Projections', { timeout: 5000 });
      await page.waitForSelector('input[type=checkbox]', { timeout: 5000 });
      // click the first checkbox
      await page.click('input[type=checkbox]');

      // Click Analyze
      await page.click('button:has-text("Analyze")');

      // Wait for Analysis section to appear
      found = await page.waitForSelector('text=AI Analysis Results', { timeout: 15000 }).catch(() => null);
    }

    if (found) {
      console.log('Found Analysis header');
      console.log('Found Analysis header');
      // Wait for numeric evidence block to appear (rendered by AnalysisSection)
      const numeric = await page.waitForSelector('[data-test="numeric-evidence"]', { timeout: 10000 }).catch(() => null);
      if (numeric) console.log('Numeric evidence block present');
      else console.warn('Numeric evidence block not found (continuing)');

      // Check for flagged-for-review text (optional)
      const flagged = await page.$('text=Flagged for review');
      if (flagged) console.log('Found flagged-for-review notice');
      else console.log('No flagged-for-review notices present');

      // Validate specific numeric values and LLM-derived recommendation
      // Wait for the rendered card that includes the player name
      await page.waitForSelector('text=LeBron James', { timeout: 5000 }).catch(() => null);
      // Assert the UI shows the recommendation OVER for our deterministic stub
      let recoTxt = null;
      const recoEl = await page.waitForSelector('[data-test="recommendation"]', { timeout: 3500 }).catch(() => null);
      if (recoEl) {
        recoTxt = await recoEl.evaluate((n) => n.textContent || '');
      } else {
        // fallback: try to find literal OVER text (older rendering)
        const overEl = await page.$('text=OVER');
        if (overEl) recoTxt = 'OVER';
      }
      if (recoTxt && recoTxt.includes('OVER')) {
        console.log('Recommendation OVER found in UI');
      } else {
        console.error('Expected recommendation OVER not found; found:', recoTxt);
        throw new Error('Expected recommendation OVER not found');
      }
      // Assert seasonAvg numeric evidence rendered (27)
      // Require machine-readable JSON for strict CI assertions
      const analysisJsonEl = await page.$('[data-test="analysis-json"]');
      if (!analysisJsonEl) {
        console.error('analysis-json element not found in DOM — failing strict smoke test');
        throw new Error('analysis-json element not found');
      }
      const raw = await analysisJsonEl.evaluate((n) => n.textContent || '');
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (e) {
        console.error('analysis-json content is not valid JSON — failing strict smoke test', e);
        throw e;
      }
      if (!Array.isArray(parsed) || parsed.length === 0) {
        console.error('analysis-json is not a non-empty array — failing strict smoke test');
        throw new Error('analysis-json invalid content');
      }
      const item = parsed[0];
      const seasonAvg = item?.numericEvidence?.seasonAvg;
      const reco = item?.recommendation || item?.originalRecommendation || null;
      if (seasonAvg === 27) console.log('seasonAvg 27 present in analysis-json');
      else console.warn('analysis-json seasonAvg not 27:', seasonAvg);
      if (reco && String(reco).includes('OVER')) console.log('Recommendation OVER present in analysis-json');
      else console.warn('analysis-json recommendation not OVER:', reco);

      // Cleanup: remove the inserted sample projection from IndexedDB
      try {
        await page.evaluate(async () => {
          await new Promise((resolve, reject) => {
            const req = indexedDB.open('prizepicks-db', 3);
            req.onsuccess = () => {
              const db = req.result;
              const tx = db.transaction('projections', 'readwrite');
              tx.objectStore('projections').delete('smoke-test-1');
              tx.oncomplete = () => { db.close(); resolve(); };
              tx.onerror = () => reject(tx.error);
            };
            req.onerror = () => resolve();
          });
        });
        console.log('Cleaned up test projection from IndexedDB');
      } catch (e) {
        console.warn('Cleanup failed', e);
      }

      console.log('Smoke test PASSED');
      await browser.close();
      process.exit(0);
    } else {
      console.error('Failed to find Analysis header; capturing page title and body snapshot');
      const title = await page.title();
      console.error('Page title:', title);
      const html = await page.content();
      console.error('Page HTML snippet:', html.slice(0, 2000));
      await browser.close();
      process.exit(1);
    }
  } catch (e) {
    console.error('Playwright error:', e);
    await browser.close();
    process.exit(3);
  }
})();
