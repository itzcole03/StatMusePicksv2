This folder previously contained a small local proxy that wrapped `nba_api`.
Per repository direction all bundled proxy code has been removed.

If you need to run `nba_api` server-side, create a standalone backend (Flask / FastAPI)
outside this frontend workspace and expose only the endpoints your UI needs.

Example guidance is included in repository notes and can be re-added on request.
