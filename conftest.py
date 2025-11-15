"""Pytest configuration for this repository.

Ensure the repository root is on sys.path during collection so tests that
import top-level modules (e.g. `backend.*`) work reliably in different
environments and CI runners.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Insert the repository root at the front of sys.path so imports like
# `import backend.services` resolve when pytest runs from various CWDs.
ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
