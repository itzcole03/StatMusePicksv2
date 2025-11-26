from backend.services.model_registry import ModelRegistry
class M:
    def __init__(self):
        self._kept_contextual_features=['feat_a','feat_b']
        self._feature_list=['feat_a','feat_b','feat_c']

m=M()
reg=ModelRegistry(model_dir='tmp_models_test')
reg.save_model('Dummy Player', m, version='v1', notes='n')
import json, os
p=reg._model_path('Dummy Player')
s=os.path.splitext(p)[0]+'_metadata.json'
print('sidecar',s)
print(open(s).read())
