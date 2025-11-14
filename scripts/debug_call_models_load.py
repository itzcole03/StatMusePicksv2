from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app)
rv = client.post('/api/models/load', json={'player':'John Doe','model_dir':'backend/models_store'})
print('STATUS', rv.status_code)
print(rv.text)
