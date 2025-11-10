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

  recommendation: 'OVER' | 'UNDER' | null;
  expectedValue: number | null;
}

// Calculate statistical evidence from recent numeric values
export function calculateStatisticalEvidence(recentGames: number[] | null): PredictionResult['evidence'] {
  if (!recentGames || recentGames.length === 0) {
    return { mean: null, median: null, std: null, trendSlope: null, confidenceInterval: null, sampleSize: 0 };
  }
  const n = recentGames.length;
  const mean = recentGames.reduce((a, b) => a + b, 0) / n;
  const sorted = [...recentGames].sort((a, b) => a - b);
  const median = sorted[Math.floor(n / 2)];
  const variance = recentGames.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / n;
  const std = Math.sqrt(variance);
  // simple linear trend slope (least squares)
  const xMean = (n - 1) / 2;
  const numerator = recentGames.reduce((s, y, x) => s + (x - xMean) * (y - mean), 0);
  const denominator = recentGames.reduce((s, _, x) => s + Math.pow(x - xMean, 2), 0) || 1;
  const trendSlope = numerator / denominator;
  const margin = 1.96 * (std / Math.sqrt(n));
  const ci: [number, number] = [mean - margin, mean + margin];
  return { mean, median, std, trendSlope, confidenceInterval: ci, sampleSize: n };
}

// Convert American odds (e.g. -110) to decimal multiplier
function americanToDecimal(odds: number): number {
  if (odds > 0) return (odds / 100) + 1;
  return (100 / Math.abs(odds)) + 1;
}

// Calculate expected value given a probability of OVER and American odds
export function calculateExpectedValue(overProbability: number, oddsOver = -110, oddsUnder = -110): number {
  const decOver = americanToDecimal(oddsOver);
  const decUnder = americanToDecimal(oddsUnder);
  const evOver = (overProbability * decOver) - 1;
  const evUnder = ((1 - overProbability) * decUnder) - 1;
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
export function buildPredictionFromFeatures(player: string, stat: string, line: number, recentGames: number[] | null, predictedValue: number | null = null): PredictionResult {
  const evidence = calculateStatisticalEvidence(recentGames);
  let predicted = predictedValue;
  if (predicted == null) {
    predicted = evidence.mean ?? line;
  }
  const overProb = scoreToProbability(predicted, line);
  const underProb = 1 - overProb;
  const ev = calculateExpectedValue(overProb);
  let recommendation: PredictionResult['recommendation'] = null;
  if (overProb > 0.55) recommendation = 'OVER';
  else if (underProb > 0.55) recommendation = 'UNDER';

  const calibratedConfidence = Math.round(Math.abs(overProb - 0.5) * 200);

  return {
    player,
    stat,
    line,
    overProbability: overProb,
    underProbability: underProb,
    calibratedConfidence,
    modelPredictions: predictedValue != null ? { baseline: predictedValue } : undefined,
    evidence,
    recommendation,
    expectedValue: ev
  };
}

export default {
  calculateStatisticalEvidence,
  calculateExpectedValue,
  buildPredictionFromFeatures,
  scoreToProbability
};
