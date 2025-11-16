"""Simple calibration helpers (Platt scaling) without external deps.

Provides a small, numerically-stable fit for a logistic (Platt) scaling
model that maps uncalibrated probabilities p -> calibrated sigmoid(a*p + b).

This implementation uses a Newton-Raphson fit on a two-parameter logistic
model and depends only on numpy.
"""
from __future__ import annotations

import numpy as np
from typing import Tuple


def _sigmoid(x: np.ndarray) -> np.ndarray:
    # numerically stable sigmoid
    out = np.empty_like(x, dtype=float)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    neg = ~pos
    ex = np.exp(x[neg])
    out[neg] = ex / (1.0 + ex)
    return out


def fit_platt_scaling(p: np.ndarray, y: np.ndarray, maxiter: int = 100, tol: float = 1e-6, reg: float = 1e-8) -> Tuple[float, float]:
    """Fit Platt scaling (sigmoid(a*p + b)) using Newton-Raphson.

    p: array-like of uncalibrated probabilities (0..1)
    y: binary labels (0/1)

    Returns (a, b) parameters.
    """
    p = np.asarray(p, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if p.shape[0] != y.shape[0]:
        raise ValueError("p and y must have the same length")

    # design matrix: [p, 1]
    X = np.vstack([p, np.ones_like(p)]).T  # shape (n,2)

    # initialize weights using logit of mean label
    eps = 1e-12
    y_mean = np.clip(y.mean(), eps, 1.0 - eps)
    w = np.array([1.0, np.log(y_mean / (1.0 - y_mean))])

    for i in range(maxiter):
        z = X.dot(w)
        s = _sigmoid(z)
        # gradient of log-likelihood (with small L2 reg)
        grad = X.T.dot(y - s) - reg * w
        S = s * (1.0 - s)
        # Hessian (negative definite)
        # H = - X.T * S @ X
        XS = X * S[:, None]
        H = -(X.T.dot(XS)) - reg * np.eye(2)

        # Solve for Newton step: H * delta = grad  => delta = pinv(H) @ grad
        try:
            delta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            delta = np.linalg.pinv(H).dot(grad)

        w_new = w - delta
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new

    a, b = float(w[0]), float(w[1])
    return a, b


def apply_platt(p: np.ndarray, a: float, b: float) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    return _sigmoid(a * p + b)


def fit_platt_kfold(p: np.ndarray, y: np.ndarray, k: int = 5, random_seed: int = 0) -> tuple[float, float]:
    """Fit Platt scaling using k-fold cross-fitting and return averaged params.

    This performs K independent fits on training folds and returns the mean
    of coefficients (a, b). It's a lightweight K-fold approach to stabilize
    parameter estimates without adding sklearn dependencies.
    """
    p = np.asarray(p, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = p.shape[0]
    if n != y.shape[0]:
        raise ValueError("p and y must be same length")
    if n < k:
        # fallback to single fit
        return fit_platt_scaling(p, y)

    # shuffle indices for folds
    rng = np.random.default_rng(random_seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)

    params = []
    for i in range(k):
        # training indices exclude fold i
        train_idx = np.concatenate([folds[j] for j in range(k) if j != i])
        p_train = p[train_idx]
        y_train = y[train_idx]
        try:
            a, b = fit_platt_scaling(p_train, y_train)
            params.append((a, b))
        except Exception:
            continue

    if not params:
        return fit_platt_scaling(p, y)

    # average parameters
    a_mean = float(sum(a for a, _ in params) / len(params))
    b_mean = float(sum(b for _, b in params) / len(params))
    return a_mean, b_mean


def fit_isotonic(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit an isotonic regression (PAV) mapping p -> calibrated probability.

    Returns (xs, ys) where xs are sorted unique input p values and ys are
    non-decreasing calibrated values. Use numpy.interp to apply.
    """
    p = np.asarray(p, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    # sort by p
    order = np.argsort(p)
    xs = p[order]
    ys = y[order]

    # Pool-Adjacent-Violators algorithm to enforce non-decreasing ys
    n = len(ys)
    if n == 0:
        return np.array([]), np.array([])

    # initialize blocks
    blocks = [[i] for i in range(n)]
    block_vals = ys.copy()

    i = 0
    while i < len(blocks) - 1:
        left = blocks[i]
        right = blocks[i + 1]
        left_mean = block_vals[left].mean() if isinstance(left, list) else block_vals[left]
        right_mean = block_vals[right].mean() if isinstance(right, list) else block_vals[right]
        if left_mean <= right_mean:
            i += 1
            continue
        # merge blocks i and i+1
        merged = left + right
        merged_mean = ys[merged].mean()
        blocks[i] = merged
        del blocks[i + 1]
        # update ys values for merged block by setting them to merged_mean
        ys[merged] = merged_mean
        # backtrack
        i = max(i - 1, 0)

    # produce unique xs (representative) and block means
    xs_out = []
    ys_out = []
    for block in blocks:
        if not block:
            continue
        idxs = np.array(block)
        xs_out.append(xs[idxs].mean())
        ys_out.append(float(ys[idxs].mean()))

    return np.array(xs_out), np.array(ys_out)


def apply_isotonic(p: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Apply isotonic mapping using linear interpolation and clipping to [0,1]."""
    if xs.size == 0:
        return np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    p = np.asarray(p, dtype=float)
    # left/right fill with endpoint values
    calibrated = np.interp(p, xs, ys, left=ys[0], right=ys[-1])
    return np.clip(calibrated, 0.0, 1.0)


def fit_isotonic_kfold(p: np.ndarray, y: np.ndarray, k: int = 5, random_seed: int = 0):
    """Fit K isotonic models and return list of (xs, ys) models."""
    p = np.asarray(p, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = len(p)
    if n < k:
        xs, ys = fit_isotonic(p, y)
        return [(xs, ys)]

    rng = np.random.default_rng(random_seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    models = []
    for i in range(k):
        train_idx = np.concatenate([folds[j] for j in range(k) if j != i])
        p_train = p[train_idx]
        y_train = y[train_idx]
        try:
            xs, ys = fit_isotonic(p_train, y_train)
            models.append((xs, ys))
        except Exception:
            continue
    if not models:
        xs, ys = fit_isotonic(p, y)
        return [(xs, ys)]
    return models


def apply_isotonic_ensemble(p: np.ndarray, models) -> np.ndarray:
    """Apply ensemble of isotonic models (average predictions)."""
    p = np.asarray(p, dtype=float)
    preds = []
    for xs, ys in models:
        preds.append(apply_isotonic(p, xs, ys))
    if not preds:
        return p
    arr = np.vstack(preds)
    return np.mean(arr, axis=0)
