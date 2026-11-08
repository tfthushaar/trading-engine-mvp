"""
Single backtest engine shared by neural-network signals and rule strategies.

positions[t] is the exposure chosen at the close of day t (1 = long, 0 = flat, -1 = short). It earns
the close-to-close return from t to t+1. Costs are charged on turnover |pos_t - pos_{t-1}|.
All metrics are computed from the daily return stream.
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS = 252
PERIODS_PER_YEAR = {"1h": 252 * 7, "60m": 252 * 7, "1d": 252, "1wk": 52, "1mo": 12}


def periods_per_year(interval: str) -> int:
    return PERIODS_PER_YEAR.get(interval, TRADING_DAYS)


def performance(returns: np.ndarray, exposure: np.ndarray | None = None, ppy: int = TRADING_DAYS) -> dict:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return {k: None for k in ("total_return", "cagr", "ann_vol", "sharpe", "sortino", "max_drawdown", "calmar", "hit_rate", "exposure")}
    equity = np.cumprod(1.0 + r)
    total = float(equity[-1] - 1.0)
    years = r.size / ppy
    cagr = float(equity[-1] ** (1.0 / years) - 1.0) if years > 0 and equity[-1] > 0 else None
    sd = float(r.std(ddof=1)) if r.size > 1 else 0.0
    if sd < 1e-12:  # flat returns: volatility is numerically zero, so a ratio would be meaningless
        sd = 0.0
    vol = sd * float(np.sqrt(ppy))
    sharpe = float(r.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0
    downside = r[r < 0]
    dd_std = float(np.sqrt((downside**2).mean())) if downside.size else 0.0
    sortino = float(r.mean() / dd_std * np.sqrt(ppy)) if dd_std > 1e-12 else None
    peak = np.maximum.accumulate(equity)
    max_dd = float((equity / peak - 1.0).min())
    calmar = float(cagr / abs(max_dd)) if cagr is not None and max_dd < 0 else None
    active = r != 0
    return {
        "total_return": round(total, 6),
        "cagr": None if cagr is None else round(cagr, 6),
        "ann_vol": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "sortino": None if sortino is None else round(sortino, 4),
        "max_drawdown": round(max_dd, 6),
        "calmar": None if calmar is None else round(calmar, 4),
        "hit_rate": round(float((r[active] > 0).mean()), 4) if active.any() else None,
        "exposure": round(float(np.mean(np.abs(exposure))), 4) if exposure is not None and len(exposure) else None,
    }


def run_positions(next_returns: np.ndarray, positions: np.ndarray, cost_bps: float = 5.0, ppy: int = TRADING_DAYS) -> dict:
    """
    next_returns[t]: simple return from t to t+1. positions[t]: exposure held over that interval.
    Returns daily strategy returns, equity curve, turnover and trade list (index based).
    """
    rn = np.nan_to_num(np.asarray(next_returns, dtype=float))
    pos = np.asarray(positions, dtype=float)
    prev = np.concatenate([[0.0], pos[:-1]])
    turnover = np.abs(pos - prev)
    strat = pos * rn - turnover * cost_bps / 1e4
    equity = np.cumprod(1.0 + strat)
    trades = []
    entry = None
    for t in range(len(pos)):
        if pos[t] != 0 and (t == 0 or pos[t] != prev[t]):
            if entry is not None:
                trades.append((entry, t))
            entry = t
        elif pos[t] == 0 and entry is not None:
            trades.append((entry, t))
            entry = None
    if entry is not None:
        trades.append((entry, len(pos)))
    trade_returns = [float(np.prod(1.0 + strat[a:b]) - 1.0) for a, b in trades]
    wins = [x for x in trade_returns if x > 0]
    losses = [-x for x in trade_returns if x < 0]
    pf = (sum(wins) / sum(losses)) if losses else None
    return {
        "returns": strat,
        "equity": equity,
        "turnover": float(turnover.sum()),
        "trades": trades,
        "trade_returns": trade_returns,
        "n_trades": len(trades),
        "win_rate": round(len(wins) / len(trade_returns), 4) if trade_returns else None,
        "profit_factor": None if pf is None else round(float(pf), 4),
        "metrics": performance(strat, pos, ppy),
    }


def buy_and_hold(next_returns: np.ndarray, ppy: int = TRADING_DAYS) -> dict:
    return run_positions(next_returns, np.ones(len(next_returns)), cost_bps=0.0, ppy=ppy)
