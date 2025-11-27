import { useEffect, useState, useRef } from "react";
import { marked } from "marked";
import { ParsedProjection, Settings } from "../types";
import {
  buildAnalysisPromptAsync,
  scoreModelOutput,
} from "../services/aiService";
import { streamOllamaAnalysis } from "../services/aiService.v2";
import { buildPredictionFromFeatures } from "../services/aiService.v2";
import { validateOutput } from "../services/analysisValidator";
import { buildExternalContextForProjections } from "../services/nbaService";
import { saveNbaContexts } from "../services/indexedDBService";

interface AnalysisSectionProps {
  projections: ParsedProjection[];
  settings: Settings;
}

export default function AnalysisSection({
  projections,
  settings,
}: AnalysisSectionProps) {
  const [content, setContent] = useState("");
  const [parsedResults, setParsedResults] = useState<any[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [externalContexts, setExternalContexts] = useState<Record<
    string,
    any
  > | null>(null);
  const [showExternalDetails, setShowExternalDetails] = useState(false);
  const [refetchingIds, setRefetchingIds] = useState<Set<string>>(new Set());
  const sectionRef = useRef<HTMLDivElement>(null);
  const [rawOutput, setRawOutput] = useState<string | null>(null);
  const [validationReasons, setValidationReasons] = useState<string[] | null>(
    null
  );
  const [agreementSummary, setAgreementSummary] = useState<{
    agreement: number;
    items: any[];
  } | null>(null);
  const [v2Predictions, setV2Predictions] = useState<any[] | null>(null);
  const [v2Agreement, setV2Agreement] = useState<number | null>(null);

  useEffect(() => {
    if (
      sectionRef.current &&
      typeof (sectionRef.current as any).scrollIntoView === "function"
    ) {
      (sectionRef.current as any).scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }

    const runAnalysis = async () => {
      setIsLoading(true);
      setError(null);
      setContent("");

      try {
        const { prompt, externalUsed, contexts } =
          (await buildAnalysisPromptAsync(projections, settings)) as any;
        setExternalContexts(contexts || null);
        if (externalUsed) {
          setContent(
            (prev) =>
              prev + "\n> [External StatMuse data appended to prompt]\n\n"
          );
        }

        // If settings require external numeric data, ensure every projection has sufficient numeric evidence.
        if (settings.requireExternalData) {
          const missing: string[] = [];
          for (const p of projections) {
            const ctx = (contexts || {})[p.id];
            const hasNumeric =
              ctx &&
              ((Array.isArray(ctx.recentGames) && ctx.recentGames.length > 0) ||
                ctx.seasonAvg != null);
            const explicitNoGames = ctx && ctx.noGamesThisSeason;
            if (!hasNumeric && !explicitNoGames) {
              missing.push(p.player + " (" + p.stat + ")");
            }
          }
          if (missing.length > 0) {
            setError(
              `External numeric data required but missing for: ${missing.join(
                ", "
              )}. Open Settings to configure ` +
                `your NBA endpoint or disable "Require external numeric data".`
            );
            setIsLoading(false);
            return;
          }
        }

        // Helper to extract JSON array from LLM text output
        const extractFirstJsonArray = (text: string): any | null => {
          try {
            const j = JSON.parse(text);
            if (Array.isArray(j)) return j;
          } catch {}
          // try to find first [...] block
          const start = text.indexOf("[");
          const end = text.lastIndexOf("]");
          if (start === -1 || end === -1 || end <= start) return null;
          const candidate = text.slice(start, end + 1);
          try {
            const parsed = JSON.parse(candidate);
            if (Array.isArray(parsed)) return parsed;
          } catch {
            return null;
          }
          return null;
        };

        // use external validator helper
        // import dynamically to avoid top-level circular imports in test env
        // (module import at top of file is fine; here we call the helper below)

        // Build aiService.v2 statistical predictions from trusted contexts so we can compare later
        let preds: any[] | null = null;
        try {
          preds = projections.map((p) => {
            const ctx = (contexts || {})[p.id] || null;
            let recentVals: number[] | null = null;
            if (
              ctx &&
              Array.isArray(ctx.recentGames) &&
              ctx.recentGames.length > 0
            ) {
              recentVals = ctx.recentGames
                .map((g: any) => Number(g.statValue))
                .filter((v: any) => !isNaN(v));
            } else if (ctx && ctx.seasonAvg != null) {
              recentVals = [Number(ctx.seasonAvg)];
            }
            return buildPredictionFromFeatures(
              p.player,
              p.stat,
              Number(p.line),
              recentVals,
              null
            );
          });
          setV2Predictions(preds);
        } catch {
          setV2Predictions(null);
        }

        // Run LLM via backend SSE stream and capture output in real-time
        let full = "";
        await streamOllamaAnalysis(
          prompt,
          {
            model: settings.llmModel,
            testProjections: (settings as any).testProjections,
          },
          (chunk) => {
            if (chunk.error) {
              // surface error but continue to let exception handling decide
              // this will be handled by the outer try/catch below
              return;
            }
            if (chunk.text) {
              full += chunk.text;
              setContent(full);
            }
            if (chunk.done) {
              // noop; stream helper will resolve
            }
          },
          () => {
            // onDone
          },
          (err) => {
            // bubble up as thrown error to trigger retry/fallback
            throw new Error(String(err));
          }
        );

        // Try parsing and validating. If invalid, retry once with stricter enforcement.
        let parsed = extractFirstJsonArray(full);
        let valid = parsed
          ? validateOutput(parsed, projections, externalUsed ? contexts : null)
          : { ok: false, reasons: ["No JSON array found in output"] };
        if (!valid.ok) {
          // Save raw output and reasons for debugging
          setRawOutput(full);
          setValidationReasons(valid.reasons || ["Validation failed"]);

          // Attempt one retry with a strict sample JSON skeleton to maximize chance of valid output
          const sampleSkeleton = JSON.stringify(
            projections.map((p) => ({
              player: p.player,
              stat: p.stat,
              line: p.line,
              recommendation: null,
              confidence: "Low",
              numericEvidence: {
                recentGames: null,
                seasonAvg: null,
                opponent: null,
                projectedMinutes: null,
              },
              reasoning: "",
              dataUsed: { external: true, sources: [] },
            })),
            null,
            2
          );

          const enforcement =
            "\n\nENFORCEMENT: Your previous output did not meet the required structured JSON schema or matched the trusted numeric context. Now output ONLY the corrected JSON array (no markdown) that matches the schema exactly. Use this skeleton and fill numericEvidence fields with the exact values from the trusted block or null if missing:\n\n" +
            sampleSkeleton +
            "\n\nReturn ONLY the JSON array, nothing else.\n";
          let full2 = "";
          await streamOllamaAnalysis(
            prompt + enforcement,
            {
              model: settings.llmModel,
              testProjections: (settings as any).testProjections,
            },
            (chunk) => {
              if (chunk.error) return;
              if (chunk.text) {
                full2 += chunk.text;
                setContent(full2);
              }
            },
            () => {},
            (err) => {
              throw new Error(String(err));
            }
          );
          parsed = extractFirstJsonArray(full2);
          const valid2 = parsed
            ? validateOutput(
                parsed,
                projections,
                externalUsed ? contexts : null
              )
            : { ok: false, reasons: ["No JSON array found after retry"] };
          if (!valid2.ok) {
            // Save retry raw output and reasons for further debugging
            setRawOutput(full2);
            setValidationReasons(
              valid2.reasons || ["Validation failed after retry"]
            );
            setError("LLM output failed validation. See details below.");
            setIsLoading(false);
            return;
          }
          valid = valid2;
        }

        // Post-process: score model output vs trusted numeric context and apply deterministic reviewer flags
        const score = scoreModelOutput(
          parsed,
          projections,
          externalUsed ? contexts : null
        );
        setAgreementSummary({ agreement: score.agreement, items: score.items });

        // Compare LLM parsed recommendations with aiService.v2 statistical predictions
        // Use the locally computed `preds` (from earlier in this run) rather than
        // the external `v2Predictions` state to avoid stale reads and satisfy
        // hook dependency checks.
        if (typeof preds !== "undefined" && Array.isArray(preds)) {
          const v2Items = score.items.map((_it: any, idx: number) => {
            const v2 = preds[idx];
            const modelRec = parsed[idx]?.recommendation || null;
            const v2Rec = v2?.recommendation || null;
            return {
              index: idx,
              modelRec,
              v2Rec,
              match: modelRec === v2Rec,
              v2,
            };
          });
          const matches = v2Items.filter((i: any) => i.match).length;
          const agreementPct = Math.round((matches / v2Items.length) * 100);
          setV2Agreement(agreementPct);

          // Apply deterministic flagging using v2: if LLM recommendation disagrees with v2
          // and v2 calibratedConfidence >= threshold, null the recommendation and flag for review.
          const V2_CONF_THRESHOLD =
            typeof settings.v2ConfidenceThreshold === "number"
              ? settings.v2ConfidenceThreshold
              : 60;
          const updatedParsed = parsed.map((it: any, idx: number) => {
            const v2 = preds[idx];
            if (!v2) return it;
            const v2Conf =
              typeof v2.calibratedConfidence === "number"
                ? Number(v2.calibratedConfidence)
                : 0;
            const modelRec = it.recommendation || null;
            const v2Rec = v2.recommendation || null;
            // If there's a conflict and v2 has sufficient confidence, flag
            if (
              modelRec &&
              v2Rec &&
              modelRec !== v2Rec &&
              v2Conf >= V2_CONF_THRESHOLD
            ) {
              return {
                ...it,
                originalRecommendation: it.recommendation,
                recommendation: null,
                confidence: "Low",
                flaggedForReview: true,
                v2Recommendation: v2Rec,
              };
            }
            return it;
          });

          parsed = updatedParsed;
        }

        // Use thresholds from settings (with sensible defaults) to apply deterministic safety
        const REVIEW_THRESHOLD =
          typeof settings.reviewThreshold === "number"
            ? settings.reviewThreshold
            : 60;
        const MODEL_HEURISTIC_DELTA =
          typeof settings.modelHeuristicDelta === "number"
            ? settings.modelHeuristicDelta
            : 20;

        const flaggedParsed = parsed.map((it: any, idx: number) => {
          const info = score.items[idx];
          const needsReview = !info.match && score.agreement < REVIEW_THRESHOLD;
          if (needsReview) {
            return {
              ...it,
              originalRecommendation: it.recommendation,
              recommendation: null,
              confidence: "Low",
              flaggedForReview: true,
            };
          }
          // also flag single-item large disagreement if modelConfidenceScore wildly differs from heuristic
          const modelScore =
            typeof it.modelConfidenceScore === "number"
              ? Number(it.modelConfidenceScore)
              : null;
          const heuristicScore = info.heuristicScore || 0;
          if (
            modelScore != null &&
            Math.abs(modelScore - heuristicScore) > MODEL_HEURISTIC_DELTA
          ) {
            return {
              ...it,
              originalRecommendation: it.recommendation,
              flaggedForReview: true,
            };
          }
          return it;
        });

        setParsedResults(flaggedParsed);
        setContent(JSON.stringify(flaggedParsed, null, 2));
        setIsLoading(false);
      } catch (_err) {
        setError(_err instanceof Error ? _err.message : "An error occurred");
        setIsLoading(false);
      }
    };

    runAnalysis();
  }, [projections, settings]);

  const renderMarkdown = (text: string) => {
    return { __html: marked(text) };
  };

  return (
    <div ref={sectionRef} className="mb-6">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold">AI Analysis Results</h2>
        </div>
        <div className="p-6">
          {error ? (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-red-700 dark:text-red-400">Error: {error}</p>
              <p className="text-sm text-red-600 dark:text-red-500 mt-2">
                Make sure your local LLM is running at {settings.llmEndpoint}
              </p>
            </div>
          ) : (
            <div>
              {externalContexts && Object.keys(externalContexts).length > 0 && (
                <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-100 dark:border-gray-800">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      External StatMuse data was fetched for some players.
                    </div>
                    <button
                      onClick={() => setShowExternalDetails((s) => !s)}
                      className="text-sm text-blue-600 dark:text-blue-300 underline"
                    >
                      {showExternalDetails ? "Hide" : "Show"} details
                    </button>
                  </div>
                  {showExternalDetails && (
                    <div className="mt-3 text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      {projections.map((p) => {
                        const ctx = (externalContexts as any)[p.id];
                        if (!ctx) return null;
                        return (
                          <div
                            key={p.id}
                            className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-100 dark:border-gray-700"
                          >
                            <div className="font-medium">
                              {p.player} — {p.stat}
                            </div>
                            {ctx.recent && (
                              <div className="text-xs mt-1">
                                Recent:{" "}
                                <span className="italic">
                                  {ctx.recent.slice(0, 200)}
                                  {ctx.recent.length > 200 ? "…" : ""}
                                </span>
                              </div>
                            )}
                            {ctx.season && (
                              <div className="text-xs mt-1">
                                Season:{" "}
                                <span className="italic">
                                  {ctx.season.slice(0, 200)}
                                  {ctx.season.length > 200 ? "…" : ""}
                                </span>
                              </div>
                            )}

                            {ctx.opponent && (
                              <div className="text-xs mt-1">
                                Opponent:{" "}
                                <span className="italic">
                                  {ctx.opponent.name ?? "Unknown"}
                                </span>{" "}
                                — DRtg: {ctx.opponent.defensiveRating ?? "null"}{" "}
                                | Pace: {ctx.opponent.pace ?? "null"}
                              </div>
                            )}

                            {ctx.projectedMinutes != null && (
                              <div className="text-xs mt-1">
                                Projected minutes:{" "}
                                <span className="italic">
                                  {ctx.projectedMinutes}
                                </span>
                              </div>
                            )}

                            {ctx.rollingAverages &&
                              Object.keys(ctx.rollingAverages).length > 0 && (
                                <div className="text-xs mt-1">
                                  <strong>Rolling averages:</strong>
                                  <div className="mt-1 flex flex-wrap gap-2">
                                    {Object.entries(ctx.rollingAverages).map(
                                      ([k, v]: any) => (
                                        <div
                                          key={k}
                                          className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs"
                                        >
                                          {k}:{" "}
                                          {v != null
                                            ? Number(v).toFixed(2)
                                            : "null"}
                                        </div>
                                      )
                                    )}
                                  </div>
                                </div>
                              )}

                            {ctx.noGamesThisSeason && (
                              <div className="mt-2 text-xs text-yellow-700 dark:text-yellow-300">
                                <strong>Note:</strong>{" "}
                                {ctx.note ||
                                  "No recent games available for this player this season."}
                                {ctx.lastSeason && (
                                  <div>
                                    Last season with data:{" "}
                                    <span className="italic">
                                      {ctx.lastSeason}
                                    </span>
                                  </div>
                                )}
                                {ctx.lastGameDate && (
                                  <div>
                                    Last known game date:{" "}
                                    <span className="italic">
                                      {ctx.lastGameDate}
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                            <div className="mt-2 flex items-center gap-2">
                              <button
                                onClick={async () => {
                                  try {
                                    setRefetchingIds((prev) =>
                                      new Set(prev).add(p.id)
                                    );
                                    const contexts =
                                      await buildExternalContextForProjections(
                                        [p],
                                        settings
                                      );
                                    await saveNbaContexts(contexts);
                                    // merge into existing externalContexts state
                                    setExternalContexts((prev) => ({
                                      ...(prev || {}),
                                      ...contexts,
                                    }));
                                  } catch {
                                    // ignore; UI will still show existing context
                                  } finally {
                                    setRefetchingIds((prev) => {
                                      const s = new Set(prev);
                                      s.delete(p.id);
                                      return s;
                                    });
                                  }
                                }}
                                className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600"
                                disabled={refetchingIds.has(p.id)}
                              >
                                {refetchingIds.has(p.id)
                                  ? "Refreshing…"
                                  : "Refetch context"}
                              </button>
                              <div className="text-xs text-gray-500">
                                Click to refresh numeric context for this
                                player.
                              </div>
                            </div>
                            <div className="mt-2 text-xs">
                              {ctx.recentSource && (
                                <a
                                  className="text-blue-600 dark:text-blue-300 underline mr-3"
                                  href={ctx.recentSource}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Recent Source
                                </a>
                              )}
                              {ctx.seasonSource && (
                                <a
                                  className="text-blue-600 dark:text-blue-300 underline"
                                  href={ctx.seasonSource}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Season Source
                                </a>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Raw debug output and validation reasons when present */}
              {rawOutput && validationReasons && (
                <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-800">
                  <div className="text-sm text-yellow-800 dark:text-yellow-200 font-semibold">
                    LLM output failed validation
                  </div>
                  <div className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
                    Reasons:
                  </div>
                  <ul className="text-xs text-yellow-700 dark:text-yellow-300 list-disc ml-5 mt-1">
                    {validationReasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                  <details className="mt-2">
                    <summary className="text-xs text-blue-600 dark:text-blue-300 underline">
                      Show raw LLM output
                    </summary>
                    <pre className="text-xs mt-2 bg-white dark:bg-gray-900 p-2 rounded max-h-60 overflow-auto">
                      {rawOutput}
                    </pre>
                  </details>
                </div>
              )}

              <div className="prose dark:prose-invert max-w-none">
                {parsedResults ? (
                  <div className="space-y-3">
                    {agreementSummary && (
                      <div className="p-3 mb-2 rounded bg-gray-50 dark:bg-gray-900 text-sm text-gray-700 dark:text-gray-300 border border-gray-100 dark:border-gray-800">
                        <div>
                          Model/Heuristic agreement:{" "}
                          <strong>{agreementSummary.agreement}%</strong>.
                        </div>
                        {v2Agreement != null && (
                          <div>
                            Statistical model agreement:{" "}
                            <strong>{v2Agreement}%</strong>.
                          </div>
                        )}
                        <div>Items flagged for review are highlighted.</div>
                      </div>
                    )}
                    {parsedResults.map((r, idx) => (
                      <div
                        key={idx}
                        className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="font-medium">
                              {r.player} — {r.stat}{" "}
                              <span className="text-sm text-gray-500">
                                (line {r.line})
                              </span>
                            </div>
                            <div className="text-sm text-gray-500 mt-1">
                              {r.reasoning}
                            </div>
                          </div>
                          <div className="text-right">
                            <div
                              className={`inline-block px-3 py-1 rounded-full font-semibold ${
                                r.recommendation === "OVER"
                                  ? "bg-green-100 text-green-800"
                                  : r.recommendation === "UNDER"
                                  ? "bg-red-100 text-red-800"
                                  : "bg-gray-100 text-gray-700"
                              }`}
                            >
                              {r.recommendation || "NO LEAN"}
                            </div>
                            <div className="text-xs mt-1">
                              Confidence:{" "}
                              <span className="font-medium">
                                {r.confidence}
                              </span>
                            </div>
                          </div>
                        </div>

                        {r.numericEvidence && (
                          <div className="mt-3 text-xs text-gray-600 dark:text-gray-300">
                            <div>
                              <strong>Numeric evidence:</strong>
                            </div>
                            <div>
                              seasonAvg: {r.numericEvidence.seasonAvg ?? "null"}
                            </div>
                            <div>
                              recentGames:{" "}
                              {Array.isArray(r.numericEvidence.recentGames)
                                ? `${r.numericEvidence.recentGames
                                    .map((g: any) => g.statValue)
                                    .join(", ")}`
                                : "null"}
                            </div>
                            {r.numericEvidence.opponent && (
                              <div>
                                opponent:{" "}
                                {r.numericEvidence.opponent.name ?? "null"} —
                                DRtg:{" "}
                                {r.numericEvidence.opponent.defensiveRating ??
                                  "null"}{" "}
                                | Pace:{" "}
                                {r.numericEvidence.opponent.pace ?? "null"}
                              </div>
                            )}
                            <div>
                              projectedMinutes:{" "}
                              {r.numericEvidence.projectedMinutes ?? "null"}
                            </div>
                          </div>
                        )}

                        {v2Predictions && v2Predictions[idx] && (
                          <div className="mt-3 text-xs text-gray-600 dark:text-gray-300">
                            <div>
                              <strong>Statistical model:</strong>{" "}
                              {v2Predictions[idx].recommendation ?? "NO LEAN"} —
                              Prob(OVER):{" "}
                              {(
                                v2Predictions[idx].overProbability ?? 0
                              ).toFixed(2)}
                            </div>
                          </div>
                        )}
                        {r.flaggedForReview && (
                          <div className="mt-3 text-xs text-yellow-700 dark:text-yellow-300">
                            <strong>Flagged for review:</strong> The model's
                            recommendation disagrees with the trusted numeric
                            evidence. Recommendation has been nulled to avoid
                            unsafe advice.
                          </div>
                        )}

                        {r.dataUsed && (
                          <div className="mt-2 text-xs text-gray-500">
                            Data used:{" "}
                            {r.dataUsed.external
                              ? "external"
                              : "projection only"}{" "}
                            {r.dataUsed.sources
                              ? `(${r.dataUsed.sources.join(", ")})`
                              : ""}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div>
                    <div dangerouslySetInnerHTML={renderMarkdown(content)} />
                    {isLoading && (
                      <div className="mt-4 flex items-center text-gray-500">
                        <div className="w-2 h-2 bg-[#5D5CDE] rounded-full mr-2 animate-pulse"></div>
                        Analyzing...
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
