"""
Feature engineering and dataset construction for sequence models.

Leakage controls:
  * Features at day t only use information available at the close of day t.
  * Chronological split (train -> validation -> test), never shuffled across time.
  * Embargo: the last `horizon` samples of train and validation are dropped, because their
    labels overlap the next split's period.
  * Standardisation statistics are fitted on training rows only, then applied everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend.market import indicators as ind

FEATURES: dict[str, str] = {
    "ret_1": "1-day log return",
    "ret_5": "5-day log return",
    "ret_20": "20-day log return",
    "range": "High-low range / close",
    "body": "Close vs open (intraday log return)",
    "volume_z": "Log-volume z-score vs 20 days",
    "rsi": "RSI(14), centred and scaled",
    "macd": "MACD histogram / close",
    "sma20_gap": "Close / SMA(20) - 1",
    "sma50_gap": "Close / SMA(50) - 1",
    "volatility": "20-day realised volatility",
    "atr": "ATR(14) / close",
    "bb_pos": "Position inside Bollinger bands",
    "mkt_ret_5": "S&P 500 (SPY) 5-day log return",
    "vix": "VIX level (log)",
}
DEFAULT_FEATURES = ["ret_1", "ret_5", "ret_20", "range", "body", "volume_z", "rsi", "macd", "sma20_gap", "sma50_gap", "volatility", "atr"]
MARKET_FEATURES = {"mkt_ret_5", "vix"}


def compute_features(df: pd.DataFrame, market: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """All candidate features for a daily OHLCV frame. Rows with incomplete look-backs are dropped."""
    c, o, h, lo, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
    logc = np.log(c)
    r1 = logc.diff()
    logv = np.log(v.replace(0, np.nan)).ffill()
    bb = ind.bollinger(c)
    f = pd.DataFrame(index=df.index)
    f["ret_1"] = r1
    f["ret_5"] = logc.diff(5)
    f["ret_20"] = logc.diff(20)
    f["range"] = (h - lo) / c
    f["body"] = np.log(c / o)
    f["volume_z"] = (logv - logv.rolling(20).mean()) / logv.rolling(20).std().replace(0, np.nan)
    f["rsi"] = (ind.rsi(c) - 50.0) / 50.0
    f["macd"] = ind.macd(c)["hist"] / c
    f["sma20_gap"] = c / ind.sma(c, 20) - 1.0
    f["sma50_gap"] = c / ind.sma(c, 50) - 1.0
    f["volatility"] = r1.rolling(20).std()
    f["atr"] = ind.atr(df) / c
    f["bb_pos"] = (c - bb["mid"]) / (2 * bb["sd"]).replace(0, np.nan)
    if market:
        spy = market.get("SPY")
        if spy is not None and not spy.empty:
            f["mkt_ret_5"] = np.log(spy["Close"]).diff(5).reindex(f.index).ffill()
        vix = market.get("^VIX")
        if vix is not None and not vix.empty:
            f["vix"] = np.log(vix["Close"]).reindex(f.index).ffill()
    return f.replace([np.inf, -np.inf], np.nan)


@dataclass
class Dataset:
    features: list[str]
    window: int
    horizon: int
    task: str
    X: np.ndarray            # (N, W, F) standardised windows with known labels
    y: np.ndarray            # (N,) class labels (0/1) or scaled forward returns
    fwd_ret: np.ndarray      # (N,) forward log return over the horizon (unscaled)
    next_ret: np.ndarray     # (N,) simple return from t to t+1 (for daily backtests)
    dates: np.ndarray        # (N,) sample end dates (decision time t), ISO strings
    close: np.ndarray        # (N,) close at t
    train: np.ndarray        # index arrays into the N samples
    val: np.ndarray
    test: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    y_scale: float           # regression target scale (std of train forward returns)
    latest_X: np.ndarray     # (1, W, F) most recent window (label not yet known)
    latest_date: str
    latest_close: float
    meta: dict = field(default_factory=dict)

    def split(self, name: str):
        idx = getattr(self, name)
        return self.X[idx], self.y[idx]


def build_dataset(
    df: pd.DataFrame,
    features: list[str] | None = None,
    window: int = 30,
    horizon: int = 5,
    task: str = "classification",
    market: dict[str, pd.DataFrame] | None = None,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    min_samples: int = 200,
) -> Dataset:
    features = [f for f in (features or DEFAULT_FEATURES) if f in FEATURES]
    if not features:
        raise ValueError("select at least one feature")
    feat = compute_features(df, market)
    missing = [f for f in features if f not in feat.columns]
    if missing:
        raise ValueError(f"features unavailable for this symbol: {', '.join(missing)}")
    feat = feat[features].dropna()
    close = df["Close"].reindex(feat.index)
    rows = len(feat)

    logc = np.log(close.to_numpy())
    cl = close.to_numpy()
    # Forward targets for each row t (NaN when the future is not observed yet)
    fwd = np.full(rows, np.nan)
    fwd[: rows - horizon] = logc[horizon:] - logc[:-horizon]
    nxt = np.full(rows, np.nan)
    nxt[:-1] = cl[1:] / cl[:-1] - 1.0

    # Candidate samples: rows t with a full window behind them
    ends = np.arange(window - 1, rows)
    labelled = ends[~np.isnan(fwd[ends])]
    n = len(labelled)
    if n < min_samples:
        raise ValueError(f"not enough history: {n} labelled samples (need {min_samples}); use a longer period or smaller window")

    n_test = max(int(n * test_frac), 20)
    n_val = max(int(n * val_frac), 20)
    n_train = n - n_val - n_test
    emb = horizon  # embargo
    train = np.arange(0, max(n_train - emb, 1))
    val = np.arange(n_train, max(n_train + n_val - emb, n_train + 1))
    test = np.arange(n_train + n_val, n)

    # Standardise with statistics from rows that only training windows can see
    last_train_row = labelled[train[-1]]
    vals = feat.to_numpy(dtype=float)
    mean = vals[: last_train_row + 1].mean(axis=0)
    std = vals[: last_train_row + 1].std(axis=0)
    std[std < 1e-12] = 1.0
    z = np.clip((vals - mean) / std, -5.0, 5.0)

    windows = np.lib.stride_tricks.sliding_window_view(z, window, axis=0).transpose(0, 2, 1)  # (rows-W+1, W, F)
    X = np.ascontiguousarray(windows[labelled - (window - 1)])
    fwd_l = fwd[labelled]
    y_scale = float(np.std(fwd_l[train])) or 1.0
    if task == "classification":
        y = (fwd_l > 0).astype(float)
    elif task == "regression":
        y = fwd_l / y_scale
    else:
        raise ValueError("task must be 'classification' or 'regression'")

    dates = np.array([d.strftime("%Y-%m-%d") for d in feat.index[labelled]])
    latest_row = rows - 1
    return Dataset(
        features=features, window=window, horizon=horizon, task=task,
        X=X, y=y, fwd_ret=fwd_l, next_ret=nxt[labelled], dates=dates, close=cl[labelled],
        train=train, val=val, test=test, mean=mean, std=std, y_scale=y_scale,
        latest_X=np.ascontiguousarray(windows[latest_row - (window - 1)][None]),
        latest_date=feat.index[latest_row].strftime("%Y-%m-%d"),
        latest_close=float(cl[latest_row]),
        meta={
            "rows": rows,
            "samples": n,
            "first_date": feat.index[0].strftime("%Y-%m-%d"),
            "last_date": feat.index[-1].strftime("%Y-%m-%d"),
            "embargo": emb,
        },
    )


def split_summary(ds: Dataset) -> dict:
    out = {}
    for name in ("train", "val", "test"):
        idx = getattr(ds, name)
        y = ds.y[idx]
        part = {"n": int(len(idx)), "start": ds.dates[idx[0]], "end": ds.dates[idx[-1]]}
        if ds.task == "classification":
            part["up_rate"] = round(float(y.mean()), 4)
        else:
            part["mean_fwd_ret"] = round(float(ds.fwd_ret[idx].mean()), 6)
        out[name] = part
    return out
