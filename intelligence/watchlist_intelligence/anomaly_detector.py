"""
Watchlist Intelligence — AI-narrated anomaly detection.
Detects: volume spikes, breakouts, sentiment spikes, options anomalies, trend reversals.
"""
import json
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
import pandas as pd
import anthropic

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER
from core.data_ingestion.options_collector import OptionsCollector

settings = get_settings()

VOLUME_SPIKE_THRESHOLD = 2.5
BREAKOUT_PCT = 0.99  # within 1% of 52w high


async def _narrate_alert(ticker: str, alert_type: str, context: dict) -> str:
    """Generate AI narration for a detected anomaly."""
    context_str = json.dumps(context, default=str)
    prompt = f"""You are a market analyst. A {alert_type} alert was detected for {ticker}.

Context: {context_str}

Write ONE sentence explaining what this means for traders watching this stock.
Be factual, specific, and educational. No buy/sell recommendation."""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return f"{ticker} {alert_type} detected."


async def scan_ticker(ticker: str) -> list[dict]:
    """Run all anomaly checks on a ticker. Returns list of AI-narrated alerts."""
    alerts = []
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="30d", interval="1d")
        if hist.empty:
            return alerts

        info = t.fast_info
        current_price = info.last_price
        prev_close = info.previous_close

        # 1. Volume spike
        avg_vol_20d = hist["Volume"].rolling(20).mean().iloc[-1]
        today_vol = hist["Volume"].iloc[-1]
        vol_ratio = today_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0

        if vol_ratio >= VOLUME_SPIKE_THRESHOLD:
            context = {"vol_ratio": round(vol_ratio, 2), "avg_vol_20d": int(avg_vol_20d)}
            narration = await _narrate_alert(ticker, "volume_spike", context)
            alerts.append({
                "type": "volume_spike",
                "ticker": ticker,
                "severity": "high" if vol_ratio > 4 else "medium",
                "data": context,
                "narration": narration,
                "disclaimer": MANDATORY_DISCLAIMER,
            })

        # 2. Breakout (52-week high proximity)
        high_52w = hist["High"].max()
        if current_price >= high_52w * BREAKOUT_PCT:
            context = {"current_price": round(current_price, 2), "high_52w": round(high_52w, 2)}
            narration = await _narrate_alert(ticker, "breakout", context)
            alerts.append({
                "type": "breakout",
                "ticker": ticker,
                "severity": "high",
                "data": context,
                "narration": narration,
                "disclaimer": MANDATORY_DISCLAIMER,
            })

        # 3. Large price move
        if prev_close:
            move_pct = (current_price - prev_close) / prev_close * 100
            if abs(move_pct) >= 4.0:
                context = {"move_pct": round(move_pct, 2), "current_price": round(current_price, 2)}
                narration = await _narrate_alert(ticker, "large_price_move", context)
                alerts.append({
                    "type": "price_move",
                    "ticker": ticker,
                    "severity": "high" if abs(move_pct) > 7 else "medium",
                    "data": context,
                    "narration": narration,
                    "disclaimer": MANDATORY_DISCLAIMER,
                })

        # 4. Options anomaly (if configured)
        try:
            options_collector = OptionsCollector()
            opt_data = options_collector.get_unusual_activity(ticker)
            if opt_data.get("unusual_activity"):
                context = {
                    "put_call_ratio": opt_data.get("put_call_ratio"),
                    "net_bias": opt_data.get("net_bias"),
                }
                narration = await _narrate_alert(ticker, "options_anomaly", context)
                alerts.append({
                    "type": "options_anomaly",
                    "ticker": ticker,
                    "severity": "medium",
                    "data": context,
                    "narration": narration,
                    "disclaimer": MANDATORY_DISCLAIMER,
                })
        except Exception:
            pass

    except Exception as exc:
        print(f"[AnomalyDetector] Error for {ticker}: {exc}")

    return alerts


async def scan_watchlist(watchlist_id: str, user_id: str) -> dict:
    """Scan all tickers in a watchlist and return AI-narrated alerts."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(
                Watchlist.watchlist_id == watchlist_id,
                Watchlist.user_id == user_id,
            )
        )
        wl = result.scalar_one_or_none()

    if not wl:
        return {"alerts": [], "tickers_scanned": 0}

    all_alerts = []
    tickers = wl.tickers or []
    for ticker in tickers:
        ticker_alerts = await scan_ticker(ticker)
        all_alerts.extend(ticker_alerts)

    return {
        "watchlist_id": watchlist_id,
        "watchlist_name": wl.name,
        "tickers_scanned": len(tickers),
        "alert_count": len(all_alerts),
        "alerts": all_alerts,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_user_alerts(user_id: str) -> dict:
    """Get all active alerts across all of a user's watchlists."""
    from apps.api.database import AsyncSessionLocal
    from database.models.users import Watchlist
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Watchlist).where(Watchlist.user_id == user_id)
        )
        watchlists = result.scalars().all()

    all_tickers = set()
    for wl in watchlists:
        for ticker in (wl.tickers or []):
            all_tickers.add(ticker)

    all_alerts = []
    for ticker in all_tickers:
        alerts = await scan_ticker(ticker)
        all_alerts.extend(alerts)

    return {
        "user_id": user_id,
        "tickers_monitored": len(all_tickers),
        "alert_count": len(all_alerts),
        "alerts": sorted(all_alerts, key=lambda x: x.get("severity", ""), reverse=True),
    }
