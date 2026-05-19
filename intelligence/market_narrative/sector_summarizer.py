"""Sector-level AI narrative generator."""
from datetime import datetime, timezone
import yfinance as yf
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SECTOR_ETF_MAP = {
    "technology": "XLK", "financials": "XLF", "healthcare": "XLV",
    "energy": "XLE", "consumer_discretionary": "XLY", "industrials": "XLI",
    "utilities": "XLU", "materials": "XLB", "real_estate": "XLRE",
    "consumer_staples": "XLP", "communication": "XLC",
}

SECTOR_LEADERS = {
    "technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMD"],
    "financials": ["JPM", "BAC", "GS", "WFC", "MS"],
    "healthcare": ["JNJ", "UNH", "ABBV", "PFE", "LLY"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB"],
}


async def summarize_sector(sector: str) -> dict:
    sector_key = sector.lower().replace(" ", "_").replace("-", "_")
    etf = SECTOR_ETF_MAP.get(sector_key, "SPY")
    leaders = SECTOR_LEADERS.get(sector_key, [])

    etf_data = {}
    try:
        t = yf.Ticker(etf)
        info = t.fast_info
        etf_data = {
            "etf": etf,
            "price": round(info.last_price, 2),
            "change_pct": round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            ),
        }
    except Exception:
        etf_data = {"etf": etf, "price": None, "change_pct": None}

    leaders_data = []
    for sym in leaders[:4]:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            leaders_data.append({
                "ticker": sym,
                "change_pct": round(
                    (info.last_price - info.previous_close) / info.previous_close * 100, 2
                ),
            })
        except Exception:
            pass

    leaders_text = ", ".join(
        f"{l['ticker']} ({'+' if l['change_pct'] > 0 else ''}{l['change_pct']}%)"
        for l in leaders_data
    )

    prompt = f"""Analyze the {sector} sector and write a brief market intelligence summary.

ETF ({etf}): {etf_data.get('change_pct', 'N/A')}% today
Key stocks: {leaders_text or 'N/A'}

Write 2-3 sentences: what is driving sector performance today, and what traders should watch.
Be factual. No buy/sell recommendations."""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = response.content[0].text.strip()
    except Exception:
        narrative = f"The {sector} sector ETF ({etf}) is trading at {etf_data.get('change_pct', 'N/A')}% today."

    return {
        "sector": sector,
        "etf_data": etf_data,
        "leaders": leaders_data,
        "narrative": narrative,
        "disclaimer": MANDATORY_DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
