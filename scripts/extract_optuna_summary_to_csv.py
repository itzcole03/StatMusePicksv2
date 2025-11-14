import sys
import json
from pathlib import Path
import pandas as pd

if len(sys.argv) < 2:
    print("Usage: python extract_optuna_summary_to_csv.py <optuna_study.json>")
    sys.exit(2)

p = Path(sys.argv[1])
if not p.exists():
    print('file not found', p)
    sys.exit(1)

text = p.read_text(encoding='utf-8')
# Find the '"summary":' block and cut it out before the top-level '"trials": ['
if '"summary":' not in text:
    print('no summary key found')
    sys.exit(1)

parts = text.split('"summary":', 1)
rest = parts[1]
split_token = '\n  "trials": ['
if split_token in rest:
    summary_body = rest.split(split_token, 1)[0]
else:
    # fallback: try to find closing of summary object by finding '\n  },\n'
    try:
        end_idx = rest.index('\n  },\n') + len('\n  },\n')
        summary_body = rest[:end_idx]
    except Exception as e:
        print('could not isolate summary block:', e)
        sys.exit(1)

# Reconstruct JSON that contains only the summary
# Remove trailing commas after the summary object (original file had a top-level comma before trials)
summary_body = summary_body.rstrip()
if summary_body.endswith(','):
    summary_body = summary_body[:-1]
summary_json_text = '{"summary":' + summary_body + '}'
# Ensure it is valid JSON
try:
    summary_obj = json.loads(summary_json_text)
except Exception as e:
    print('json parse failed for reconstructed summary:', e)
    sys.exit(1)

trials = summary_obj.get('summary', {}).get('trials')
if not trials:
    print('no trials found in summary')
    sys.exit(1)

# sanitize simple: convert nested dicts to JSON-friendly types; pandas will handle most
out_csv = p.parent / 'optuna_trials_extracted_from_summary.csv'
df = pd.DataFrame(trials)
df.to_csv(out_csv, index=False)
print('wrote', out_csv)
