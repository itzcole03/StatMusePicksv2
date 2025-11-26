"""Feature selection helpers: correlation filter and RFE wrapper."""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd


def select_by_correlation(
    df: pd.DataFrame, target_col: str = "target", thresh: float = 0.01
) -> List[str]:
    """Return feature columns with absolute correlation >= thresh with the target.

    df: DataFrame containing features and target_col. Non-numeric columns are ignored.
    """
    if target_col not in df.columns:
        raise ValueError("target_col not in DataFrame")
    numeric = df.select_dtypes(include=[np.number]).copy()
    if numeric.shape[1] <= 1:
        return []
    corrs = numeric.corr()[target_col].abs().drop(labels=[target_col], errors="ignore")
    selected = corrs[corrs >= float(thresh)].index.tolist()
    return selected


def rfe_select(
    df: pd.DataFrame,
    target_col: str = "target",
    n_features: Optional[int] = None,
    estimator=None,
    step: int = 1,
) -> List[str]:
    """Run RFE to select top features.

    If estimator is None, uses a small RandomForestRegressor. Returns list of selected column names.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.feature_selection import RFE

    if target_col not in df.columns:
        raise ValueError("target_col not in DataFrame")

    X = df.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0)
    y = df[target_col].astype(float)

    if X.shape[1] == 0:
        return []

    n_features = (
        int(n_features) if n_features is not None else max(1, min(10, X.shape[1] // 2))
    )

    if estimator is None:
        estimator = RandomForestRegressor(n_estimators=50, random_state=42)

    selector = RFE(estimator=estimator, n_features_to_select=n_features, step=step)
    selector = selector.fit(X, y)
    chosen = list(X.columns[selector.support_])
    return chosen
