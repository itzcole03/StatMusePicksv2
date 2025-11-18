# NBA API Usage Optimization Report for StatMusePicksV2

**Author:** Manus AI

**Date:** November 17, 2025

## 1. Executive Summary

The codebase review confirms that the foundational defensive mechanisms (caching, rate limiting, retries) for interacting with the unofficial NBA API are **robust and well-implemented**. This is a critical strength.

However, to achieve **"true accurate usage"** for 10/10 prediction analysis, the current implementation is limited by its default focus on the current season, which hinders the historical data depth required for advanced feature engineering.

This report details the necessary refinements to the `nba_api` usage, focusing on multi-season data retrieval and the integration of advanced statistical metrics. The core optimization is a shift from single-season data fetching to explicit, multi-season queries where necessary for the training pipeline.

## 2. Analysis of Current `nba_api` Usage

The analysis focused on `backend/services/nba_stats_client.py` and `backend/services/nba_service.py`.

### 2.1. Strengths (Robust Defensive Mechanisms)

| Feature | Implementation in Codebase | Optimization Status |
| :--- | :--- | :--- |
| **Rate Limiting** | Token-bucket style with `MAX_REQUESTS_PER_MINUTE` (default 20) and `_acquire_token` logic. | **Excellent.** Essential for preventing IP bans. |
| **Retries** | `_with_retries` wrapper with exponential backoff. | **Excellent.** Handles transient network errors and rate limit spikes. |
| **Caching** | Multi-level caching (Redis → in-process TTLCache). | **Excellent.** Reduces API calls, which is the single most important optimization. |
| **Player Lookup** | Uses `nba_api.stats.static.players` with caching and fallbacks. | **Excellent.** Correctly uses static data to avoid unnecessary API calls. |

### 2.2. Weaknesses (Data Accuracy and Depth)

| Endpoint | Current Limitation | Impact on Prediction Accuracy |
| :--- | :--- | :--- |
| `PlayerGameLog` | Defaults to current season only. | **High.** Prevents calculation of long-term rolling averages (e.g., last 50 games) and full historical backtesting. |
| `TeamGameLog` | Defaults to current season only. | **High.** Prevents calculation of accurate, long-term opponent-adjusted metrics (e.g., opponent defensive rating over the last 3 seasons). |
| Advanced Stats | No usage of advanced metrics endpoints. | **Critical.** The original plan identified advanced metrics (PER, USG%, PIE) as vital for 10/10 analysis. |

## 3. Optimization Strategy: Multi-Season Data Retrieval

The strategy is to modify the low-level client (`nba_stats_client.py`) to accept a `season` parameter for all relevant endpoints and to introduce a new function for advanced stats. The higher-level service (`nba_service.py`) will then be updated to leverage this multi-season capability, especially for the training data pipeline.

### 3.1. Refinement to `nba_stats_client.py`

The following table summarizes the required changes to the core client functions:

| Function | Change | Rationale |
| :--- | :--- | :--- |
| `fetch_recent_games` | Added optional `season: Optional[str]` parameter. Updated cache key to include `season`. | Allows the training pipeline to explicitly request game logs for previous seasons, enabling full historical backtesting. |
| `get_team_stats` | Added optional `season: Optional[str]` parameter. Updated cache key to include `season`. | Enables the calculation of team-level features (e.g., opponent pace, defensive rating) for any given season, which is crucial for opponent-adjusted features. |
| **NEW:** `get_advanced_player_stats` | Implemented using `leaguedashplayerstats`. | Directly addresses the critical need for advanced metrics (PER, TS%, USG%, PIE) identified in the initial improvement plan. |

### 3.2. Refinement to `nba_service.py`

The service layer must be adapted to utilize the new multi-season capabilities.

| Function | Change | Rationale |
| :--- | :--- | :--- |
| `get_player_summary` | Added optional `season: Optional[str]` parameter. Passes `season` to `fetch_recent_games`. | Ensures the frontend can request context for past seasons if needed, and the cache key is more specific. |
| **NEW:** `get_player_context_for_training` | Dedicated function to fetch all data for a single training sample, explicitly requesting data for the relevant season. | **Critical for accuracy.** This separates the data needs of the frontend (current context) from the data needs of the ML pipeline (historical context), ensuring no data leakage and maximum historical depth. |

## 4. Implementation Recommendations (Code Snippets)

