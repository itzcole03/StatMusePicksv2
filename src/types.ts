export interface ProjectionData {
  data: Array<{
    id: string;
    type: string;
    attributes: {
      stat_type: string;
      line_score: number;
      start_time: string;
      status: string;
    };
    relationships: {
      new_player: { data: { id: string } };
      league: { data: { id: string } };
      game?: { data: { id: string } };
    };
  }>;
  included: Array<{
    id: string;
    type: string;
    attributes: {
      name?: string;
      team?: string;
      position?: string;
      home_team?: string;
      away_team?: string;
    };
  }>;
}

export interface ParsedProjection {
  id: string;
  player: string;
  team: string;
  position: string;
  league: string;
  stat: string;
  line: number;
  startTime: string;
  status: string;
  gameId?: string;
  // Optional NBA context injected by the external NBA service proxy.
  // Frontend components may use `nbaContext.noGamesThisSeason` to display
  // compact UI badges when no recent game data exists for the player.
  nbaContext?: {
    noGamesThisSeason?: boolean;
    lastSeason?: string | null;
    lastGameDate?: string | null;
  } | null;
}

export interface Settings {
  aiProvider: "local";
  llmEndpoint: string;
  llmModel: string;
  // Optional human-friendly name for a chosen local model directory
  modelDirectory?: string;
  // Optional: external StatMuse-like data source removed; prefer structured NBA service
  // Optional: structured NBA data service endpoint (preferred for numeric stats)
  nbaEndpoint?: string;
  // Optional API key for NBA service (if required)
  nbaApiKey?: string;
  // If true, analysis will require external numeric context for all selected projections and fail otherwise
  requireExternalData?: boolean;
  // Percentage threshold (0-100). If model vs heuristic agreement is below this,
  // the projection will be flagged for review and recommendation nullified.
  reviewThreshold?: number;
  // Allowed absolute difference between model confidence and heuristic score
  // before considering them in strong disagreement (0-100 scale).
  modelHeuristicDelta?: number;
  // Calibrated v2 confidence threshold (0-100). Used by AnalysisSection to
  // compare deterministic v2 scores with the LLM output. Optional and
  // backwards-compatible.
  v2ConfidenceThreshold?: number;
}
