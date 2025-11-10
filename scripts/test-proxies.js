async function test() {
  const players = ['LeBron James', 'Stephen Curry'];
  for (const player of players) {
    try {
      console.log(`\nTesting NBA proxy for ${player}`);
      const nbaRes = await fetch(`http://localhost:3000/api/nba/player_summary?player=${encodeURIComponent(player)}&stat=points&limit=5`);
      console.log('NBA status:', nbaRes.status);
      const nj = await nbaRes.json();
      console.log('NBA body sample:', JSON.stringify(nj, null, 2).slice(0, 1000));
    } catch (e) {
      console.error('NBA proxy error:', e);
    }

    try {
      console.log(`\nTesting StatMuse proxy for ${player}`);
      const smRes = await fetch(`http://localhost:3000/api/statmuse?player=${encodeURIComponent(player)}&stat=points&limit=5`);
      console.log('StatMuse status:', smRes.status);
      const sj = await smRes.json();
      console.log('StatMuse body sample:', JSON.stringify(sj, null, 2).slice(0, 1000));
    } catch (e) {
      console.error('StatMuse proxy error:', e);
    }
  }
}

if (typeof fetch === 'undefined') {
  console.error('Node version does not have global fetch. Use Node 18+ or run via a fetch polyfill.');
  process.exit(1);
}

test();
