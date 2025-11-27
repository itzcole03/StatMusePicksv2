"""Quick smoke-check for the ModelRegistry startup preload.

Run from the repository root with PYTHONPATH set to the project root.
Example:
    $env:PYTHONPATH = "${PWD}"; python backend/scripts/check_model_registry.py
"""

from backend.services.model_registry import ModelRegistry


def main():
    mr = ModelRegistry()
    print(f"Model dir: {mr.model_dir}")
    names = mr.list_models()
    print(f"Found {len(names)} model files: {names}")
    loaded = mr.load_all_models()
    print(f"Loaded {len(loaded)} models into cache: {loaded}")
    # show cached keys
    cached = list(mr._loaded_models.keys())
    print(f"Cache keys: {cached}")


if __name__ == "__main__":
    main()
