#!/usr/bin/env python3
"""Helper to pull recommended Ollama embedding models.

Usage:
  python pull_ollama_models.py --models embeddinggemma,qwen3-embedding

Reads `OLLAMA_MODELS` env var if `--models` not provided.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from typing import List

DEFAULT_MODELS = ["embeddinggemma", "qwen3-embedding", "all-minilm"]


def run_pull(models: List[str], pull_cmd: str = "ollama", timeout: int = 600) -> int:
    exit_code = 0
    for m in models:
        m = m.strip()
        if not m:
            continue
        cmd = [pull_cmd, "pull", m]
        print(f"Pulling model: {m} using: {' '.join(shlex.quote(p) for p in cmd)}")
        try:
            subprocess.run(cmd, check=True, timeout=timeout)
            print(f"Pulled model: {m}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to pull model {m}: {e}", file=sys.stderr)
            exit_code = exit_code or e.returncode or 1
        except FileNotFoundError:
            print(
                f"Pull command not found: {pull_cmd}. Is Ollama installed and on PATH?",
                file=sys.stderr,
            )
            return 2
        except Exception as e:
            print(f"Unexpected error pulling {m}: {e}", file=sys.stderr)
            exit_code = exit_code or 1
    return exit_code


def parse_models(arg: str | None) -> List[str]:
    if arg:
        return [s.strip() for s in arg.split(",") if s.strip()]
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    return DEFAULT_MODELS


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", help="Comma-separated models to pull")
    p.add_argument("--pull-cmd", default=os.environ.get("OLLAMA_PULL_CMD", "ollama"))
    p.add_argument(
        "--timeout", type=int, default=int(os.environ.get("OLLAMA_PULL_TIMEOUT", "600"))
    )
    args = p.parse_args()

    models = parse_models(args.models)
    if not models:
        print("No models to pull.")
        sys.exit(0)

    code = run_pull(models, pull_cmd=args.pull_cmd, timeout=args.timeout)
    sys.exit(code)


if __name__ == "__main__":
    main()
