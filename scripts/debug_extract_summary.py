import json
from pathlib import Path
p = Path('backend/models_store/player_1001/versions/0d82ac641c11/optuna_study.json')
text = p.read_text(encoding='utf-8')
parts = text.split('"summary":', 1)
rest = parts[1]
split_token = '\n  "trials": ['
if split_token in rest:
    summary_body = rest.split(split_token, 1)[0]
else:
    summary_body = rest
summary_json_text = '{"summary":' + summary_body
print('--- reconstructed preview (first 800 chars) ---')
print(summary_json_text[:800])
print('--- repr preview ---')
print(repr(summary_json_text[:800]))
try:
    obj = json.loads(summary_json_text)
    print('JSON parsed ok; summary keys:', list(obj.get('summary', {}).keys()))
except Exception as e:
    import traceback
    traceback.print_exc()
    # print nearby context where decode error occurred
    try:
        err = e
        if hasattr(err, 'lineno') and hasattr(err, 'colno'):
            ln = err.lineno
            col = err.colno
            lines = summary_json_text.splitlines()
            start = max(0, ln-3)
            for i in range(start, min(len(lines), ln+2)):
                print(i+1, lines[i])
    except Exception:
        pass
