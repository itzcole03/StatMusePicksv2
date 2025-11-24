# PER & Win Shares from Play-by-Play — Research & Implementation Plan

Goal
----
Design and implement a pipeline to compute canonical Player Efficiency Rating (PER)
and Win Shares (WS) from play-by-play or aggregated box-score data when LeagueDash
values are unavailable. Deliverables:

- Research notes and formula references
- Prototype implementation computing season-level PER and WS estimates from
  aggregated game logs (play-by-play optional)
- Integration plan for `nba_stats_client` fallback and `advanced_metrics_service`

Background & References
-----------------------
- John Hollinger's PER: https://www.basketball-reference.com/about/per.html
- Win Shares (Bill James / Basketball-Reference): https://www.basketball-reference.com/about/ws.html
- Both formulas require league/team-level constants (pace, league factor) and
  many box-score fields. Full canonical computation needs play-by-play or
  season totals for team/league possessions.

Practical approach
------------------
Given time and available data, implement a staged approach:

1. Lightweight season proxies (prototype):
   - Aggregate per-game box stats from `nba_api` (or cached logs) per player/season.
   - Compute a per-game efficiency proxy: PTS + REB + AST + STL + BLK - MissedFG - MissedFT - TOV.
   - Scale proxy to approximate PER (multiplicative factor tuned to move mean near ~15).
   - Estimate WS as `WS_per_game_proxy * games` with a minutes normalization factor.

2. Improved seasonal estimates (next iteration):
   - Compute possessions and league pace from team-season logs.
   - Implement detailed uPER calculation per Hollinger using season totals and league constants.
   - Compute offensive & defensive Win Shares (OWS/DWS) using play-by-play derived possession data.

3. Full canonical implementation (longer term):
   - Require play-by-play or league-summarized tables with possessions, opponent-rep weights.
   - Implement exact formulas and validate against Basketball-Reference values for a sample season.

Implementation plan & timeline (estimate)
----------------------------------------
- Week 0 (this PR): research + prototype module that computes season aggregates and proxy PER/WS.
- Week 1: improve normalization using league_map (z-score) and tuning constants; validate on 10 players.
- Week 2-4: implement uPER using season totals and league constants; validate vs external source.
- Week 4+: implement OWS/DWS from play-by-play if data is available.

Data requirements
-----------------
- Game logs per player per season (available via `nba_api` endpoints or cached game logs in `backend/data`).
- League-level aggregated metrics (pace, possessions) for accurate normalization.

Integration points
------------------
- `backend/services/nba_stats_client.py` — add a helper to compute seasonal aggregates (existing helpers can be reused).
- `backend/services/advanced_metrics_service.py` — call new helper when LeagueDash data absent.
- `backend/services/feature_engineering.py` — prefer canonical `PER`/`WS` but accept computed fallbacks.

Acceptance criteria for prototype
--------------------------------
- Prototype computes `PER_estimate` and `WS_estimate` for a player-season and persists sample outputs.
- Values are non-null and roughly in plausible ranges (PER ~ 5-30, WS seasonal ~ 0-20 for star players).

Next step: prototype module + sample runner will be added under `backend/services` and `backend/scripts`.

---

Created: 2025-11-22
