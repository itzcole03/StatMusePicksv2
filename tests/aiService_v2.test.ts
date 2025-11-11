import { describe, it, expect } from "vitest";
import {
  calculateStatisticalEvidence,
  scoreToProbability,
  calculateExpectedValue,
  buildPredictionFromFeatures,
} from "../src/services/aiService.v2";

describe("aiService.v2 statistical helpers", () => {
  it("calculates mean, median, std and CI", () => {
    const recent = [10, 12, 14, 16, 18];
    const evidence = calculateStatisticalEvidence(recent as any);
    expect(evidence.sampleSize).toBe(5);
    expect(evidence.mean).toBeCloseTo(14, 6);
    expect(evidence.median).toBe(14);
    expect(evidence.std).toBeGreaterThan(0);
    expect(evidence.confidenceInterval).not.toBeNull();
  });

  it("turns predicted score into probability between 0 and 1", () => {
    const p1 = scoreToProbability(15, 10);
    const p2 = scoreToProbability(8, 10);
    expect(p1).toBeGreaterThan(0.5);
    expect(p2).toBeLessThan(0.5);
  });

  it("calculates expected value (finite number)", () => {
    const ev = calculateExpectedValue(0.6, -110, -110);
    expect(typeof ev).toBe("number");
    expect(isFinite(ev)).toBe(true);
  });

  it("builds a prediction result with recommendation", () => {
    const pred = buildPredictionFromFeatures(
      "Jane Doe",
      "points",
      12,
      [10, 11, 13, 14, 12],
      null
    );
    expect(pred.player).toBe("Jane Doe");
    expect(pred.evidence.sampleSize).toBeGreaterThan(0);
    expect(pred.overProbability + pred.underProbability).toBeCloseTo(1, 6);
  });
});
