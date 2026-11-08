"""
Rule-based strategies: the five classic strategies used as baselines, plus a no-code rule language.

All strategies output a position series (1 = long, 0 = flat) decided at each close, which is then
evaluated by the shared engine (strategies.engine) exactly like the neural-network signals.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from backend.market import indicators as ind
from backend.strategies import engine


def _state_machine(buy: pd.Series, sell: pd.Series) -> np.ndarray:
    """Enter on buy when flat, exit on sell when long (sell wins ties)."""
    sig = pd.Series(np.nan, index=buy.index)
    sig[buy.fillna(False)] = 1.0
    sig[sell.fillna(False)] = 0.0
    return sig.ffill().fillna(0.0).to_numpy()


def rsi_mean_reversion(df: pd.DataFrame) -> np.ndarray:
    r = ind.rsi(df["Close"])
    return _state_machine(r < 30, r > 65)


def ema_trend(df: pd.DataFrame) -> np.ndarray:
    fast, slow = ind.ema(df["Close"], 9), ind.ema(df["Close"], 21)
    return _state_machine(fast > slow, fast < slow)


def bollinger_breakout(df: pd.DataFrame) -> np.ndarray:
    c = df["Close"]
    bb = ind.bollinger(c)
    vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean()
    return _state_machine((c > bb["upper"]) & (vol_ratio > 1.3), c < bb["mid"])


def macd_momentum(df: pd.DataFrame) -> np.ndarray:
    h = ind.macd(df["Close"])["hist"]
    return _state_machine((h > 0) & (h.shift(1) <= 0), (h < 0) & (h.shift(1) >= 0))


def volume_price(df: pd.DataFrame) -> np.ndarray:
    c = df["Close"]
    sma20 = ind.sma(c, 20)
    vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean()
    r = ind.rsi(c)
    return _state_machine((c > sma20) & (vol_ratio > 1.5) & (r >= 40) & (r <= 65), (c < sma20) | (r > 72))


STRATEGIES: dict[str, tuple[str, str, Callable[[pd.DataFrame], np.ndarray]]] = {
    "rsi_mean_reversion": ("RSI Mean Reversion", "Buy when RSI(14) < 30, sell when RSI > 65.", rsi_mean_reversion),
    "ema_trend": ("EMA Trend", "Long while EMA(9) > EMA(21).", ema_trend),
    "bollinger_breakout": ("Bollinger Breakout", "Buy a close above the upper band on 1.3x volume; exit below the middle band.", bollinger_breakout),
    "macd_momentum": ("MACD Momentum", "Buy when the MACD histogram turns positive, sell when it turns negative.", macd_momentum),
    "volume_price": ("Volume + Price", "Buy above SMA(20) on 1.5x volume with RSI 40-65; exit below SMA(20) or RSI > 72.", volume_price),
}


def next_returns(close: pd.Series) -> np.ndarray:
    c = close.to_numpy(dtype=float)
    out = np.full(len(c), np.nan)
    out[:-1] = c[1:] / c[:-1] - 1.0
    return out


def evaluate_window(df: pd.DataFrame, positions: np.ndarray, start: str | None, end: str | None, cost_bps: float) -> dict:
    """Run the engine on [start, end] (inclusive). Indicators were computed on full history (no warm-up gap)."""
    rn = next_returns(df["Close"])
    mask = np.ones(len(df), dtype=bool)
    if start:
        mask &= df.index >= pd.Timestamp(start)
    if end:
        mask &= df.index <= pd.Timestamp(end)
    mask &= ~np.isnan(rn)
    res = engine.run_positions(rn[mask], positions[mask], cost_bps)
    intraday = bool((df.index.normalize() != df.index).any())
    fmt = "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"
    res["dates"] = [d.strftime(fmt) for d in df.index[mask]]
    res["positions"] = positions[mask]
    return res


# ---------------------------------------------------------------------------------------------
# No-code rule language
# ---------------------------------------------------------------------------------------------
OPERANDS: dict[str, dict] = {
    "price": {"label": "Price", "period": False},
    "sma": {"label": "SMA", "period": True, "default": 50},
    "ema": {"label": "EMA", "period": True, "default": 20},
    "rsi": {"label": "RSI", "period": True, "default": 14},
    "macd": {"label": "MACD line", "period": False},
    "macd_signal": {"label": "MACD signal", "period": False},
    "macd_hist": {"label": "MACD histogram", "period": False},
    "bb_upper": {"label": "Bollinger upper", "period": True, "default": 20},
    "bb_lower": {"label": "Bollinger lower", "period": True, "default": 20},
    "atr_pct": {"label": "ATR % of price", "period": True, "default": 14},
    "volume_ratio": {"label": "Volume / avg", "period": True, "default": 20},
    "stoch": {"label": "Stochastic %K", "period": True, "default": 14},
    "return": {"label": "N-day return %", "period": True, "default": 5},
    "value": {"label": "Value", "period": False},
}
OPERATORS = {">": "is above", "<": "is below", "crosses_above": "crosses above", "crosses_below": "crosses below"}


def operand_series(df: pd.DataFrame, op: dict) -> pd.Series:
    kind = op.get("kind", "value")
    if kind not in OPERANDS:
        raise ValueError(f"unknown operand {kind!r}")
    try:
        n = int(float(op.get("period") or OPERANDS[kind].get("default", 14)))
    except (TypeError, ValueError):
        raise ValueError(f"the period for {OPERANDS[kind]['label']} must be a number") from None
    n = min(max(n, 2), 250)
    c = df["Close"]
    if kind == "value":
        raw = op.get("value")
        if raw is None or raw == "":
            raise ValueError("enter a number for every Value condition")
        try:
            return pd.Series(float(raw), index=df.index)
        except (TypeError, ValueError):
            raise ValueError("enter a number for every Value condition") from None
    if kind == "price":
        return c
    if kind == "sma":
        return ind.sma(c, n)
    if kind == "ema":
        return ind.ema(c, n)
    if kind == "rsi":
        return ind.rsi(c, n)
    if kind in ("macd", "macd_signal", "macd_hist"):
        m = ind.macd(c)
        return m[{"macd": "macd", "macd_signal": "signal", "macd_hist": "hist"}[kind]]
    if kind in ("bb_upper", "bb_lower"):
        return ind.bollinger(c, n)["upper" if kind == "bb_upper" else "lower"]
    if kind == "atr_pct":
        return ind.atr(df, n) / c * 100
    if kind == "volume_ratio":
        return df["Volume"] / df["Volume"].rolling(n).mean()
    if kind == "stoch":
        return ind.stochastic(df, n)
    if kind == "return":
        return c.pct_change(n) * 100
    raise ValueError(kind)  # pragma: no cover


def condition_series(df: pd.DataFrame, cond: dict) -> pd.Series:
    a, b = operand_series(df, cond["left"]), operand_series(df, cond["right"])
    op = cond.get("op", ">")
    if op == ">":
        out = a > b
    elif op == "<":
        out = a < b
    elif op == "crosses_above":
        out = (a > b) & (a.shift(1) <= b.shift(1))
    elif op == "crosses_below":
        out = (a < b) & (a.shift(1) >= b.shift(1))
    else:
        raise ValueError(f"unknown operator {op!r}")
    return out & a.notna() & b.notna()


def rule_positions(df: pd.DataFrame, entry: list[dict], exit: list[dict], stop_loss_pct: float = 0.0, take_profit_pct: float = 0.0) -> np.ndarray:
    """Entry when ALL entry conditions hold; exit when ANY exit condition holds, or stop/target is hit."""
    if not entry:
        raise ValueError("add at least one entry condition")
    buy = np.logical_and.reduce([condition_series(df, c).to_numpy() for c in entry])
    sell = np.logical_or.reduce([condition_series(df, c).to_numpy() for c in exit]) if exit else np.zeros(len(df), bool)
    close = df["Close"].to_numpy()
    pos = np.zeros(len(df))
    holding, entry_px = False, 0.0
    for t in range(len(df)):
        if holding:
            ret = close[t] / entry_px - 1.0
            hit_stop = stop_loss_pct > 0 and ret <= -stop_loss_pct / 100
            hit_target = take_profit_pct > 0 and ret >= take_profit_pct / 100
            if sell[t] or hit_stop or hit_target:
                holding = False
        elif buy[t]:
            holding, entry_px = True, close[t]
        pos[t] = 1.0 if holding else 0.0
    return pos


def trade_list(dates: list[str], res: dict) -> list[dict]:
    out = []
    for (a, b), r in zip(res["trades"], res["trade_returns"]):
        out.append({"entry": dates[a], "exit": dates[min(b, len(dates) - 1)], "days": int(b - a), "return": round(r, 5)})
    return out
