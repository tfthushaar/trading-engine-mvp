"""
Strategy definitions for the multi-agent competition.
Each strategy is a pure function: (price_history: pd.DataFrame) -> list[Trade]

5 canonical strategies that each agent tests independently:
  1. RSI Mean Reversion
  2. EMA Trend Following
  3. Bollinger Band Breakout
  4. MACD Momentum
  5. Volume + Price Composite
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import pandas as pd
import numpy as np


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    direction: str  # "long" | "short"
    pnl_pct: float
    hold_days: int


def run_strategy(df: pd.DataFrame, signal_fn: Callable[[pd.DataFrame], pd.Series]) -> list[Trade]:
    """Generic backtester: applies a signal function and simulates trades."""
    if df.empty or len(df) < 30:
        return []

    signals = signal_fn(df)
    trades: list[Trade] = []
    position = False
    entry_idx = 0
    entry_price = 0.0

    for i in range(1, len(df)):
        sig = signals.iloc[i]
        price = df["Close"].iloc[i]
        date = str(df.index[i])[:10]

        if not position and sig == 1:
            position = True
            entry_price = price
            entry_idx = i

        elif position and sig == -1:
            exit_price = price
            hold = i - entry_idx
            pnl = (exit_price - entry_price) / entry_price * 100
            trades.append(Trade(
                entry_date=str(df.index[entry_idx])[:10],
                exit_date=date,
                entry_price=round(entry_price, 4),
                exit_price=round(exit_price, 4),
                direction="long",
                pnl_pct=round(pnl, 3),
                hold_days=hold,
            ))
            position = False

    return trades


# ── Strategy 1: RSI Mean Reversion ──────────────────────────────────────────
def rsi_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """Buy RSI < 30, sell RSI > 65."""
    close = df["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss)

    signals = pd.Series(0, index=df.index)
    signals[rsi < 30] = 1   # buy
    signals[rsi > 65] = -1  # sell
    return signals


# ── Strategy 2: EMA Trend Following ─────────────────────────────────────────
def ema_trend_following(df: pd.DataFrame) -> pd.Series:
    """Buy when 9 EMA crosses above 21 EMA, sell when crosses below."""
    close = df["Close"]
    ema9 = close.ewm(span=9).mean()
    ema21 = close.ewm(span=21).mean()

    signals = pd.Series(0, index=df.index)
    cross_up = (ema9 > ema21) & (ema9.shift(1) <= ema21.shift(1))
    cross_down = (ema9 < ema21) & (ema9.shift(1) >= ema21.shift(1))
    signals[cross_up] = 1
    signals[cross_down] = -1
    return signals


# ── Strategy 3: Bollinger Band Breakout ─────────────────────────────────────
def bollinger_breakout(df: pd.DataFrame) -> pd.Series:
    """Buy on upper band breakout with volume confirmation, sell on mean reversion."""
    close = df["Close"]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20

    vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean()

    signals = pd.Series(0, index=df.index)
    signals[(close > upper) & (vol_ratio > 1.3)] = 1
    signals[close < sma20] = -1
    return signals


# ── Strategy 4: MACD Momentum ────────────────────────────────────────────────
def macd_momentum(df: pd.DataFrame) -> pd.Series:
    """Buy on MACD histogram turning positive, sell when it turns negative."""
    close = df["Close"]
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    hist = macd - signal_line

    signals = pd.Series(0, index=df.index)
    hist_cross_up = (hist > 0) & (hist.shift(1) <= 0)
    hist_cross_down = (hist < 0) & (hist.shift(1) >= 0)
    signals[hist_cross_up] = 1
    signals[hist_cross_down] = -1
    return signals


# ── Strategy 5: Volume + Price Composite ────────────────────────────────────
def volume_price_composite(df: pd.DataFrame) -> pd.Series:
    """
    Buy when: price > 20 SMA AND volume > 1.5x avg AND RSI 40-60 (healthy momentum).
    Sell when: price < 20 SMA OR RSI > 70.
    """
    close = df["Close"]
    sma20 = close.rolling(20).mean()
    vol_ratio = df["Volume"] / df["Volume"].rolling(20).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss)

    signals = pd.Series(0, index=df.index)
    buy_cond = (close > sma20) & (vol_ratio > 1.5) & (rsi >= 40) & (rsi <= 65)
    sell_cond = (close < sma20) | (rsi > 72)
    signals[buy_cond] = 1
    signals[sell_cond] = -1
    return signals


# ── Strategy registry ────────────────────────────────────────────────────────
STRATEGIES: dict[str, tuple[str, Callable]] = {
    "rsi_mean_reversion": (
        "RSI Mean Reversion",
        rsi_mean_reversion,
    ),
    "ema_trend_following": (
        "EMA Trend Following",
        ema_trend_following,
    ),
    "bollinger_breakout": (
        "Bollinger Band Breakout",
        bollinger_breakout,
    ),
    "macd_momentum": (
        "MACD Momentum",
        macd_momentum,
    ),
    "volume_price_composite": (
        "Volume + Price Composite",
        volume_price_composite,
    ),
}
