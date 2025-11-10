import { ParsedProjection, Settings } from '../types';
import { buildExternalContextForProjections } from './nbaService';

export function buildAnalysisPrompt(projections: ParsedProjection[]): string {
  let prompt = `You are an expert sports analyst with deep knowledge of player statistics and performance trends. I need you to analyze the following PrizePicks projections and provide data-driven recommendations.

For each projection, please:
1. Research the player's recent performance (last 5-10 games)
2. Consider their season averages
3. Analyze opponent matchup data
4. Factor in home/away performance, recent trends, and any relevant context
5. Provide a clear OVER or UNDER recommendation with confidence level (High/Medium/Low)

Here are the projections to analyze:

`;

  projections.forEach((proj, idx) => {
    prompt += `**Projection ${idx + 1}:**
- Player: ${proj.player} (${proj.team})
- League: ${proj.league}
- Stat Type: ${proj.stat}
- Line: ${proj.line}
- Game Time: ${new Date(proj.startTime).toLocaleString()}

`;
  });

  prompt += `
Please provide your analysis in the following format for each projection:

### [Player Name] - [Stat Type]: O/U [Line]

**Recommendation:** OVER/UNDER
**Confidence:** High/Medium/Low

**Recent Performance:**
[Last 5-10 games summary with actual stats]

**Season Average:**
[Season stats for this specific stat type]

**Key Factors:**
- [Factor 1: e.g., Opponent defensive ranking]
- [Factor 2: e.g., Home/away splits]
- [Factor 3: e.g., Recent injury status or form]

**Analysis:**
[Your detailed reasoning in 2-3 sentences]

---

Be thorough but concise. Use real statistical data when available. If you can't find specific data, acknowledge it and base your recommendation on general knowledge and trends.`;

  return prompt;
}

// A smaller helper that returns a JSON schema/instruction to enforce structured output and guardrails
function buildOutputSchema() {
  return `
Strict output requirements and guardrails:

- Output MUST be valid JSON array where each element corresponds to one projection in the same order as provided.
- Each element must have the following keys: ` + '`player`,`stat`,`line`,`recommendation`,`confidence`,`numericEvidence`,`reasoning`,`dataUsed`' + `.
 - ` + '`numericEvidence`' + ` is an object with optional keys ` + '`recentGames`,`seasonAvg`,`opponent`,`projectedMinutes`' + `; do NOT invent numeric values. If numeric data is unavailable, set those fields to null and do NOT fabricate numbers.
- ` + '`recommendation`' + ` must be either "OVER" or "UNDER".
- ` + '`confidence`' + ` must be one of "High","Medium","Low". If numeric evidence is missing, prefer "Low" confidence.
- ` + '`dataUsed`' + ` is an object: { external: true|false, sources: [string...] } indicating whether external numeric context was used.
- ` + '`reasoning`' + ` must be a concise (1-3 sentence) explanation referencing only the provided external numericEvidence and qualitative signals; do NOT claim facts that are not present in numericEvidence or the projection data.

If you cannot make a clear recommendation due to insufficient data, set ` + '`recommendation`' + ` to null and ` + '`confidence`' + ` to "Low" and explain in ` + '`reasoning`' + ` what is missing.

Additionally, include ` + '`modelConfidenceScore`' + `: an integer from 0-100 representing the model's numeric confidence in this recommendation. Include it in each element at the top-level.
`;
}


// Note: deterministic baseline logic was removed per request — analyses must rely only on trusted external data and the LLM.

