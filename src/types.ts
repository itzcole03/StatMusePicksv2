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
    // Derived contextual factors from backend to help UI and feature engineering
    contextualFactors?: {
      daysRest?: number | null;
      isBackToBack?: boolean | null;
    } | null;
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

export interface BatchPlayerRequest {
  player: string;
  stat?: string;
  limit?: number;
}

export type BatchPlayerResult = {
  player: string;
  error: string;
} | any;

// Enhanced frontend types for backend player context
export interface RollingAverages {
  [key: string]: number | null; // e.g. 'sma_5': 12.3, 'ema_10': 11.2
}

export interface OpponentInfo {
  name?: string | null;
  defensiveRating?: number | null;
  pace?: number | null;
  [key: string]: any;
}

export interface EnhancedPlayerContext {
  player: string;
  stat: string;
  recentGames?: Array<{ date?: string | null; statValue?: number | null }> | null;
  seasonAvg?: number | null;
  noGamesThisSeason?: boolean;
  fetchedAt?: string | null;
  rollingAverages?: RollingAverages | null;
  opponentInfo?: OpponentInfo | null;
  contextualFactors?: { daysRest?: number | null; isBackToBack?: boolean | null } | null;
}
