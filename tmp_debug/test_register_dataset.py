import sys
import os
from pathlib import Path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.dataset_versioning import register_manifest, list_registered, latest_registered

# locate previously exported test manifest
manifest_glob = Path('backend/models_store/datasets_test').glob('**/manifest.json')
manifest = None
for p in manifest_glob:
    manifest = p
    break
if not manifest:
    print('no manifest found under backend/models_store/datasets_test')
    raise SystemExit(1)

print('found manifest at', manifest)
res = register_manifest(str(manifest), registry_dir='backend/models_store/datasets')
print('registered manifest:', bool(res))
print('latest for test_dataset:', latest_registered('test_dataset'))
print('all registered:', list_registered())