// Async prompt builder that will attempt to enrich each projection with external
// player context (from the NBA proxy) when settings are present.
export async function buildAnalysisPromptAsync(
  projections: ParsedProjection[],
  settings: Settings
): Promise<{ prompt: string; externalUsed: boolean; contexts?: Record<string, any> }> {
  const base = buildAnalysisPrompt(projections);
  // If no settings provided, return base prompt immediately
  if (!settings) return { prompt: base, externalUsed: false };

  try {
    const contexts = await buildExternalContextForProjections(projections, settings);
    // Build a deterministic structured block including only the trusted fields. This reduces hallucination risk.
    const trustedBlockLines: string[] = [];
    let used = false;
    projections.forEach((p, idx) => {
      const ctx = contexts[p.id] || null;
      // Include only fields we trust: recentGames (array of numeric statValue), seasonAvg, opponent, projectedMinutes
      const numericRecent = (ctx && Array.isArray(ctx.recentGames) && ctx.recentGames.length > 0) ? ctx.recentGames.map((g: any) => ({ date: g.date || g.gameDate || null, statValue: g.statValue != null ? Number(g.statValue) : null })) : null;
      const seasonAvg = ctx && ctx.seasonAvg != null ? Number(ctx.seasonAvg) : null;
      const opponent = ctx && ctx.opponent ? {
        name: ctx.opponent.name || null,
        defensiveRating: ctx.opponent.defensiveRating != null ? Number(ctx.opponent.defensiveRating) : null,
        pace: ctx.opponent.pace != null ? Number(ctx.opponent.pace) : null
      } : null;
      const projectedMinutes = ctx && ctx.projectedMinutes != null ? Number(ctx.projectedMinutes) : null;
      const noGamesThisSeason = !!(ctx && ctx.noGamesThisSeason);
      const notes = ctx && ctx.notes ? String(ctx.notes) : null;

      if (numericRecent || seasonAvg != null || opponent || projectedMinutes != null) used = true;

      trustedBlockLines.push(JSON.stringify({ index: idx + 1, id: p.id, player: p.player, stat: p.stat, line: p.line, numericRecent, seasonAvg, opponent, projectedMinutes, noGamesThisSeason, notes }));
    });

    // Compose the extra instructions: trusted data block + output schema + guardrails
    // Add strict markers and short examples to reduce formatting issues and improve model quality.
    const examples = [
      {
        example: {
          player: 'Example Player',
          stat: 'points',
          line: 10,
          recommendation: 'OVER',
          confidence: 'High',
          modelConfidenceScore: 85,
          numericEvidence: { recentGames: [{ statValue: 12 }, { statValue: 15 }], seasonAvg: 13.5, opponent: { name: 'Opp', defensiveRating: 110, pace: 100 }, projectedMinutes: 30 },
          reasoning: 'Recent games and season average both exceed the line.',
          dataUsed: { external: true, sources: ['nba'] }
        }
      },
      {
        example: {
          player: 'Example Player 2',
          stat: 'rebounds',
          line: 8,
          recommendation: null,
          confidence: 'Low',
          modelConfidenceScore: 20,
          numericEvidence: { recentGames: null, seasonAvg: null, opponent: null, projectedMinutes: null },
          reasoning: 'No numeric evidence available for this player this season.',
          dataUsed: { external: false, sources: [] }
        }
      }
    ];

    const extra = `
  ---

  Trusted external numeric context (do NOT invent additional numeric values):
  ${trustedBlockLines.join('\n')}

  ${buildOutputSchema()}

  To reduce formatting errors, when you respond output ONLY a single JSON array wrapped between the markers

  <JSON_OUTPUT>
  YOUR_JSON_ARRAY_HERE
  </JSON_OUTPUT>

  Do NOT include additional commentary outside the markers.

  Follow this short rubric when producing recommendations (use these programmatic signals):
  - If recentGames or seasonAvg exceed the line by a meaningful margin (see heuristic below), prefer OVER with higher "modelConfidenceScore".
  - If recent and season are below the line, prefer UNDER.
  - If numeric evidence is missing, set recommendation to null and confidence to Low.

  Heuristic for confidence (model use only):
  - High: average(stat) is >= line + 2 OR strong recent trend above line.
  - Medium: average(stat) is within ±2 of line.
  - Low: average(stat) is >= line -2 and <= line +2 or missing evidence.

  Examples (JSON):
  ${examples.map(e => JSON.stringify(e.example, null, 2)).join('\n\n')}

  Instructions for using the new fields:
  - "opponent" is an object with "name", "defensiveRating", and "pace". If opponent.defensiveRating is high (worse defense), increase expectation for offensive stats; if pace is high, expect more counting stats.
  - "projectedMinutes" is the model's expected minutes for the player; treat minutes as multiplicative weight for counting stats. If "projectedMinutes" is missing or null, note that in "numericEvidence.projectedMinutes" and reduce confidence.
  - In your JSON output include "numericEvidence.opponent" and "numericEvidence.projectedMinutes" with the exact values from the trusted context or null if absent.

  Respond using ONLY the projection list above and the trusted external numeric context. If numeric evidence is missing, set numericEvidence fields to null and set recommendation to null with Low confidence. Do NOT add or invent numeric facts.
  `;

    return { prompt: base + extra, externalUsed: used, contexts };
  } catch (err) {
    return { prompt: base, externalUsed: false };
  }
}

