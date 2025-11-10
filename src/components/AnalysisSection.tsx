import { useEffect, useState, useRef } from 'react';
import { marked } from 'marked';
import { ParsedProjection, Settings } from '../types';
import { analyzeWithLocalLLM, buildAnalysisPromptAsync } from '../services/aiService';
import { validateOutput } from '../services/analysisValidator';

interface AnalysisSectionProps {
  projections: ParsedProjection[];
  settings: Settings;
}

export default function AnalysisSection({ projections, settings }: AnalysisSectionProps) {
  const [content, setContent] = useState('');
  const [parsedResults, setParsedResults] = useState<any[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [externalContexts, setExternalContexts] = useState<Record<string, any> | null>(null);
  const [showExternalDetails, setShowExternalDetails] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);
  const [rawOutput, setRawOutput] = useState<string | null>(null);
  const [validationReasons, setValidationReasons] = useState<string[] | null>(null);

  useEffect(() => {
    if (sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    const runAnalysis = async () => {
      setIsLoading(true);
      setError(null);
      setContent('');

      try {
        const { prompt, externalUsed, contexts } = await buildAnalysisPromptAsync(projections, settings) as any;
        setExternalContexts(contexts || null);
        if (externalUsed) {
          setContent(prev => prev + '\n> [External StatMuse data appended to prompt]\n\n');
        }

        // If settings require external numeric data, ensure every projection has sufficient numeric evidence.
        if (settings.requireExternalData) {
          const missing: string[] = [];
          for (const p of projections) {
            const ctx = (contexts || {})[p.id];
            const hasNumeric = ctx && ((Array.isArray(ctx.recentGames) && ctx.recentGames.length > 0) || (ctx.seasonAvg != null));
            const explicitNoGames = ctx && ctx.noGamesThisSeason;
            if (!hasNumeric && !explicitNoGames) {
              missing.push(p.player + ' (' + p.stat + ')');
            }
          }
          if (missing.length > 0) {
            setError(`External numeric data required but missing for: ${missing.join(', ')}. Open Settings to configure ` +
              `your NBA endpoint or disable "Require external numeric data".`);
            setIsLoading(false);
            return;
          }
        }

        // Helper to extract JSON array from LLM text output
        const extractFirstJsonArray = (text: string): any | null => {
          try { const j = JSON.parse(text); if (Array.isArray(j)) return j; } catch (e) {}
          // try to find first [...] block
          const start = text.indexOf('[');
          const end = text.lastIndexOf(']');
          if (start === -1 || end === -1 || end <= start) return null;
          const candidate = text.slice(start, end + 1);
          try { const parsed = JSON.parse(candidate); if (Array.isArray(parsed)) return parsed; } catch (e) { return null; }
          return null;
        };

        // use external validator helper
        // import dynamically to avoid top-level circular imports in test env
        // (module import at top of file is fine; here we call the helper below)

        // Run LLM and capture output
        let full = '';
        await analyzeWithLocalLLM(
          prompt,
          settings,
          (chunk) => {
            full += chunk;
            setContent(full);
          }
        );

        // Try parsing and validating. If invalid, retry once with stricter enforcement.
        let parsed = extractFirstJsonArray(full);
        let valid = parsed ? validateOutput(parsed, projections, externalUsed ? externalContexts : null) : { ok: false, reasons: ['No JSON array found in output'] };
        if (!valid.ok) {
          // Save raw output and reasons for debugging
          setRawOutput(full);
          setValidationReasons(valid.reasons || ['Validation failed']);

          // Attempt one retry with a strict sample JSON skeleton to maximize chance of valid output
          const sampleSkeleton = JSON.stringify(projections.map((p) => ({
            player: p.player,
            stat: p.stat,
            line: p.line,
            recommendation: null,
            confidence: 'Low',
            numericEvidence: { recentGames: null, seasonAvg: null, opponent: null, projectedMinutes: null },
            reasoning: '',
            dataUsed: { external: true, sources: [] }
          })), null, 2);

          const enforcement = '\n\nENFORCEMENT: Your previous output did not meet the required structured JSON schema or matched the trusted numeric context. Now output ONLY the corrected JSON array (no markdown) that matches the schema exactly. Use this skeleton and fill numericEvidence fields with the exact values from the trusted block or null if missing:\n\n' + sampleSkeleton + '\n\nReturn ONLY the JSON array, nothing else.\n';
          let full2 = '';
          await analyzeWithLocalLLM(
            prompt + enforcement,
            settings,
            (chunk) => { full2 += chunk; setContent(full2); }
          );
          parsed = extractFirstJsonArray(full2);
          const valid2 = parsed ? validateOutput(parsed, projections, externalUsed ? externalContexts : null) : { ok: false, reasons: ['No JSON array found after retry'] };
          if (!valid2.ok) {
            // Save retry raw output and reasons for further debugging
            setRawOutput(full2);
            setValidationReasons(valid2.reasons || ['Validation failed after retry']);
            setError('LLM output failed validation. See details below.');
            setIsLoading(false);
            return;
          }
          valid = valid2;
        }

        // At this point parsed is valid - store structured results and pretty JSON
        setParsedResults(parsed);
        setContent(JSON.stringify(parsed, null, 2));
        setIsLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
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
                    <div className="text-sm text-gray-700 dark:text-gray-300">External StatMuse data was fetched for some players.</div>
                    <button onClick={() => setShowExternalDetails(s => !s)} className="text-sm text-blue-600 dark:text-blue-300 underline">{showExternalDetails ? 'Hide' : 'Show'} details</button>
                  </div>
                  {showExternalDetails && (
                    <div className="mt-3 text-sm text-gray-700 dark:text-gray-300 space-y-2">
                      {projections.map((p) => {
                        const ctx = (externalContexts as any)[p.id];
                        if (!ctx) return null;
                        return (
                          <div key={p.id} className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-100 dark:border-gray-700">
                            <div className="font-medium">{p.player} — {p.stat}</div>
                            {ctx.recent && (
                              <div className="text-xs mt-1">Recent: <span className="italic">{ctx.recent.slice(0, 200)}{ctx.recent.length > 200 ? '…' : ''}</span></div>
                            )}
                            {ctx.season && (
                              <div className="text-xs mt-1">Season: <span className="italic">{ctx.season.slice(0, 200)}{ctx.season.length > 200 ? '…' : ''}</span></div>
                            )}

                            {ctx.opponent && (
                              <div className="text-xs mt-1">Opponent: <span className="italic">{ctx.opponent.name ?? 'Unknown'}</span> — DRtg: {ctx.opponent.defensiveRating ?? 'null'} | Pace: {ctx.opponent.pace ?? 'null'}</div>
                            )}

                            {ctx.projectedMinutes != null && (
                              <div className="text-xs mt-1">Projected minutes: <span className="italic">{ctx.projectedMinutes}</span></div>
                            )}

                            {ctx.noGamesThisSeason && (
                              <div className="mt-2 text-xs text-yellow-700 dark:text-yellow-300">
                                <strong>Note:</strong> {ctx.note || 'No recent games available for this player this season.'}
                                {ctx.lastSeason && <div>Last season with data: <span className="italic">{ctx.lastSeason}</span></div>}
                                {ctx.lastGameDate && <div>Last known game date: <span className="italic">{ctx.lastGameDate}</span></div>}
                              </div>
                            )}
                            <div className="mt-2 text-xs">
                              {ctx.recentSource && (
                                <a className="text-blue-600 dark:text-blue-300 underline mr-3" href={ctx.recentSource} target="_blank" rel="noreferrer">Recent Source</a>
                              )}
                              {ctx.seasonSource && (
                                <a className="text-blue-600 dark:text-blue-300 underline" href={ctx.seasonSource} target="_blank" rel="noreferrer">Season Source</a>
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
                  <div className="text-sm text-yellow-800 dark:text-yellow-200 font-semibold">LLM output failed validation</div>
                  <div className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">Reasons:</div>
                  <ul className="text-xs text-yellow-700 dark:text-yellow-300 list-disc ml-5 mt-1">
                    {validationReasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                  <details className="mt-2">
                    <summary className="text-xs text-blue-600 dark:text-blue-300 underline">Show raw LLM output</summary>
                    <pre className="text-xs mt-2 bg-white dark:bg-gray-900 p-2 rounded max-h-60 overflow-auto">{rawOutput}</pre>
                  </details>
                </div>
              )}

              <div className="prose dark:prose-invert max-w-none">
                {parsedResults ? (
                  <div className="space-y-3">
                    {parsedResults.map((r, idx) => (
                      <div key={idx} className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="font-medium">{r.player} — {r.stat} <span className="text-sm text-gray-500">(line {r.line})</span></div>
                            <div className="text-sm text-gray-500 mt-1">{r.reasoning}</div>
                          </div>
                          <div className="text-right">
                            <div className={`inline-block px-3 py-1 rounded-full font-semibold ${r.recommendation === 'OVER' ? 'bg-green-100 text-green-800' : r.recommendation === 'UNDER' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}`}>{r.recommendation || 'NO LEAN'}</div>
                            <div className="text-xs mt-1">Confidence: <span className="font-medium">{r.confidence}</span></div>
                          </div>
                        </div>

                        {r.numericEvidence && (
                          <div className="mt-3 text-xs text-gray-600 dark:text-gray-300">
                            <div><strong>Numeric evidence:</strong></div>
                            <div>seasonAvg: {r.numericEvidence.seasonAvg ?? 'null'}</div>
                            <div>recentGames: {Array.isArray(r.numericEvidence.recentGames) ? `${r.numericEvidence.recentGames.map((g:any)=>g.statValue).join(', ')}` : 'null'}</div>
                            {r.numericEvidence.opponent && (
                              <div>opponent: {r.numericEvidence.opponent.name ?? 'null'} — DRtg: {r.numericEvidence.opponent.defensiveRating ?? 'null'} | Pace: {r.numericEvidence.opponent.pace ?? 'null'}</div>
                            )}
                            <div>projectedMinutes: {r.numericEvidence.projectedMinutes ?? 'null'}</div>
                          </div>
                        )}

                        {r.dataUsed && (
                          <div className="mt-2 text-xs text-gray-500">Data used: {r.dataUsed.external ? 'external' : 'projection only'} {r.dataUsed.sources ? `(${r.dataUsed.sources.join(', ')})` : ''}</div>
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
