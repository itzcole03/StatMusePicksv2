"""Small helper to invoke `ollama pull <model>` on the host where the Ollama CLI is available.

This script must be executed on the machine that hosts the Ollama server/CLI.
It is intentionally simple: it shells out and returns subprocess exit code.
"""

import os
import shlex
import subprocess
import sys


def pull_model(model_name: str) -> int:
    if not model_name:
        print("Model name required", file=sys.stderr)
        return 2
    cmd = f"ollama pull {shlex.quote(model_name)}"
    print("Running:", cmd)
    try:
        proc = subprocess.run(cmd, shell=True)
        return proc.returncode
    except FileNotFoundError:
        print("ollama CLI not found on PATH. Install Ollama and retry.")
        return 3
    except Exception as e:
        print("Error running ollama pull:", e, file=sys.stderr)
        return 4


def main():
    model = os.environ.get("OLLAMA_PULL_MODEL") or (
        sys.argv[1] if len(sys.argv) > 1 else None
    )
    rc = pull_model(model)
    sys.exit(rc)


if __name__ == "__main__":
    main()
