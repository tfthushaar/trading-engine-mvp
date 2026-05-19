"""
Market Narrative Engine — generates three daily artifacts:
  A. Pre-market briefing (08:00)
  B. Intraday snapshot (12:00)
  C. EOD debrief (16:30)

Also generates per-ticker summaries.
"""
import json
from datetime import datetime, timezone

import yfinance as yf
import anthropic

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

MACRO_SYMBOLS = {
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "IWM": "Russell 2000",
    "^VIX": "VIX", "^TNX": "10Y Treasury Yield", "DX-Y.NYB": "US Dollar Index",
}

SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Healthcare": "XLV",
    "Energy": "XLE", "Consumer Disc.": "XLY", "Industrials": "XLI",
}


def _get_macro_snapshot() -> dict:
    snapshot = {}
    for sym, label in MACRO_SYMBOLS.items():
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            change_pct = round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            )
            snapshot[label] = {"price": round(info.last_price, 2), "change_pct": change_pct}
        except Exception:
            snapshot[label] = {"price": None, "change_pct": None}
    return snapshot


def _get_sector_snapshot() -> dict:
    snapshot = {}
    for sector, etf in SECTOR_ETFS.items():
        try:
            t = yf.Ticker(etf)
            info = t.fast_info
            change_pct = round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            )
            snapshot[sector] = {"etf": etf, "change_pct": change_pct}
        except Exception:
            snapshot[sector] = {"etf": etf, "change_pct": None}
    return snapshot


async def _call_llm(prompt: str, max_tokens: int = 600) -> str:
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        print(f"[BriefingGenerator] LLM error: {exc}")
        return "Market briefing temporarily unavailable."


async def generate_daily_briefing() -> dict:
    """Pre-market AI briefing. Cached in DB for 4 hours."""
    macro = _get_macro_snapshot()
    sectors = _get_sector_snapshot()
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    macro_text = "\n".join(
        f"  {label}: {d['price']} ({'+' if d['change_pct'] and d['change_pct']>0 else ''}{d['change_pct']}%)"
        for label, d in macro.items() if d["price"]
    )
    sector_text = "\n".join(
        f"  {sector}: {d['change_pct']}%"
        for sector, d in sectors.items() if d["change_pct"] is not None
    )

    prompt = f"""You are a senior market analyst writing the daily pre-market briefing for {today}.

Current Market Data:
{macro_text}

Sector Performance:
{sector_text}

Write a professional pre-market briefing in this exact structure:

1. MARKET MOOD (1 sentence — overall tone)
2. TOP 3 CATALYSTS (numbered list — what traders need to know today)
3. SECTOR TO WATCH (which sector and exactly why)
4. KEY LEVELS (2-3 price levels on SPY or QQQ to watch)
5. RISK EVENTS (scheduled economic events or earnings today)

Keep it tight, factual, and actionable. No fluff. No promises about direction."""

    briefing_text = await _call_llm(prompt, max_tokens=700)

    # Parse sections
    catalysts = []
    sectors_to_watch = []
    risk_events = []
    lines = briefing_text.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith(("1.", "2.", "3.")) and len(catalysts) < 3:
            catalysts.append(line.lstrip("123. "))
        if "watch" in line.lower() and len(sectors_to_watch) < 2:
            sectors_to_watch.append(line)
        if any(kw in line.lower() for kw in ["fed", "cpi", "pce", "earnings", "gdp", "jobs"]):
            risk_events.append(line)

    return {
        "date": today,
        "briefing": briefing_text,
        "top_catalysts": catalysts[:3] or ["Market data being processed."],
        "sectors_to_watch": sectors_to_watch[:2] or list(sectors.keys())[:2],
        "risk_events": risk_events[:4],
        "macro_snapshot": macro,
        "sector_snapshot": sectors,
        "disclaimer": MANDATORY_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_ticker_summary(ticker: str) -> dict:
    """Full AI intelligence summary for a single ticker."""
    technicals_text = ""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo", interval="1d")
        info = t.fast_info
        close = hist["Close"]
        ema50 = close.ewm(span=50).mean().iloc[-1]
        rsi_val = 50.0
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi_val = (100 - 100 / (1 + rs)).iloc[-1]

        technicals_text = (
            f"Price: ${info.last_price:.2f}, "
            f"Change: {(info.last_price - info.previous_close) / info.previous_close * 100:.2f}%, "
            f"RSI(14): {rsi_val:.1f}, 50 EMA: ${ema50:.2f}, "
            f"52W High: ${hist['High'].max():.2f}, 52W Low: ${hist['Low'].min():.2f}"
        )
    except Exception:
        technicals_text = "Technical data unavailable."

    prompt = f"""Analyze {ticker} and provide a comprehensive but concise market intelligence summary.

Technical Data: {technicals_text}

Write a 4-5 sentence summary covering:
1. Current price action and trend
2. Key support/resistance levels
3. Momentum and volume analysis
4. Overall assessment for traders (bullish/bearish/neutral with reasons)

Be factual and educational. Do not make price predictions. Do not recommend buying or selling."""

    summary = await _call_llm(prompt, max_tokens=350)

    return {
        "ticker": ticker,
        "summary": summary,
        "disclaimer": MANDATORY_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
