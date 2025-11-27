"""List MLflow experiments and recent runs (prints run_id, status, start_time).

Run from repo root so MLflow uses ./mlruns by default.
"""

from datetime import datetime

from mlflow.tracking import MlflowClient

client = MlflowClient()
# Support different mlflow client versions: prefer `list_experiments`, fallback to `search_experiments`
if hasattr(client, "list_experiments"):
    exps = client.list_experiments()
else:
    try:
        exps = client.search_experiments(max_results=100)
    except Exception:
        exps = []
if not exps:
    print("No experiments found")
for exp in exps:
    print(f"Experiment: id={exp.experiment_id} name={exp.name}")
    runs = client.search_runs(
        exp.experiment_id, order_by=["attributes.start_time DESC"], max_results=20
    )
    if not runs:
        print("  No runs for this experiment")
    for r in runs:
        info = r.info
        st = (
            datetime.fromtimestamp(info.start_time / 1000.0)
            if info.start_time
            else None
        )
        print(f"  run_id: {info.run_id} status: {info.status} start_time: {st}")
        # print a few params/metrics if present
        if r.data.params:
            print("    params:", {k: v for k, v in r.data.params.items()})
        if r.data.metrics:
            print("    metrics:", {k: v for k, v in r.data.metrics.items()})

print("\nDone.")