// Post-process and score model output against trusted numeric context.
export function scoreModelOutput(parsed: any[], projections: ParsedProjection[], contextsMap: Record<string, any> | null) {
  const items = parsed.map((it, idx) => {
    const p = projections[idx];
    const ctx = contextsMap ? contextsMap[p.id] : null;

    const trustedAvg = (() => {
      if (ctx && Array.isArray(ctx.recentGames) && ctx.recentGames.length > 0) {
        const vals = ctx.recentGames.map((g:any) => Number(g.statValue)).filter((v:any)=>!isNaN(v));
        if (vals.length) return vals.reduce((a:number,b:number)=>a+b,0)/vals.length;
      }
      if (ctx && ctx.seasonAvg != null) return Number(ctx.seasonAvg);
      return null;
    })();

    const expectedRec = trustedAvg == null ? null : (trustedAvg >= (p.line as number) ? 'OVER' : 'UNDER');

    const modelRec = it.recommendation;
    const match = expectedRec === modelRec;

    // heuristic confidence estimation
    let heuristicScore = 20;
    if (trustedAvg != null) {
      const diff = Math.abs(trustedAvg - (p.line as number));
      if (diff >= 2) heuristicScore = 80;
      else if (diff >= 0.5) heuristicScore = 50;
      else heuristicScore = 25;
    }

    const modelScore = typeof it.modelConfidenceScore === 'number' ? Number(it.modelConfidenceScore) : null;

    return { index: idx, expectedRec, modelRec, match, trustedAvg, heuristicScore, modelScore };
  });

  const matches = items.filter(i => i.match).length;
  const agreement = Math.round((matches / items.length) * 100);
  return { items, agreement };
}

export async function analyzeWithLocalLLM(
  prompt: string,
  settings: Settings,
  onChunk: (chunk: string) => void
): Promise<void> {
  // Build candidate endpoints to try when the configured endpoint doesn't match the server
  const buildCandidates = (base: string) => {
    try {
      const url = new URL(base);
      const origin = url.origin;
      const candidates = [base];
      // Common OpenAI-compatible and Ollama endpoints
      candidates.push(origin + '/api/chat');
      candidates.push(origin + '/api/generate');
      candidates.push(origin + '/v1/chat/completions');
      candidates.push(origin + '/v1/completions');
      candidates.push(origin + '/models');
      return Array.from(new Set(candidates));
    } catch (e) {
      return [base];
    }
  };

  const candidates = buildCandidates(settings.llmEndpoint);
  const decoder = new TextDecoder();
  const errors: string[] = [];

  for (const endpoint of candidates) {
    try {
      // Try OpenAI chat-compatible body first
      const chatBody = JSON.stringify({
        model: settings.llmModel,
        messages: [
          { role: 'system', content: 'You are an expert sports analyst with deep knowledge of player statistics and performance trends.' },
          { role: 'user', content: prompt }
        ],
        stream: true
      });

      let response: Response | null = null;
      try {
        response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: chatBody });
      } catch (e) {
        // network-level error
        errors.push(`Network error to ${endpoint}: ${String(e)}`);
        response = null;
      }

      if (!response) continue;

      // 200-level OK - handle stream or non-stream
      if (!response.ok) {
        // collect body for diagnostics
        let txt = '';
        try { txt = await response.text(); } catch (e) { txt = String(e); }
        errors.push(`Endpoint ${endpoint} returned ${response.status}: ${txt}`);
        continue;
      }

      const contentType = response.headers.get('content-type') || '';

      // If it's a stream (SSE or chunked), parse lines and JSON shapes
      if (contentType.includes('text/event-stream') || contentType.includes('stream') || contentType.includes('application/x-ndjson')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body (stream)');

        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split(/\r?\n/);
          buf = parts.pop() || '';
          for (const part of parts) {
            const line = part.trim();
            if (!line) continue;
            const data = line.startsWith('data:') ? line.replace(/^data:\s*/, '') : line;
            if (data === '[DONE]') continue;
            try {
              const json = JSON.parse(data);
              if (json.message?.content) onChunk(json.message.content);
              else if (json.choices && json.choices[0]?.delta?.content) onChunk(json.choices[0].delta.content);
              else if (json.choices && json.choices[0]?.message?.content) onChunk(json.choices[0].message.content);
              else if (json.results && json.results[0]?.content) onChunk(json.results[0].content);
              else if (json.completion?.content) onChunk(json.completion.content);
              else if (typeof json === 'string') onChunk(json as unknown as string);
            } catch (e) {
              if (data) onChunk(data);
            }
          }
        }
        if (buf.trim()) {
          try {
            const j = JSON.parse(buf);
            if (j.message?.content) onChunk(j.message.content);
          } catch {}
        }
        return;
      }

      // Fallback: try to parse JSON body (non-stream)
      try {
        const json = await response.json();
        if (json.choices && json.choices[0]?.message?.content) { onChunk(json.choices[0].message.content); return; }
        if (json.results && json.results[0]?.content) { onChunk(json.results[0].content); return; }
        if (json.choices && json.choices[0]?.text) { onChunk(json.choices[0].text); return; }
        // try Ollama generate shape: { output: [...] } or { text: '...' }
        if (json.output && Array.isArray(json.output) && json.output[0]?.content) { onChunk(json.output[0].content); return; }
        if (json.text) { onChunk(json.text); return; }
        // final fallback: stringify
        onChunk(JSON.stringify(json));
        return;
      } catch (e) {
        // if parsing fails, return the raw text
        try { const txt = await response.text(); onChunk(txt); return; } catch (_) { throw new Error('Unable to parse response from ' + endpoint); }
      }
    } catch (err) {
      errors.push(String(err));
      continue;
    }
  }

  // if we reach here, none of the candidate endpoints worked
  throw new Error('All endpoints failed. Diagnostics: ' + errors.join(' | '));
}

