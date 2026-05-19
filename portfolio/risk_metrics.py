"""Portfolio risk metrics: VaR, beta, correlation."""
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

from intelligence.base import MANDATORY_DISCLAIMER


async def compute_risk_metrics(user_id: str) -> dict:
    from portfolio.analyzer import _get_positions
    positions = await _get_positions(user_id)
    if not positions:
        return {"message": "No positions found.", "disclaimer": MANDATORY_DISCLAIMER}

    tickers = [p["ticker"] for p in positions]
    spy = yf.Ticker("SPY").history(period="1y", interval="1d")["Close"]

    price_data = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="1y", interval="1d")["Close"]
            price_data[ticker] = hist
        except Exception:
            pass

    if not price_data:
        return {"message": "Unable to fetch price data.", "disclaimer": MANDATORY_DISCLAIMER}

    price_df = pd.DataFrame(price_data).dropna()
    returns_df = price_df.pct_change().dropna()
    spy_returns = spy.pct_change().dropna()

    # Portfolio weights (equal weight for now)
    n = len(price_df.columns)
    weights = np.array([1 / n] * n)

    # Portfolio daily returns
    portfolio_returns = returns_df.values @ weights

    # VaR (95% confidence, 1-day)
    var_95 = float(np.percentile(portfolio_returns, 5) * 100)
    cvar_95 = float(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)].mean() * 100)

    # Beta vs SPY
    aligned = pd.concat([pd.Series(portfolio_returns, index=returns_df.index), spy_returns], axis=1).dropna()
    if len(aligned) > 10:
        cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
        beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else 1.0
    else:
        beta = 1.0

    # Max drawdown
    cumulative = (1 + pd.Series(portfolio_returns)).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = float(drawdown.min() * 100)

    return {
        "var_95_pct": round(var_95, 3),
        "cvar_95_pct": round(cvar_95, 3),
        "beta_vs_spy": round(beta, 3),
        "max_drawdown_pct": round(max_drawdown, 2),
        "annualized_volatility_pct": round(float(np.std(portfolio_returns) * np.sqrt(252)) * 100, 2),
        "health_score": max(0, round(70 + 10 * (1 - abs(beta - 1)) - abs(max_drawdown) / 2, 1)),
        "disclaimer": MANDATORY_DISCLAIMER,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def compute_correlation_matrix(user_id: str) -> dict:
    from portfolio.analyzer import _get_positions
    positions = await _get_positions(user_id)
    tickers = [p["ticker"] for p in positions]

    price_data = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="6mo", interval="1d")["Close"]
            price_data[ticker] = hist
        except Exception:
            pass

    if len(price_data) < 2:
        return {"message": "Need at least 2 positions for correlation analysis.", "disclaimer": MANDATORY_DISCLAIMER}

    df = pd.DataFrame(price_data).dropna()
    corr = df.pct_change().corr()

    # Find highest correlation pair
    max_corr = 0.0
    max_pair = ("", "")
    for i, t1 in enumerate(corr.columns):
        for j, t2 in enumerate(corr.columns):
            if i < j:
                c = abs(corr.loc[t1, t2])
                if c > max_corr:
                    max_corr = c
                    max_pair = (t1, t2)

    return {
        "tickers": list(corr.columns),
        "matrix": corr.round(3).values.tolist(),
        "highest_correlation": {
            "pair": list(max_pair),
            "correlation": round(float(max_corr), 3),
            "risk_level": "high" if max_corr > 0.8 else "medium" if max_corr > 0.6 else "low",
        },
        "disclaimer": MANDATORY_DISCLAIMER,
    }
