/* eslint-env node */
/* global __dirname, console */
const fs = require("fs");
const path = require("path");

function buildBasePrompt(projections) {
  let prompt = `You are an expert sports analyst with deep knowledge of player statistics and performance trends. I need you to analyze the following PrizePicks projections and provide data-driven recommendations.\n\n`;
  projections.forEach((proj, idx) => {
    prompt += `Projection ${idx + 1}:\n- Player: ${proj.player} (${
      proj.team
    })\n- League: ${proj.league}\n- Stat Type: ${proj.stat}\n- Line: ${
      proj.line
    }\n- Game Time: ${new Date(proj.startTime).toLocaleString()}\n\n`;
  });
  return prompt;
}

function mockedContextsFor(projections) {
  const ctx = {};
  projections.forEach((p) => {
    if (p.player === "LeBron James") {
      ctx[p.id] = {
        recentGames: [28, 32, 25, 30, 26],
        seasonAvg: 27.8,
        recent: "28, 32, 25, 30, 26",
      };
    } else if (p.player === "Stephen Curry") {
      ctx[p.id] = {
        recentGames: [30, 29, 35, 22, 31],
        seasonAvg: 29.4,
        recent: "30, 29, 35, 22, 31",
      };
    } else {
      ctx[p.id] = null;
    }
  });
  return ctx;
}

function buildPromptWithContexts(base, projections, contexts) {
  let extra = "\n---\nExternal data (mocked NBA contexts):\n\n";
  projections.forEach((p, idx) => {
    const c = contexts[p.id];
    extra += `Projection ${idx + 1}: ${p.player} - ${p.stat}\n`;
    if (!c) {
      extra += "- No external data available.\n\n";
      return;
    }
    if (c.recentGames && Array.isArray(c.recentGames)) {
      extra += `- Recent numeric values (most recent first): [${c.recentGames.join(
        ", "
      )}]\n`;
      if (c.seasonAvg != null) extra += `- Recent average: ${c.seasonAvg}\n`;
    } else if (c.recent) {
      extra += `- Recent: ${c.recent}\n`;
    }
    extra += "\n";
  });
  return base + extra;
}

function main() {
  const file = path.join(__dirname, "sample_projections.json");
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  const base = buildBasePrompt(data);
  const contexts = mockedContextsFor(data);
  const full = buildPromptWithContexts(base, data, contexts);
  console.log(full);
}

main();