// Try to discover available models from a local LLM endpoint.
// Tries a few common endpoints derived from the provided llmEndpoint.
export async function discoverModels(llmEndpoint: string): Promise<string[]> {
  const candidates = new Set<string>();
  try {
    const url = new URL(llmEndpoint);
    const origin = url.origin;
    // common paths
    const paths = ['/models', '/api/models', '/v1/models', '/models/list'];
    for (const p of paths) {
      candidates.add(origin + p);
    }
    // also try the exact endpoint if it looks like a base list
    candidates.add(llmEndpoint);
  } catch (e) {
    // not a URL, try raw candidates
    candidates.add(llmEndpoint);
  }

  const found = new Set<string>();
  for (const candidate of candidates) {
    try {
      const resp = await fetch(candidate, { method: 'GET' });
      if (!resp.ok) continue;
      const ct = resp.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const json = await resp.json();
        // try common shapes
        if (Array.isArray(json)) {
          json.forEach((m: any) => {
            if (typeof m === 'string') found.add(m);
            else if (m?.name) found.add(m.name);
            else if (m?.id) found.add(m.id);
          });
        } else if (json?.models && Array.isArray(json.models)) {
          json.models.forEach((m: any) => { if (m?.name) found.add(m.name); else if (m?.id) found.add(m.id); });
        } else if (json?.results && Array.isArray(json.results)) {
          // Ollama or similar may return { results: [...] }
          json.results.forEach((r: any) => { if (r?.model) found.add(r.model); });
        } else if (json?.name) {
          found.add(json.name);
        }
      } else {
        // if plain text, try to parse lines
        const text = await resp.text();
        text.split(/\r?\n/).map(s => s.trim()).filter(Boolean).forEach(s => found.add(s));
      }
    } catch (err) {
      // ignore and try next
    }
  }

  return Array.from(found).sort();
}

