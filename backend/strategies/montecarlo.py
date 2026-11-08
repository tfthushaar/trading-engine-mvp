"""Bootstrap Monte Carlo of a strategy's daily returns (vectorised)."""
from __future__ import annotations

import numpy as np


def bootstrap(daily_returns: np.ndarray, n_sims: int = 2000, horizon: int = 252, block: int = 5, seed: int = 0) -> dict:
    """
    Stationary-ish block bootstrap: resample blocks of `block` consecutive days to keep short-range
    autocorrelation. Returns percentile equity bands and risk statistics.
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 20:
        raise ValueError("need at least 20 daily returns for a Monte Carlo simulation")
    n_sims = int(min(max(n_sims, 100), 10000))
    horizon = int(min(max(horizon, 20), 756))
    block = int(min(max(block, 1), 20))
    rng = np.random.default_rng(seed)
    n_blocks = -(-horizon // block)
    starts = rng.integers(0, r.size - block + 1, size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_sims, -1)[:, :horizon]
    sims = r[idx]
    equity = np.cumprod(1.0 + sims, axis=1)
    equity = np.concatenate([np.ones((n_sims, 1)), equity], axis=1)
    peak = np.maximum.accumulate(equity, axis=1)
    mdd = (equity / peak - 1.0).min(axis=1)
    final = equity[:, -1] - 1.0
    pct = [5, 25, 50, 75, 95]
    bands = np.percentile(equity, pct, axis=0)
    hist_counts, hist_edges = np.histogram(final, bins=30)
    return {
        "n_sims": n_sims,
        "horizon_days": horizon,
        "block": block,
        "bands": {f"p{p}": np.round(bands[i], 5).tolist() for i, p in enumerate(pct)},
        "final_return": {f"p{p}": round(float(np.percentile(final, p)), 5) for p in pct},
        "prob_loss": round(float((final < 0).mean()), 4),
        "prob_drawdown_20": round(float((mdd <= -0.2).mean()), 4),
        "max_drawdown": {"median": round(float(np.median(mdd)), 5), "p5": round(float(np.percentile(mdd, 5)), 5)},
        "histogram": {"counts": hist_counts.tolist(), "edges": np.round(hist_edges, 5).tolist()},
    }
