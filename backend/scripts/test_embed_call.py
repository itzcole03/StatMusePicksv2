from backend.services.llm_feature_service import create_default_service

svc = create_default_service()
print('Service created:', svc)
text = 'Test embedding fallback for offline demo'
emb = svc.generate_embedding(text)
print('Embedding is None?', emb is None)
if emb:
    print('len:', len(emb))
    print('first 5:', emb[:5])
