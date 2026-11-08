"""
Panel (cross-sectional) datasets for the global model.

One network is trained on many symbols at once. The features are scale-free (returns, ratios,
z-scores), so a model trained on the panel can score any symbol, including ones it never saw.
Shared by the offline trainer (research/) and the online inference code (global_model.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.dl.data import DEFAULT_FEATURES, compute_features

UNIVERSE: dict[str, tuple[str, str]] = {
    # symbol: (name, sector)
    "SPY": ("S&P 500 ETF", "Index"), "QQQ": ("Nasdaq 100 ETF", "Index"), "IWM": ("Russell 2000 ETF", "Index"),
    "DIA": ("Dow Jones ETF", "Index"),
    "XLK": ("Technology Select", "Sector ETF"), "XLF": ("Financials Select", "Sector ETF"), "XLV": ("Health Care Select", "Sector ETF"),
    "XLE": ("Energy Select", "Sector ETF"), "XLY": ("Consumer Discretionary Select", "Sector ETF"), "XLI": ("Industrials Select", "Sector ETF"),
    "XLU": ("Utilities Select", "Sector ETF"), "XLB": ("Materials Select", "Sector ETF"), "XLP": ("Consumer Staples Select", "Sector ETF"),
    "AAPL": ("Apple", "Technology"), "MSFT": ("Microsoft", "Technology"), "NVDA": ("NVIDIA", "Technology"),
    "AVGO": ("Broadcom", "Technology"), "AMD": ("AMD", "Technology"), "INTC": ("Intel", "Technology"),
    "ORCL": ("Oracle", "Technology"), "CRM": ("Salesforce", "Technology"), "ADBE": ("Adobe", "Technology"),
    "GOOGL": ("Alphabet", "Communication"), "META": ("Meta Platforms", "Communication"), "NFLX": ("Netflix", "Communication"),
    "DIS": ("Disney", "Communication"),
    "AMZN": ("Amazon", "Consumer Disc."), "TSLA": ("Tesla", "Consumer Disc."), "HD": ("Home Depot", "Consumer Disc."),
    "MCD": ("McDonald's", "Consumer Disc."),
    "WMT": ("Walmart", "Consumer Staples"), "COST": ("Costco", "Consumer Staples"), "KO": ("Coca-Cola", "Consumer Staples"),
    "PG": ("Procter & Gamble", "Consumer Staples"),
    "JPM": ("JPMorgan Chase", "Financials"), "BAC": ("Bank of America", "Financials"), "GS": ("Goldman Sachs", "Financials"),
    "V": ("Visa", "Financials"), "MA": ("Mastercard", "Financials"),
    "JNJ": ("Johnson & Johnson", "Health Care"), "UNH": ("UnitedHealth", "Health Care"), "LLY": ("Eli Lilly", "Health Care"),
    "PFE": ("Pfizer", "Health Care"),
    "XOM": ("Exxon Mobil", "Energy"), "CVX": ("Chevron", "Energy"),
    "CAT": ("Caterpillar", "Industrials"), "BA": ("Boeing", "Industrials"), "GE": ("GE Aerospace", "Industrials"),
}
MARKET_SYMBOLS = ["SPY", "^VIX"]
GLOBAL_FEATURES = DEFAULT_FEATURES + ["mkt_ret_5", "vix"]
EXTENDED_FEATURES = GLOBAL_FEATURES + ["ret_60", "high_252_gap", "sma200_gap", "vol_ratio", "rel_ret_5", "rel_ret_20", "mkt_ret_20", "vix_chg_5"]
# Extra liquid large caps used only as additional training data (signals still display UNIVERSE)
TRAIN_UNIVERSE = (
    "CSCO IBM QCOM TXN MU AMAT LRCX ADI HON UPS RTX LMT DE MMM UNP FDX SBUX NKE LOW TGT TJX BKNG PEP PM MO CL MDLZ MRK ABT TMO DHR "
    "AMGN GILD BMY CVS C WFC MS AXP BLK SCHW USB COP SLB EOG NEE DUK SO T VZ CMCSA LIN"
).split()


def standardize(values: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.clip((values - mean) / std, -5.0, 5.0)


def sliding(z: np.ndarray, window: int) -> np.ndarray:
    """(rows, F) -> (rows - window + 1, window, F)."""
    return np.lib.stride_tricks.sliding_window_view(z, window, axis=0).transpose(0, 2, 1)


def symbol_frame(df: pd.DataFrame, market: dict[str, pd.DataFrame], features: list[str]) -> pd.DataFrame:
    return compute_features(df, market)[features].dropna()


def build_panel(
    dfs: dict[str, pd.DataFrame],
    market: dict[str, pd.DataFrame],
    features: list[str],
    window: int,
    horizon: int,
    train_end: str,
    val_end: str,
) -> dict:
    """
    Pooled windows from every symbol, split by calendar date (identical cut-offs for all symbols).
    Samples whose label window crosses a cut-off are dropped (embargo). Statistics come from train rows only.
    """
    t_end, v_end = pd.Timestamp(train_end), pd.Timestamp(val_end)
    frames = {s: symbol_frame(df, market, features) for s, df in dfs.items()}
    frames = {s: f for s, f in frames.items() if len(f) > window + horizon + 50}
    train_rows = np.concatenate([f[f.index <= t_end].to_numpy() for f in frames.values()])
    mean, std = train_rows.mean(axis=0), train_rows.std(axis=0)
    std[std < 1e-12] = 1.0

    parts: dict[str, list] = {k: [] for k in ("X", "y", "ret", "nxt", "date", "sym", "split")}
    for s, f in frames.items():
        close = dfs[s]["Close"].reindex(f.index).to_numpy()
        logc = np.log(close)
        rows = len(f)
        fwd = np.full(rows, np.nan)
        fwd[: rows - horizon] = logc[horizon:] - logc[:-horizon]
        nxt = np.full(rows, np.nan)
        nxt[:-1] = close[1:] / close[:-1] - 1.0
        W = sliding(standardize(f.to_numpy(), mean, std), window)
        ends = np.arange(window - 1, rows)
        idx = f.index[ends]
        # date of the label's last day, to apply the embargo across split boundaries
        label_end = f.index[np.minimum(ends + horizon, rows - 1)]
        split = np.where(idx <= t_end, 0, np.where(idx <= v_end, 1, 2))
        crosses = ((idx <= t_end) & (label_end > t_end)) | ((idx > t_end) & (idx <= v_end) & (label_end > v_end))
        keep = ~np.isnan(fwd[ends]) & ~crosses
        parts["X"].append(W[keep].astype(np.float32))
        parts["y"].append((fwd[ends][keep] > 0).astype(np.float32))
        parts["ret"].append(fwd[ends][keep])
        parts["nxt"].append(nxt[ends][keep])
        parts["date"].append(np.array([d.strftime("%Y-%m-%d") for d in idx[keep]]))
        parts["sym"].append(np.full(keep.sum(), s))
        parts["split"].append(split[keep])
    out = {k: np.concatenate(v) for k, v in parts.items()}
    out["mean"], out["std"] = mean, std
    out["symbols"] = sorted(frames)
    return out
