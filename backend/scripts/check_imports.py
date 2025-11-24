import importlib, sys, os

# Ensure repository root is on sys.path (same pattern used in scripts)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

mods = [
    'backend.services.feature_selection',
    'backend.scripts.train_orchestrator',
    'backend.scripts.hyperparam_tune'
]
ok = True
for m in mods:
    try:
        importlib.import_module(m)
        print(m + ' OK')
    except Exception as e:
        print(m + ' FAILED:', e)
        ok = False
sys.exit(0 if ok else 1)
