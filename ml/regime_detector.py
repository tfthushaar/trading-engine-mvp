"""
Market Regime Classifier — XGBoost-based.

Regimes:
  BULL_TRENDING | BULL_CHOPPY | BEAR_TRENDING | BEAR_CHOPPY
  HIGH_VOLATILITY | RANGE_BOUND

Input:  SPY features + macro signals
Output: regime label + confidence + feature importance
"""
import os
import pickle
from dataclasses import dataclass
from typing import Literal
from enum import Enum

import numpy as np
import pandas as pd
import yfinance as yf

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from intelligence.base import MANDATORY_DISCLAIMER

MODEL_PATH = "ml/models/regime_detector.pkl"

RegimeLabel = Literal[
    "bull_trending", "bull_choppy", "bear_trending",
    "bear_choppy", "high_volatility", "range_bound"
]


@dataclass
class RegimeResult:
    regime: str
    confidence: float
    description: str
    implications: str
    disclaimer: str = MANDATORY_DISCLAIMER


def _get_spy_features() -> pd.DataFrame:
    """Compute regime features from SPY and VIX."""
    spy = yf.Ticker("SPY").history(period="1y", interval="1d")
    vix = yf.Ticker("^VIX").history(period="1y", interval="1d")

    if spy.empty:
        return pd.DataFrame()

    close = spy["Close"]
    ema50 = close.ewm(span=50).mean()
    ema200 = close.ewm(span=200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - 100 / (1 + rs)

    df = pd.DataFrame({
        "spy_return_20d": close.pct_change(20),
        "spy_above_200ma": (close > ema200).astype(int),
        "spy_ema50_vs_200": (ema50 / ema200 - 1),
        "rsi_14": rsi,
        "vol_20d": close.pct_change().rolling(20).std(),
    })

    if not vix.empty:
        vix_close = vix["Close"].reindex(df.index, method="ffill")
        df["vix_level"] = vix_close
        df["vix_change_5d"] = vix_close.pct_change(5)

    df.dropna(inplace=True)
    return df


def _rule_based_regime(features: dict) -> tuple[str, float, str]:
    """
    Fallback rule-based regime detection (no trained model needed).
    Returns (regime_label, confidence, description).
    """
    vix = features.get("vix_level", 20)
    return_20d = features.get("spy_return_20d", 0)
    above_200ma = features.get("spy_above_200ma", 1)
    vol_20d = features.get("vol_20d", 0.01)

    if vix > 30:
        return "high_volatility", 0.85, "VIX above 30 — elevated fear and uncertainty in markets"

    if above_200ma and return_20d > 0.03:
        return "bull_trending", 0.78, "SPY above 200MA with positive momentum — healthy bull market"

    if above_200ma and abs(return_20d) < 0.02:
        return "bull_choppy", 0.65, "SPY above 200MA but momentum is flat — range-bound consolidation"

    if not above_200ma and return_20d < -0.03:
        return "bear_trending", 0.80, "SPY below 200MA with negative momentum — confirmed downtrend"

    if not above_200ma and abs(return_20d) < 0.02:
        return "bear_choppy", 0.60, "SPY below 200MA but momentum is mixed — uncertain bear market"

    return "range_bound", 0.55, "Markets in equilibrium — no clear directional trend"


REGIME_IMPLICATIONS = {
    "bull_trending": "Momentum strategies and trend-following setups work well. Buy dips in leading sectors.",
    "bull_choppy": "Mean-reversion setups may work better than breakouts. Reduce position sizing.",
    "bear_trending": "Short setups have higher probability. Long positions carry significant headwind risk.",
    "bear_choppy": "Avoid large directional bets. Volatility strategies may be preferable.",
    "high_volatility": "Reduce position sizes significantly. Widen stops. Avoid overnight holds.",
    "range_bound": "Sell options premium or trade range boundaries. Breakout entries likely to fail.",
}


def detect_current_regime() -> RegimeResult:
    """Detect the current market regime using the best available method."""
    features_df = _get_spy_features()
    if features_df.empty:
        return RegimeResult(
            regime="unknown",
            confidence=0.0,
            description="Unable to compute regime — market data unavailable.",
            implications="Proceed with caution.",
        )

    latest = features_df.iloc[-1].to_dict()

    # Try XGBoost model if trained
    if XGB_AVAILABLE and os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            feature_cols = [c for c in latest if c in features_df.columns]
            X = np.array([[latest[c] for c in feature_cols]])
            proba = model.predict_proba(X)[0]
            regime_idx = int(np.argmax(proba))
            confidence = float(proba[regime_idx])
            regime_labels = ["bull_trending", "bull_choppy", "bear_trending",
                             "bear_choppy", "high_volatility", "range_bound"]
            regime = regime_labels[regime_idx]
            description = REGIME_IMPLICATIONS.get(regime, "")
            return RegimeResult(
                regime=regime,
                confidence=round(confidence, 3),
                description=description,
                implications=REGIME_IMPLICATIONS.get(regime, ""),
            )
        except Exception as exc:
            print(f"[RegimeDetector] XGBoost error: {exc} — falling back to rules")

    # Rule-based fallback
    regime, confidence, description = _rule_based_regime(latest)
    return RegimeResult(
        regime=regime,
        confidence=round(confidence, 3),
        description=description,
        implications=REGIME_IMPLICATIONS.get(regime, ""),
    )