The following code snippets illustrate the most critical changes to the data fetching logic.

### 4.1. Optimized `get_team_stats` (in `nba_stats_client.py`)

The original implementation of `get_team_stats` was limited to the current season. The optimized version explicitly passes the `season` parameter to `TeamGameLog`.

```python
def get_team_stats(team_id: int, season: Optional[str] = None) -> Dict[str, float]:
    # ... (caching logic) ...
    
    if teamgamelog is None:
        return {}

    try:
        def _fetch(tid, s):
            # Pass season to TeamGameLog
            tg = teamgamelog.TeamGameLog(team_id=tid, season=s)
            return tg.get_data_frames()[0]

        # Call fetch with the season parameter
        df = _with_retries(_fetch, team_id, season)
        
        # ... (data processing and mean calculation logic) ...
        
        return stats
    except Exception:
        # ... (error handling) ...
        return {}
```

### 4.2. New `get_advanced_player_stats` (in `nba_stats_client.py`)

This new function is essential for incorporating advanced metrics into the feature set.

```python
def get_advanced_player_stats(player_id: int, season: str) -> Dict[str, float]:
    # ... (caching logic) ...
    
    try:
        def _fetch(s):
            # Use LeagueDashPlayerStats to get advanced metrics
            lds = leaguedashplayerstats.LeagueDashPlayerStats(
                season=s,
                per_mode_simple='PerGame',
            )
            return lds.get_data_frames()[0]

        df_all = _with_retries(_fetch, season)
        
        # Find the row for the specific player
        player_row = df_all[df_all['PLAYER_ID'] == player_id]
        
        # Extract advanced metrics (PER, TS_PCT, USG_PCT, PIE, etc.)
        stats: Dict[str, float] = {}
        for col in ['PER', 'TS_PCT', 'USG_PCT', 'PIE', 'OFF_RATING', 'DEF_RATING']:
            if col in player_row.columns:
                stats[col] = float(player_row[col].iloc[0])
        
        # ... (caching logic) ...
        return stats
    except Exception:
        # ... (error handling) ...
        return {}
```

### 4.3. New `get_player_context_for_training` (in `nba_service.py`)

This function is the bridge between the optimized client and the ML training pipeline.

```python
def get_player_context_for_training(
    player: str, 
    stat: str, 
    game_date: str, 
    season: str
) -> Dict[str, Any]:
    """
    Dedicated function to fetch all necessary context for a single training sample.
    """
    pid = nba_stats_client.find_player_id_by_name(player)
    if not pid:
        raise ValueError(f'Player not found: {player}')

    # 1. Player Game Log (Fetch all games in the season for feature engineering to filter)
    recent_games_season = nba_stats_client.fetch_recent_games(
        pid, 
        limit=82, # Fetch all games in the season
        season=season
    )
    
    # 2. Season Stats (for the season)
    season_stats = nba_stats_client.get_player_season_stats(pid, season)
    
    # 3. Advanced Stats (for the season)
    advanced_stats = nba_stats_client.get_advanced_player_stats(pid, season)
    
    # ... (Return structured context) ...
    return {
        'player': player,
        'playerId': pid,
        'season': season,
        'recentGamesRaw': recent_games_season,
        'seasonStats': season_stats,
        'advancedStats': advanced_stats,
        # ... (other context) ...
    }
```

## 5. Conclusion and Next Steps

The current `nba_api` usage is defensively sound but analytically limited. The proposed changes directly address the need for historical data depth and advanced metrics, which are non-negotiable for achieving 10/10 prediction accuracy.

The next step in the implementation, as outlined in the original roadmap, is to integrate these optimized data fetching functions into the **Feature Engineering Pipeline** (Phase 1, Task 1.3.1) and the **Training Data Pipeline** (Phase 2, Task 2.1.1).

The optimized code for `nba_stats_client.py` and `nba_service.py` has been generated and is ready for implementation.

## 6. References

[1] swar/nba\_api. *An API Client package to access the APIs for NBA.com*. [https://github.com/swar/nba\_api](https://github.com/swar/nba_api)
[2] Manus AI. *Comprehensive Improvement Plan for StatMusePicksV2 AI Service*. November 10, 2025. (Internal Document)
[3] Manus AI. *Technical Implementation Guide: Detailed Specifications*. November 10, 2025. (Internal Document)
