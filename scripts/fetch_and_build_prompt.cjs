const url = require("url");

async function fetchJson(u) {
  const res = await fetch(u);
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
  return res.json();
}

function buildPromptFromSummary(summary) {
  const lines = [];
  lines.push(`Player: ${summary.player}`);
  lines.push(`Stat: ${summary.stat}`);
  if (summary.recent) lines.push(`Recent: ${summary.recent}`);
  if (summary.noGamesThisSeason) lines.push(`Note: ${summary.note}`);
  if (summary.seasonAvg !== undefined && summary.seasonAvg !== null)
    lines.push(`Season avg: ${summary.seasonAvg}`);
  if (Array.isArray(summary.recentGames) && summary.recentGames.length) {
    lines.push("Recent games:");
    for (const g of summary.recentGames) {
      lines.push(`- ${g.gameDate} ${g.matchup || ""} => ${g.statValue}`);
    }
  }
  lines.push(
    "\nAssistant: Using the numeric context above, analyze whether the projection is likely over or under, and explain reasoning with simple numeric comparisons and recent trends."
  );
  return lines.join("\n");
}

async function main() {
  const args = process.argv.slice(2);
  const player = args[0] || "LeBron James";
  const stat = args[1] || "points";
  const limit = args[2] || "5";
  const base = process.env.NBA_BACKEND || "http://127.0.0.1:3002";

  const q = new url.URL("/player_summary", base);
  q.searchParams.set("player", player);
  q.searchParams.set("stat", stat);
  q.searchParams.set("limit", limit);

  try {
    console.log(`Fetching ${q.toString()}...`);
    const summary = await fetchJson(q.toString());
    const prompt = buildPromptFromSummary(summary);
    console.log("\n=== GENERATED PROMPT ===\n");
    console.log(prompt);
  } catch (err) {
    console.error("Error fetching or building prompt:", err.message);
    process.exit(2);
  }
}

main();
