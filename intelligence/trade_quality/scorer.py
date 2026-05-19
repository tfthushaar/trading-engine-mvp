"""
Trade Quality Engine — scores a trade setup across 7 dimensions.

Input:  ticker, entry, stop_loss, target, timeframe
Output: overall score (0–100), grade, per-dimension breakdown, AI narrative
"""
import json
from datetime import datetime
from typing import Literal

import yfinance as yf
import pandas as pd
import numpy as np
import anthropic

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()


def _compute_technicals(ticker: str, entry: float) -> dict:
    """Fetch price history and compute key technical signals."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo", interval="1d")
        if hist.empty:
            return {}

        close = hist["Close"]
        volume = hist["Volume"]

        # Moving averages
        ema21 = close.ewm(span=21).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]
        ema200 = close.ewm(span=200).mean().iloc[-1]

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - 100 / (1 + rs)).iloc[-1]

        # ATR
        high_low = hist["High"] - hist["Low"]
        atr = high_low.rolling(14).mean().iloc[-1]

        # Volume ratio
        vol_ratio = volume.iloc[-1] / volume.rolling(20).mean().iloc[-1]

        # 52-week range
        high_52w = hist["High"].max()
        low_52w = hist["Low"].min()

        return {
            "ema21": round(ema21, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "rsi_14": round(rsi, 1),
            "atr_14": round(atr, 2),
            "volume_ratio_20d": round(vol_ratio, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "above_ema21": entry > ema21,
            "above_ema50": entry > ema50,
            "above_ema200": entry > ema200,
        }
    except Exception:
        return {}


def _score_risk_reward(entry: float, stop_loss: float, target: float) -> dict:
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    rr = reward / risk if risk > 0 else 0
    score = min(100, rr * 25)  # 4:1 RR = 100 score
    return {
        "risk_per_share": round(risk, 4),
        "reward_per_share": round(reward, 4),
        "risk_reward_ratio": round(rr, 2),
        "score": round(score, 1),
        "grade": "excellent" if rr >= 3 else "good" if rr >= 2 else "acceptable" if rr >= 1.5 else "poor",
    }


def _score_technicals(technicals: dict, entry: float, direction: str = "long") -> dict:
    if not technicals:
        return {"score": 50.0, "signals": [], "warnings": []}

    signals = []
    warnings = []
    score = 50.0

    rsi = technicals.get("rsi_14", 50)
    if direction == "long":
        if rsi < 30:
            signals.append("RSI oversold — potential entry zone")
            score += 10
        elif rsi > 70:
            warnings.append(f"RSI overbought at {rsi:.0f} — elevated risk for long entry")
            score -= 10
        elif 40 <= rsi <= 60:
            signals.append(f"RSI neutral at {rsi:.0f}")

    if technicals.get("above_ema21"):
        signals.append("Price above 21 EMA — short-term bullish")
        score += 8
    if technicals.get("above_ema50"):
        signals.append("Price above 50 EMA — medium-term bullish")
        score += 8
    if technicals.get("above_ema200"):
        signals.append("Price above 200 EMA — long-term bullish")
        score += 8

    vol_ratio = technicals.get("volume_ratio_20d", 1.0)
    if vol_ratio > 1.5:
        signals.append(f"Volume {vol_ratio:.1f}× average — confirming move")
        score += 6
    elif vol_ratio < 0.7:
        warnings.append("Below-average volume — weak confirmation")
        score -= 5

    atr = technicals.get("atr_14", 0)

    return {
        "score": round(min(100, max(0, score)), 1),
        "signals": signals,
        "warnings": warnings,
        "rsi": rsi,
        "volume_ratio": vol_ratio,
    }


async def _generate_trade_narrative(
    ticker: str, entry: float, stop_loss: float, target: float,
    rr: dict, tech: dict, overall_score: float
) -> str:
    """LLM-generated trade quality narrative."""
    prompt = f"""You are a professional trading coach reviewing a trade setup. Be direct and educational.

Trade Setup:
- Ticker: {ticker}
- Entry: ${entry}
- Stop Loss: ${stop_loss}
- Target: ${target}
- Risk/Reward: {rr['risk_reward_ratio']}:1
- Overall Score: {overall_score}/100

Technical Context:
- RSI: {tech.get('rsi_14', 'N/A')}
- Above 50 EMA: {tech.get('above_ema50', 'N/A')}
- Above 200 EMA: {tech.get('above_ema200', 'N/A')}
- Volume ratio: {tech.get('volume_ratio_20d', 'N/A')}x

Write a 3-4 sentence trade quality assessment covering: setup quality, key strengths, key risks, and one actionable suggestion. Be honest — don't hype the trade."""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return f"Trade setup for {ticker} shows a {rr['risk_reward_ratio']}:1 risk/reward ratio."


async def score_trade(
    ticker: str,
    entry: float,
    stop_loss: float,
    target: float,
    timeframe: str = "swing",
) -> dict:
    """Main entry point — score a trade across all dimensions."""
    direction = "long" if target > entry else "short"

    technicals = _compute_technicals(ticker, entry)
    rr = _score_risk_reward(entry, stop_loss, target)
    tech_score = _score_technicals(technicals, entry, direction)

    # Weighted overall score
    overall = (rr["score"] * 0.4) + (tech_score["score"] * 0.6)
    overall = round(overall, 1)

    grade = (
        "A+" if overall >= 90 else "A" if overall >= 80 else
        "B" if overall >= 70 else "C" if overall >= 60 else
        "D" if overall >= 50 else "F"
    )

    narrative = await _generate_trade_narrative(ticker, entry, stop_loss, target, rr, technicals, overall)

    return {
        "ticker": ticker.upper(),
        "direction": direction,
        "overall_score": overall,
        "grade": grade,
        "risk_reward": rr,
        "technical_analysis": tech_score,
        "technical_context": technicals,
        "ai_assessment": narrative,
        "risk_warnings": tech_score["warnings"],
        "disclaimer": MANDATORY_DISCLAIMER,
        "evaluated_at": datetime.utcnow().isoformat(),
    }
