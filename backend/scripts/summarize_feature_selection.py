import ast
from collections import Counter
from pathlib import Path

import pandas as pd


def parse_list_field(val):
    if pd.isna(val):
        return []
    if isinstance(val, (list, tuple, set)):
        return list(val)
    s = str(val).strip()
    # Try literal eval for python list strings
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
            return [str(x).strip() for x in parsed]
    except Exception:
        pass
    # Fallback: split on commas or semicolons
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts
    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
        return parts
    if s == "[]" or s == "":
        return []
    return [s]


def main(report_path=None, out_path=None):
    repo_root = Path(__file__).resolve().parents[2]
    report_path = (
        Path(report_path)
        if report_path
        else repo_root / "backend/models_store/feature_selection_report.csv"
    )
    out_path = (
        Path(out_path)
        if out_path
        else repo_root / "backend/models_store/feature_selection_summary.csv"
    )

    if not report_path.exists():
        print(f"Input report not found: {report_path}")
        return 2

    df = pd.read_csv(report_path, encoding="utf-8")

    corr_counter = Counter()
    rfe_counter = Counter()

    for _, row in df.iterrows():
        corr_feats = parse_list_field(row.get("corr_selected", ""))
        rfe_feats = parse_list_field(row.get("rfe_selected", ""))
        corr_counter.update(corr_feats)
        rfe_counter.update(rfe_feats)

    features = sorted(set(list(corr_counter.keys()) + list(rfe_counter.keys())))

    rows = []
    for f in features:
        rows.append(
            {
                "feature": f,
                "corr_count": int(corr_counter.get(f, 0)),
                "rfe_count": int(rfe_counter.get(f, 0)),
                "total_count": int(corr_counter.get(f, 0) + rfe_counter.get(f, 0)),
            }
        )

    out_df = pd.DataFrame(rows).sort_values(
        ["total_count", "feature"], ascending=[False, True]
    )
    out_df.to_csv(out_path, index=False, encoding="utf-8")

    print(f"Wrote feature-frequency summary to {out_path} (features={len(out_df)})")
    # print top 20
    print(out_df.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    import sys

    rpt = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    raise SystemExit(main(rpt, out))
