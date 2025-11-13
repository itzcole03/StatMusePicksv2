import React from 'react';
import { render, screen, waitFor } from "@testing-library/react";
import AnalysisSection from "../AnalysisSection";
import { vi } from "vitest";

// Mock aiService to return a v2 disagreement: LLM -> OVER, v2 -> UNDER with high confidence
vi.mock("../../../src/services/aiService", async () => {
  return {
    buildAnalysisPromptAsync: vi.fn(
      async (projections: any[], _settings: any) => {
        const contexts: Record<string, any> = {};
        projections.forEach((p: any, idx: number) => {
          contexts[p.id] = {
            recentGames: [{ statValue: 5 + idx }, { statValue: 6 + idx }],
            seasonAvg: 5 + idx,
            opponent: { name: "Opp", defensiveRating: 110, pace: 95 },
            projectedMinutes: 25,
          };
        });
        return { prompt: "fake-prompt", externalUsed: true, contexts };
      }
    ),
    analyzeWithLocalLLM: vi.fn(
      async (prompt: string, settings: any, onChunk: (_c: string) => void) => {
        // LLM returns OVER for first projection
        const arr = settings.testProjections.map((p: any, idx: number) => ({
          player: p.player,
          stat: p.stat,
          line: p.line,
          recommendation: "OVER",
          confidence: "High",
          modelConfidenceScore: 85,
          numericEvidence: {
            recentGames: [5 + idx, 6 + idx],
            seasonAvg: 5 + idx,
            opponent: { name: "Opp" },
            projectedMinutes: 25,
          },
          reasoning: "LLM says OVER",
          dataUsed: { external: true, sources: ["nba"] },
        }));
        onChunk(JSON.stringify(arr));
      }
    ),
    scoreModelOutput: (
      parsed: any[],
      _projections: any[],
      _contextsMap: Record<string, any> | null
    ) => {
      const items = parsed.map((it: any, idx: number) => ({
        index: idx,
        expectedRec: "UNDER",
        modelRec: it.recommendation,
        match: it.recommendation === "UNDER",
        heuristicScore: 20,
        modelScore: it.modelConfidenceScore,
      }));
      return { items, agreement: 0 };
    },
  };
});

// Provide a real aiService.v2 by importing normally

const sampleProjections = [
  {
    id: "p1",
    player: "Player One",
    stat: "points",
    line: 12,
    team: "T1",
    league: "NBA",
    startTime: Date.now(),
  },
];

describe("AnalysisSection E2E disagreement handling", () => {
  it("flags items for review when v2 strongly disagrees", async () => {
    const _settings = {
      llmEndpoint: "http://local.test",
      llmModel: "test",
      requireExternalData: true,
      v2ConfidenceThreshold: 50,
      testProjections: sampleProjections,
    } as any;
    render(
      <AnalysisSection
        projections={sampleProjections as any}
        settings={_settings as any}
      />
    );

    // Wait for the agreement header and flagged content
    await waitFor(
      () =>
        expect(
          screen.getByText(/Items flagged for review are highlighted/i)
        ).toBeInTheDocument(),
      { timeout: 2000 }
    );

    // Ensure a flagged-for-review badge/text appears somewhere in the item list
    const flaggedMatches = screen.getAllByText(/Flagged for review/i);
    expect(flaggedMatches.length).toBeGreaterThan(0);

    // Ensure the recommendation was nulled in the UI
    expect(screen.getByText(/NO LEAN/)).toBeInTheDocument();
  });
});
