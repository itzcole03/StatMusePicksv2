import sys
import os
from pathlib import Path
# ensure the repository root is on sys.path so `backend` package imports work
repo_root = str(Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from fastapi.testclient import TestClient
from backend.main import app
import joblib, shutil
from pathlib import Path
from backend.tests.dummy_model import DummyModel
MODELS_DIR = Path('backend/models_store')
if MODELS_DIR.exists():
    shutil.rmtree(MODELS_DIR)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
joblib.dump(DummyModel(), MODELS_DIR / 'John_Doe.pkl')
client = TestClient(app)
rv = client.post('/api/models/load', json={'player': 'John Doe', 'model_dir': str(MODELS_DIR)})
print('status', rv.status_code)
try:
    print('json', rv.json())
except Exception as e:
    print('text', rv.text)
