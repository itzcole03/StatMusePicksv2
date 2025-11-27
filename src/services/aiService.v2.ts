// Enhanced aiService v2: statistical helpers and prediction interface
export interface PredictionResult {
  player: string;
  stat: string;
  line: number;

  overProbability: number; // 0-1
  underProbability: number; // 0-1
  calibratedConfidence: number; // 0-100

  modelPredictions?: Record<string, number>;

  evidence: {
    mean: number | null;
    median: number | null;
    std: number | null;
    trendSlope: number | null;
    confidenceInterval: [number, number] | null;
    sampleSize: number;
  };

  recommendation: "OVER" | "UNDER" | null;
  expectedValue: number | null;
}

// Calculate statistical evidence from recent numeric values
export function calculateStatisticalEvidence(
  recentGames: number[] | null
): PredictionResult["evidence"] {
  if (!recentGames || recentGames.length === 0) {
    return {
      mean: null,
      median: null,
      std: null,
      trendSlope: null,
      confidenceInterval: null,
      sampleSize: 0,
    };
  }
  const n = recentGames.length;
  const mean = recentGames.reduce((a, b) => a + b, 0) / n;
  const sorted = [...recentGames].sort((a, b) => a - b);
  const median = sorted[Math.floor(n / 2)];
  const variance =
    recentGames.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / n;
  const std = Math.sqrt(variance);
  // simple linear trend slope (least squares)
  const xMean = (n - 1) / 2;
  const numerator = recentGames.reduce(
    (s, y, x) => s + (x - xMean) * (y - mean),
    0
  );
  const denominator =
    recentGames.reduce((s, _, x) => s + Math.pow(x - xMean, 2), 0) || 1;
  const trendSlope = numerator / denominator;
  const margin = 1.96 * (std / Math.sqrt(n));
  const ci: [number, number] = [mean - margin, mean + margin];
  return {
    mean,
    median,
    std,
    trendSlope,
    confidenceInterval: ci,
    sampleSize: n,
  };
}

// Convert American odds (e.g. -110) to decimal multiplier
function americanToDecimal(odds: number): number {
  if (odds > 0) return odds / 100 + 1;
  return 100 / Math.abs(odds) + 1;
}

// Calculate expected value given a probability of OVER and American odds
export function calculateExpectedValue(
  overProbability: number,
  oddsOver = -110,
  oddsUnder = -110
): number {
  const decOver = americanToDecimal(oddsOver);
  const decUnder = americanToDecimal(oddsUnder);
  const evOver = overProbability * decOver - 1;
  const evUnder = (1 - overProbability) * decUnder - 1;
  return Math.max(evOver, evUnder);
}

// A small helper to turn a numeric prediction into a probability (sigmoid)
export function scoreToProbability(predicted: number, line: number): number {
  // scale difference and squash to [0,1]
  const diff = predicted - line;
  // scale factor chosen conservatively
  const scaled = diff / 5.0;
  const prob = 1 / (1 + Math.exp(-scaled));
  return Math.min(0.9999, Math.max(0.0001, prob));
}

// Lightweight wrapper that returns a PredictionResult using recentGames and optional predictedValue
export function buildPredictionFromFeatures(
  player: string,
  stat: string,
  line: number,
  recentGames: number[] | null,
  predictedValue: number | null = null
): PredictionResult {
  const evidence = calculateStatisticalEvidence(recentGames);
  let predicted = predictedValue;
  if (predicted == null) {
    predicted = evidence.mean ?? line;
  }
  const overProb = scoreToProbability(predicted, line);
  const underProb = 1 - overProb;
  const ev = calculateExpectedValue(overProb);
  let recommendation: PredictionResult["recommendation"] = null;
  if (overProb > 0.55) recommendation = "OVER";
  else if (underProb > 0.55) recommendation = "UNDER";

  const calibratedConfidence = Math.round(Math.abs(overProb - 0.5) * 200);

  return {
    player,
    stat,
    line,
    overProbability: overProb,
    underProbability: underProb,
    calibratedConfidence,
    modelPredictions:
      predictedValue != null ? { baseline: predictedValue } : undefined,
    evidence,
    recommendation,
    expectedValue: ev,
  };
}

export default {
  calculateStatisticalEvidence,
  calculateExpectedValue,
  buildPredictionFromFeatures,
  scoreToProbability,
};

// Streaming helper: connect to backend `/api/ollama_stream` POST endpoint and
// stream Server-Sent-Event style fragments delivered by the backend. The
// backend currently accepts POST JSON { model, prompt } and responds with
// text/event-stream chunks prefixed with `data:`. We consume the raw
// ReadableStream and invoke callbacks per fragment (word/line level).
export type StreamChunk = { text?: string; done?: boolean; error?: string };

export async function streamOllamaAnalysis(
  prompt: string,
  opts: { model?: string; signal?: AbortSignal; testProjections?: any[] } = {},
  onChunk: (_c: StreamChunk) => void = () => {},
  onDone: () => void = () => {},
  onError: (_err: any) => void = () => {}
): Promise<void> {
  const payload = { model: opts.model, prompt };
  // Resolve backend base URL: prefer Vite env `VITE_API_BASE`, fallback to localhost:3002
  const apiBase =
    (import.meta as any).env?.VITE_API_BASE || "http://localhost:3002";
  const url = apiBase.replace(/\/$/, "") + "/api/ollama_stream";

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: opts.signal,
    });

    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => "");
      const msg = `stream request failed: ${resp.status} ${resp.statusText} ${text}`;
      onError(msg);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double-newline; process complete frames
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const p of parts) {
        const line = p.trim();
        if (!line) continue;
        // Only handle `data:` lines; ignore other SSE meta for now
        if (line.startsWith("data:")) {
          const data = line.replace(/^data:\s*/i, "");
          if (data === "[DONE]") {
            onChunk({ done: true });
            onDone();
            return;
          }
          // Try to parse JSON payloads, otherwise return raw text
          try {
            const parsed = JSON.parse(data);
            // common shapes: { content } or { text }
            const text = parsed?.content ?? parsed?.text ?? String(parsed);
            onChunk({ text });
          } catch {
            // not JSON — emit raw string (could be partial word/phrase)
            onChunk({ text: data });
          }
        } else if (line.startsWith("event:")) {
          // example: event: error\ndata: message
          if (/event:\s*error/i.test(line)) {
            const msgMatch = line.match(/data:\s*(.*)/i);
            const msg = msgMatch ? msgMatch[1] : "unknown";
            onChunk({ error: msg });
            onError(msg);
            return;
          }
        } else {
          // fallback: emit raw frame
          onChunk({ text: line });
        }
      }
    }

    // Flush any remaining buffer
    if (buffer.trim()) {
      const lr = buffer.trim();
      if (lr === "[DONE]") {
        onChunk({ done: true });
        onDone();
        return;
      }
      try {
        const parsed = JSON.parse(lr);
        const text = parsed?.content ?? parsed?.text ?? String(parsed);
        onChunk({ text });
      } catch {
        onChunk({ text: lr });
      }
    }

    onDone();
  } catch (err) {
    onError(err);
  }
}