// Probe candidate endpoints and return the first working endpoint plus any discovered models.
export async function findWorkingEndpoint(llmEndpoint: string): Promise<{ endpoint: string; models: string[] } | null> {
  const candidates = new Set<string>();
  try {
    const url = new URL(llmEndpoint);
    const origin = url.origin;
    const paths = ['/models', '/api/models', '/v1/models', '/models/list', '/api/chat', '/api/generate', '/v1/chat/completions', '/v1/completions'];
    for (const p of paths) candidates.add(origin + p);
    candidates.add(llmEndpoint);
  } catch (e) {
    candidates.add(llmEndpoint);
  }

  // Prefer endpoints that accept generation POSTs. For each candidate, try POST first (chat-style),
  // and if it returns a generation-like response, choose it. If none accept POST, fall back to
  // GET endpoints that list models.
  let fallbackModels: string[] = [];
  for (const candidate of candidates) {
    // Try POST (OpenAI chat-style). Many Ollama installs accept /api/chat or /v1/chat/completions etc.
    try {
      const chatBody = JSON.stringify({ model: 'test', messages: [{ role: 'user', content: 'ping' }], stream: false });
      const resp = await fetch(candidate, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: chatBody });
      if (resp.ok) {
        // parse JSON if possible and look for generation shapes
        try {
          const ct = resp.headers.get('content-type') || '';
          let json: any = null;
          if (ct.includes('application/json')) json = await resp.json();
          else {
            const txt = await resp.text();
            try { json = JSON.parse(txt); } catch { json = null; }
          }
          // heuristics for a generation response
          const hasGeneration = !!(json && (json.choices || json.message || json.response || json.id || json.output));
          let models: string[] = [];
          // try to extract any models mentioned in the response
          if (json) {
            if (Array.isArray(json)) json.forEach((m: any) => { if (typeof m === 'string') models.push(m); else if (m?.name) models.push(m.name); else if (m?.id) models.push(m.id); });
            else if (json?.models && Array.isArray(json.models)) json.models.forEach((m: any) => { if (m?.name) models.push(m.name); else if (m?.id) models.push(m.id); });
            else if (json?.model) models.push(json.model);
            else if (json?.results && Array.isArray(json.results)) json.results.forEach((r: any) => { if (r?.model) models.push(r.model); });
          }
          if (hasGeneration) return { endpoint: candidate, models };
        } catch (e) {
          // parsing error - still consider a 200 as success for POST
          return { endpoint: candidate, models: [] };
        }
      }
    } catch (e) {
      // ignore POST error and continue to try GET below
    }

    // If POST didn't succeed, try GET for model listing and collect as fallback
    try {
      const respGet = await fetch(candidate, { method: 'GET' });
      if (respGet.ok) {
        try {
          const ct = respGet.headers.get('content-type') || '';
          if (ct.includes('application/json')) {
            const json = await respGet.json();
            const models: string[] = [];
            if (Array.isArray(json)) json.forEach((m: any) => { if (typeof m === 'string') models.push(m); else if (m?.name) models.push(m.name); else if (m?.id) models.push(m.id); });
            else if (json?.models && Array.isArray(json.models)) json.models.forEach((m: any) => { if (m?.name) models.push(m.name); else if (m?.id) models.push(m.id); });
            else if (json?.data && Array.isArray(json.data)) json.data.forEach((d: any) => { if (d?.id) models.push(d.id); });
            if (models.length) fallbackModels = models;
            // do not immediately return - prefer POST endpoints above
          } else {
            // text listing
            const text = await respGet.text();
            const lines = text.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
            if (lines.length) fallbackModels = lines;
          }
        } catch (e) {
          // ignore parse errors
        }
      }
    } catch (e) {
      // ignore GET error
    }
  }

  if (fallbackModels.length) {
    // if we only found a models listing, return the base listing endpoint as a fallback
    // try to return the canonical /v1/models if reachable
    try {
      const base = new URL(llmEndpoint).origin + '/v1/models';
      return { endpoint: base, models: fallbackModels };
    } catch (e) {
      return { endpoint: llmEndpoint, models: fallbackModels };
    }
  }

  return null;
}

// Run a small non-stream test request against the endpoint to verify connectivity and the selected model.
export async function testModelEndpoint(llmEndpoint: string, model: string): Promise<{ ok: boolean; status: number; body: any }>{
  try {
    const body = JSON.stringify({ model, messages: [{ role: 'user', content: 'hello' }], stream: false });
    const resp = await fetch(llmEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    const ct = resp.headers.get('content-type') || '';
    let parsed: any = null;
    try {
      if (ct.includes('application/json')) parsed = await resp.json();
      else parsed = await resp.text();
    } catch (e) {
      parsed = await resp.text();
    }
    return { ok: resp.ok, status: resp.status, body: parsed };
  } catch (err: any) {
    return { ok: false, status: 0, body: String(err?.message || err) };
  }
}
