"""Small test bootstrap to ensure repo root is on sys.path at Python startup.

This file is executed by the site module during interpreter startup when the
current working directory (repo root) is on sys.path. It helps pytest import
top-level test modules consistently in environments where import resolution
differs.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
