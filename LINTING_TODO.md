Linting TODO (prioritized)
==========================

Overview
--------
This file lists a practical, low-risk plan to finish linting work started by the `chore/lint-autofix` branch.

Priority 1 — Tests and small scripts (low-risk)
- Fix unused local variables reported by flake8 in `backend/tests/*` (F841). These are safe, small edits.
- Fix `E402` import-order issues in test integration scripts where imports are intentionally delayed — prefer moving imports to top where safe.
- Files to review first:
  - `backend/tests/test_calibration_report_writer.py`
  - `backend/tests/test_dataset_registry_helpers.py`
  - `backend/tests/test_datasets_cli.py`
  - `backend/tests/test_ingest_*` files
  - `scripts/backtest_with_calibrated_probs.py` (long line, fixable by wrapping)

Priority 2 — Utility scripts and small tools (medium-risk)
- Fix trivial unused imports/variables and short long-lines in `scripts/`.
- Avoid refactoring complex logic; focus on formatting, docstrings, and small cleanup.

Priority 3 — Backend service refactors (higher-risk)
- Files flagged with C901 (too complex) require human-led refactors. Create dedicated PRs per service with unit tests.
- Candidates:
  - `backend/services/feature_engineering.py` (multiple complex functions)
  - `backend/services/llm_feature_service.py`
  - `backend/services/model_registry.py`

CI and policy
-------------
- Add flake8 to CI using the included `.flake8`; configure CI to fail on new issues only.
- Keep `chore/lint-autofix` PR limited to formatting/import fixes; subsequent PRs should contain targeted logic changes.

How I can help next
-------------------
- I can run another cautious autoflake pass limited to the remaining failing test files and small scripts, commit, and push — or
- I can create separate PRs with grouped manual fixes for Priority 1 files, including test runs to ensure no behavior changes.

Choose one of the two options above and I'll proceed.
