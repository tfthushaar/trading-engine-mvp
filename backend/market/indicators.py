"""Technical indicators (vectorised pandas). Shared by features, rule strategies and summaries."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI (exponential smoothing with alpha = 1/n)."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std()
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd, "sd": sd})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def stochastic(df: pd.DataFrame, n: int = 14) -> pd.Series:
    lo = df["Low"].rolling(n, min_periods=n).min()
    hi = df["High"].rolling(n, min_periods=n).max()
    return 100 * (df["Close"] - lo) / (hi - lo).replace(0, np.nan)


def snapshot(df: pd.DataFrame) -> dict:
    """Latest technical readings for a daily OHLCV frame."""
    c = df["Close"]
    last = float(c.iloc[-1])

    def val(s: pd.Series):
        v = s.iloc[-1] if len(s) else np.nan
        return None if pd.isna(v) else float(v)

    year = df.tail(252)
    out = {
        "price": last,
        "rsi_14": val(rsi(c)),
        "sma_20": val(sma(c, 20)),
        "sma_50": val(sma(c, 50)),
        "sma_200": val(sma(c, 200)),
        "macd_hist": val(macd(c)["hist"]),
        "atr_14": val(atr(df)),
        "volatility_20d_ann": val(np.log(c).diff().rolling(20).std() * np.sqrt(252)),
        "high_52w": float(year["High"].max()),
        "low_52w": float(year["Low"].min()),
        "volume_ratio_20d": float(df["Volume"].iloc[-1] / df["Volume"].tail(20).mean()) if df["Volume"].tail(20).mean() else None,
        "return_1m": float(c.iloc[-1] / c.iloc[-22] - 1) if len(c) > 22 else None,
        "return_3m": float(c.iloc[-1] / c.iloc[-64] - 1) if len(c) > 64 else None,
        "return_1y": float(c.iloc[-1] / c.iloc[-253] - 1) if len(c) > 253 else None,
    }
    for k in ("sma_20", "sma_50", "sma_200"):
        out[f"above_{k}"] = None if out[k] is None else bool(last > out[k])
    trend_votes = [out["above_sma_20"], out["above_sma_50"], out["above_sma_200"]]
    votes = [v for v in trend_votes if v is not None]
    out["trend"] = "up" if votes and sum(votes) == len(votes) else "down" if votes and not any(votes) else "mixed"
    return out
