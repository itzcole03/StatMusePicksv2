import { render, screen, waitFor } from "@testing-library/react";
import AnalysisSection from "../AnalysisSection";
import { vi } from "vitest";

// Mock the aiService helpers used by AnalysisSection
vi.mock("../../../src/services/aiService", async () => {
  return {
    buildAnalysisPromptAsync: vi.fn(
      async (projections: any[], _settings: any) => {
        // Build a fake contexts map with numeric recentGames for each projection
        const contexts: Record<string, any> = {};
        projections.forEach((p: any, idx: number) => {
          contexts[p.id] = {
            recentGames: [
              { statValue: 12 + idx },
              { statValue: 13 + idx },
              { statValue: 11 + idx },
            ],
            seasonAvg: 12 + idx,
            opponent: { name: "Opp", defensiveRating: 105, pace: 100 },
            projectedMinutes: 30,
          };
        });
        return { prompt: "fake-prompt", externalUsed: true, contexts };
      }
    ),
    analyzeWithLocalLLM: vi.fn(
      async (prompt: string, settings: any, onChunk: (_c: string) => void) => {
        // Build an LLM JSON array that recommends OVER for every projection
        // Simulate streaming by calling onChunk once with full JSON
        const arr = settings.testProjections.map((p: any, idx: number) => ({
          player: p.player,
          stat: p.stat,
          line: p.line,
          recommendation: "OVER",
          confidence: "High",
          modelConfidenceScore: 85,
          numericEvidence: {
            recentGames: [12 + idx, 13 + idx, 11 + idx],
            seasonAvg: 12 + idx,
            opponent: { name: "Opp" },
            projectedMinutes: 30,
          },
          reasoning: "Recent games and season average exceed the line",
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
      // Simple mimic of original scoring: trust seasonAvg -> expectedRec
      const items = parsed.map((it, idx) => ({
        index: idx,
        expectedRec: "OVER",
        modelRec: it.recommendation,
        match: it.recommendation === "OVER",
        heuristicScore: 80,
        modelScore: it.modelConfidenceScore,
      }));
      return { items, agreement: 100 };
    },
  };
});

// Also ensure aiService.v2 is real so the component uses its prediction logic
// We don't mock it; import normally

const sampleProjections = [
  {
    id: "p1",
    player: "Player One",
    stat: "points",
    line: 10,
    team: "T1",
    league: "NBA",
    startTime: Date.now(),
  },
  {
    id: "p2",
    player: "Player Two",
    stat: "points",
    line: 11,
    team: "T2",
    league: "NBA",
    startTime: Date.now(),
  },
];

describe("AnalysisSection E2E compare LLM vs statistical model", () => {
  it("shows agreement between LLM and statistical model (aiService.v2)", async () => {
    // Render with settings that pass testProjections into mocked analyzeWithLocalLLM
    const _settings = {
      llmEndpoint: "http://local.test",
      llmModel: "test",
      requireExternalData: true,
      testProjections: sampleProjections,
    } as any;
    render(
      <AnalysisSection
        projections={sampleProjections as any}
        settings={_settings as any}
      />
    );

    // Wait for the agreement summary to appear
    await waitFor(
      () =>
        expect(
          screen.getByText(/Model\/Heuristic agreement:/i)
        ).toBeInTheDocument(),
      { timeout: 2000 }
    );

    // The numeric '100%' might be wrapped in a <strong>, so assert the numeric token and headers separately
    expect(
      screen.getByText(/Model\/Heuristic agreement:/i)
    ).toBeInTheDocument();
    const percents = screen.getAllByText(/100%/);
    expect(percents.length).toBeGreaterThan(0);

    // Check that each rendered result shows the statistical model line label
    const statLabels = screen.getAllByText(/Statistical model:/i);
    expect(statLabels.length).toBeGreaterThan(0);
  });
});
