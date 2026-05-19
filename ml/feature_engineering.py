"""
Shared feature engineering pipeline.
All ML models consume features produced by this module.
"""
import numpy as np
import pandas as pd
import yfinance as yf


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def compute_macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    return macd, signal, hist


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    width = (upper - lower) / sma
    return upper, lower, width


def build_features(ticker: str, period: str = "2y") -> pd.DataFrame:
    """
    Build the full feature matrix for a ticker.
    Returns a DataFrame with one row per day, ready for ML models.
    """
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval="1d")
    if hist.empty or len(hist) < 60:
        return pd.DataFrame()

    df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # ── Technical indicators ──────────────────────────────────────────────────
    df["rsi_14"] = compute_rsi(close, 14)
    df["rsi_28"] = compute_rsi(close, 28)
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(close)
    df["bb_upper"], df["bb_lower"], df["bb_width"] = compute_bollinger_bands(close)
    df["atr_14"] = compute_atr(high, low, close, 14)
    df["atr_28"] = compute_atr(high, low, close, 28)

    df["ema_9"]   = close.ewm(span=9).mean()
    df["ema_21"]  = close.ewm(span=21).mean()
    df["ema_50"]  = close.ewm(span=50).mean()
    df["ema_200"] = close.ewm(span=200).mean()

    df["volume_ratio_20d"] = volume / volume.rolling(20).mean()

    # Price position vs range
    df["price_vs_52w_high"] = close / high.rolling(252).max()
    df["price_vs_52w_low"]  = close / low.rolling(252).min()

    # Stochastics
    low14  = low.rolling(14).min()
    high14 = high.rolling(14).max()
    df["stoch_k"] = (close - low14) / (high14 - low14) * 100
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # OBV slope
    obv = (np.sign(close.diff()) * volume).cumsum()
    df["obv_slope_5d"] = obv.diff(5)

    # Returns
    df["return_1d"] = close.pct_change(1)
    df["return_5d"] = close.pct_change(5)
    df["return_20d"] = close.pct_change(20)

    # ── Target variable (next-day direction for classification) ───────────────
    df["target_direction"] = (close.shift(-1) > close).astype(int)

    df.dropna(inplace=True)
    return df


def get_feature_columns() -> list[str]:
    """Return the ordered list of feature column names used by all models."""
    return [
        "rsi_14", "rsi_28", "macd", "macd_signal", "macd_hist",
        "bb_width", "atr_14", "atr_28",
        "ema_9", "ema_21", "ema_50", "ema_200",
        "volume_ratio_20d", "price_vs_52w_high", "price_vs_52w_low",
        "stoch_k", "stoch_d", "obv_slope_5d",
        "return_1d", "return_5d", "return_20d",
    ]
